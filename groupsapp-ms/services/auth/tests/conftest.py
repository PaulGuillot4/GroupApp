import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent  # services/auth/
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "generated"))

import pytest


@pytest.fixture(scope="session")
def django_db_setup(django_test_environment, django_db_blocker):
    """Ensure the 'auth' schema exists and reuse the existing database."""
    with django_db_blocker.unblock():
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("CREATE SCHEMA IF NOT EXISTS auth;")
        from django.test.utils import setup_databases
        setup_databases(verbosity=0, interactive=False, keepdb=True)
