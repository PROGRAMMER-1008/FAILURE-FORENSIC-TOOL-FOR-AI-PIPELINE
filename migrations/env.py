from alembic import context
from ffv2.db import engine, metadata
from ffv2.settings import Settings

with engine(Settings().database_url).connect() as connection:
    context.configure(connection=connection, target_metadata=metadata)
    with context.begin_transaction():
        context.run_migrations()
