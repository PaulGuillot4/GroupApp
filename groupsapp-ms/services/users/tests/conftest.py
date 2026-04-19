import os
import pytest
from sqlalchemy import text
from src.db import get_engine
from src.models import metadata

@pytest.fixture(scope="session")
def engine():
    eng = get_engine()
    metadata.create_all(eng)
    yield eng
    metadata.drop_all(eng)

@pytest.fixture
def conn(engine):
    with engine.connect() as c:
        yield c
        c.rollback()
