"""Atomic shared quotas. Reservations survive crashes and are never refunded."""

import time
from sqlalchemy import delete
from sqlalchemy.engine import Engine
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ffv2.db import usage_windows


class BudgetExceeded(Exception):
    pass


def reserve(eng: Engine, scope: str, limit: int, seconds: int, at: int | None = None) -> bool:
    current = int(time.time()) if at is None else at
    window = current // seconds
    key = f"{scope}:{seconds}:{window}"
    insert = sqlite_insert if eng.dialect.name == "sqlite" else pg_insert
    statement = insert(usage_windows).values(key=key, used=1, expires=(window + 1) * seconds)
    reserving = statement.on_conflict_do_update(
        index_elements=[usage_windows.c.key],
        set_={"used": usage_windows.c.used + 1},
        where=usage_windows.c.used < limit,
    ).returning(usage_windows.c.used)
    with eng.begin() as conn:
        conn.execute(delete(usage_windows).where(usage_windows.c.expires < current - 86400))
        return conn.execute(reserving).scalar_one_or_none() is not None


class BudgetedProvider:
    def __init__(self, provider, eng: Engine, daily_calls: int):
        self.provider, self.engine, self.daily_calls = provider, eng, daily_calls
        self.name, self.model = provider.name, provider.model

    def generate(self, step, inputs):
        if not reserve(self.engine, "groq-calls", self.daily_calls, 86400):
            raise BudgetExceeded("Daily AI call allowance exhausted")
        return self.provider.generate(step, inputs)
