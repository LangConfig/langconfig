import base64
from types import SimpleNamespace

import pytest

from scripts import setup as setup_script
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


@pytest.fixture
def setup_root(tmp_path, monkeypatch):
    (tmp_path / ".env.example").write_text("APP_ENCRYPTION_KEY=\n", encoding="utf-8")
    monkeypatch.setattr(setup_script, "get_project_root", lambda: tmp_path)
    return tmp_path


@pytest.mark.parametrize(
    "key",
    [
        "",
        "replace-with-a-generated-fernet-key",
        "langconfig-default-insecure-key-change-me",
        "already-unique",
    ],
)
def test_setup_preserves_existing_env_bytes_and_warns_before_key_changes(setup_root, key, capsys):
    original = f"# Existing local settings\r\nAPP_ENCRYPTION_KEY={key}\r\nOTHER_SETTING=keep\n".encode()
    env_file = setup_root / ".env"
    env_file.write_bytes(original)

    assert setup_script.setup_env_file() is True

    assert env_file.read_bytes() == original
    output = capsys.readouterr().out.lower()
    assert "back up" in output
    assert "migrate" in output
    assert "re-enter" in output


def test_setup_creates_unique_key_only_for_new_env(setup_root, tmp_path_factory, monkeypatch):
    keys = []
    for root in (setup_root, tmp_path_factory.mktemp("second_setup")):
        (root / ".env.example").write_text("APP_ENCRYPTION_KEY=\n", encoding="utf-8")
        monkeypatch.setattr(setup_script, "get_project_root", lambda: root)

        assert setup_script.setup_env_file() is True

        env_file = root / ".env"
        original = env_file.read_bytes()
        key = original.decode().strip().split("=", 1)[1]
        assert len(base64.urlsafe_b64decode(key.encode("ascii"))) == 32
        keys.append(key)
        assert setup_script.setup_env_file() is True
        assert env_file.read_bytes() == original
    assert keys[0] != keys[1]


def test_existing_blank_key_credentials_remain_decryptable_after_setup(setup_root, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "")
    from services.encryption import EncryptionService

    monkeypatch.setattr(EncryptionService, "_instance", None)
    ciphertext = EncryptionService().encrypt("setup-regression-fixture")
    env_file = setup_root / ".env"
    env_file.write_text("APP_ENCRYPTION_KEY=\n", encoding="utf-8")

    assert setup_script.setup_env_file() is True

    persisted_key = env_file.read_text(encoding="utf-8").strip().split("=", 1)[1]
    monkeypatch.setenv("APP_ENCRYPTION_KEY", persisted_key)
    monkeypatch.setattr(EncryptionService, "_instance", None)
    assert EncryptionService().decrypt(ciphertext) == "setup-regression-fixture"


def test_setup_accepts_supported_python_and_rejects_unproven_versions():
    assert check_python_version(SimpleNamespace(major=3, minor=12, micro=0)) is True
    assert check_python_version(SimpleNamespace(major=3, minor=10, micro=0)) is False
    assert check_python_version(SimpleNamespace(major=3, minor=14, micro=0)) is False
