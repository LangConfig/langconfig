import pytest

from tests.database_safety import is_disposable_test_database


@pytest.mark.parametrize(
    "database_name",
    ["langconfig_test", "test_langconfig", "langconfig-test-scratch"],
)
def test_disposable_database_guard_accepts_explicit_test_segment(database_name):
    assert is_disposable_test_database(
        f"postgresql://user:password@localhost:5432/{database_name}"
    )


@pytest.mark.parametrize(
    "database_name",
    ["langconfig", "latest", "contest", "testimonials"],
)
def test_disposable_database_guard_rejects_substring_matches(database_name):
    assert not is_disposable_test_database(
        f"postgresql://user:password@localhost:5432/{database_name}"
    )
