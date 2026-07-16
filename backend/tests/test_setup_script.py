import base64
from types import SimpleNamespace

from scripts.setup import (
    INFRASTRUCTURE_ONLY_TABLES,
    check_python_version,
    ensure_env_encryption_key,
    has_application_schema,
    print_error,
    print_success,
    print_warning,
)


def test_docker_bootstrap_tables_do_not_count_as_existing_app_schema():
    assert has_application_schema(["vector_documents"]) is False
    assert has_application_schema(INFRASTRUCTURE_ONLY_TABLES) is False


def test_langconfig_table_counts_as_existing_app_schema():
    assert has_application_schema(["vector_documents", "workflow_profiles"]) is True


def test_setup_status_output_is_windows_console_safe(capsys):
    print_success("ready")
    print_warning("check")
    print_error("failed")

    capsys.readouterr().out.encode("cp1252")


def test_setup_generates_valid_key_for_blank_or_shipped_placeholder():
    for template in (
        "APP_ENCRYPTION_KEY=\n",
        "APP_ENCRYPTION_KEY=replace-with-a-generated-fernet-key\n",
    ):
        rendered, generated = ensure_env_encryption_key(template)
        value = rendered.strip().split("=", 1)[1]

        assert generated is True
        assert len(base64.urlsafe_b64decode(value.encode("ascii"))) == 32


def test_setup_preserves_existing_encryption_key():
    rendered, generated = ensure_env_encryption_key("APP_ENCRYPTION_KEY=already-unique\n")

    assert generated is False
    assert rendered == "APP_ENCRYPTION_KEY=already-unique\n"


def test_setup_accepts_supported_python_and_rejects_unproven_versions():
    assert check_python_version(SimpleNamespace(major=3, minor=12, micro=0)) is True
    assert check_python_version(SimpleNamespace(major=3, minor=10, micro=0)) is False
    assert check_python_version(SimpleNamespace(major=3, minor=14, micro=0)) is False
