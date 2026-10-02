"""Shared safeguards for tests that rebuild a PostgreSQL schema."""

import re

from sqlalchemy.engine import make_url


def is_disposable_test_database(database_url: str) -> bool:
    """Require `test` to be a complete underscore/hyphen-delimited DB segment."""
    database_name = make_url(database_url).database or ""
    return re.search(r"(?:^|[_-])test(?:[_-]|$)", database_name.lower()) is not None
