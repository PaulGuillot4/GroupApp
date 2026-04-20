import pytest
from sqlalchemy import text
from src.db import get_engine
from src.models import metadata


@pytest.fixture(scope="session")
def engine():
    eng = get_engine()
    with eng.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS files"))
        conn.commit()
    metadata.create_all(eng)
    yield eng
    metadata.drop_all(eng)


@pytest.fixture
def conn(engine):
    with engine.connect() as c:
        yield c
        c.rollback()
