import pytest
from ffv2.db import engine, metadata
from ffv2.store import Store


@pytest.fixture
def store(tmp_path):
    eng = engine(f"sqlite:///{tmp_path / 'test.db'}")
    metadata.create_all(eng)
    yield Store(eng)
    eng.dispose()
