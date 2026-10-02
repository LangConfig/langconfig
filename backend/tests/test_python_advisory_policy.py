"""Python advisory gate behavior without a database, network, or scanner install."""

import importlib.util
import json
import subprocess
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("python_advisory_policy", ROOT / "scripts/check-python-advisories.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)
TODAY = date(2026, 9, 25)


@pytest.fixture
def policy():
    return json.loads((ROOT / "security/dependency-exceptions.json").read_text(encoding="utf-8"))


@pytest.fixture
def report():
    return {"dependencies": [{"name": "nltk", "version": "3.10.3", "vulns": [{
        "id": "PYSEC-2026-3740", "aliases": ["GHSA-8mgp-746c-j5xp"], "fix_versions": [],
    }]}], "fixes": []}


@pytest.fixture(autouse=True)
def fixed_review_date(monkeypatch):
    class ReviewDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 9, 25, tzinfo=tz)

    monkeypatch.setattr(audit, "datetime", ReviewDateTime)


def test_policy_contains_only_original_python_records(policy):
    assert set(policy) == {"schema_version", "exceptions"}
    assert {(item["package"], item["version"]) for item in policy["exceptions"]} == {
        ("nltk", "3.10.3"),
    }
    assert all(item["reviewed_on"] == "2026-09-08" and item["expires"] == "2026-10-08"
               for item in policy["exceptions"])


def test_exact_exception_passes_and_remains_visible(report, policy):
    before = deepcopy(report)
    failures, accepted = audit.assess(report, policy, 1, TODAY)
    assert failures == []
    assert len(accepted) == 1
    assert "nltk==3.10.3" in accepted[0]
    assert "2026-10-08" in accepted[0]
    assert report == before


@pytest.mark.parametrize("key,value", [("name", "other-package"), ("version", "3.10.4")])
def test_exception_does_not_cover_other_package_or_version(report, policy, key, value):
    report["dependencies"][0][key] = value
    failures, accepted = audit.assess(report, policy, 1, TODAY)
    assert len(failures) == 1 and failures[0].startswith("UNASSESSED")
    assert not accepted


def test_unlisted_advisory_fails_even_on_excepted_package(report, policy):
    report["dependencies"][0]["vulns"].append({"id": "NEW-1", "aliases": [], "fix_versions": []})
    failures, accepted = audit.assess(report, policy, 1, TODAY)
    assert len(failures) == len(accepted) == 1
    assert "NEW-1" in failures[0]


def test_alias_can_be_primary_identifier(report, policy):
    report["dependencies"][0]["vulns"][0].update(id="GHSA-8mgp-746c-j5xp", aliases=[])
    assert audit.assess(report, policy, 1, TODAY)[0] == []


def test_expiry_is_exclusive_and_fails_even_without_findings(report, policy):
    failures, accepted = audit.assess(report, policy, 1, date(2026, 10, 8))
    assert any("EXPIRED" in failure for failure in failures)
    assert not accepted
    report["dependencies"][0]["vulns"] = []
    assert audit.assess(report, policy, 0, date(2026, 10, 8))[0]


def test_upstream_fix_requires_reassessment(report, policy):
    report["dependencies"][0]["vulns"][0]["fix_versions"] = ["3.10.4"]
    failures, accepted = audit.assess(report, policy, 1, TODAY)
    assert "FIX AVAILABLE" in failures[0]
    assert not accepted


@pytest.mark.parametrize("status", [2, 127, -9])
def test_scanner_failure_is_never_clean(report, policy, status):
    with pytest.raises(ValueError, match="Scanner failed"):
        audit.assess(report, policy, status, TODAY)


@pytest.mark.parametrize("invalid", [
    {}, [], {"dependencies": []},
    {"dependencies": [{"name": "x", "skip_reason": "network"}]},
    {"dependencies": [{"name": "x", "version": "1.0", "vulns": [], "skip_reason": "network"}]},
    {"dependencies": [{"name": "x", "version": "1.0", "vulns": None}]},
    {"dependencies": [{"name": "x", "version": "1.0", "vulns": [{}]}]},
])
def test_malformed_or_partial_report_fails(invalid, policy):
    with pytest.raises((ValueError, TypeError)):
        audit.assess(invalid, policy, 0, TODAY)


@pytest.mark.parametrize("field,value", [("aliases", None), ("fix_versions", None), ("aliases", [1])])
def test_malformed_advisory_rejected(report, policy, field, value):
    report["dependencies"][0]["vulns"][0][field] = value
    with pytest.raises(ValueError, match="Malformed advisory"):
        audit.assess(report, policy, 1, TODAY)


def test_exit_status_must_agree_with_findings(report, policy):
    with pytest.raises(ValueError, match="exit status disagrees"):
        audit.assess(report, policy, 0, TODAY)
    report["dependencies"][0]["vulns"] = []
    with pytest.raises(ValueError, match="exit status disagrees"):
        audit.assess(report, policy, 1, TODAY)


@pytest.mark.parametrize("field", ["reason", "version", "exposure_assessment", "aliases", "expires"])
def test_incomplete_exception_rejected(report, policy, field):
    del policy["exceptions"][0][field]
    with pytest.raises(ValueError):
        audit.assess(report, policy, 1, TODAY)


@pytest.mark.parametrize("field,value", [
    ("version", ">=3.10.3"), ("reviewed_on", "2026-09-26"),
    ("expires", "2026-12-08"), ("expires", "not-a-date"),
])
def test_invalid_exception_window_or_version_rejected(report, policy, field, value):
    policy["exceptions"][0][field] = value
    with pytest.raises(ValueError):
        audit.assess(report, policy, 1, TODAY)


@pytest.mark.parametrize("mode,expected_status,expected_message", [
    ("clean", 0, "0 accepted finding(s), 0 policy failure(s)"),
    ("accepted", 0, "ACCEPTED until 2026-10-08 nltk==3.10.3"),
    ("unassessed", 1, "UNASSESSED nltk==3.10.3: NEW-1"),
])
def test_cli_result_paths_resolve_complete_manifest(
    tmp_path, monkeypatch, capsys, report, mode, expected_status, expected_message,
):
    if mode == "clean":
        report["dependencies"][0]["vulns"] = []
    elif mode == "unassessed":
        report["dependencies"][0]["vulns"] = [{"id": "NEW-1", "aliases": [], "fix_versions": []}]
    output = json.dumps(report)
    calls = []

    def scan(command, **options):
        calls.append((command, options))
        return subprocess.CompletedProcess(command, 0 if mode == "clean" else 1, output, "")

    monkeypatch.setattr(audit.subprocess, "run", scan)
    destination = tmp_path / "report.json"
    assert audit.main(["--report", str(destination)]) == expected_status
    assert expected_message in capsys.readouterr().out
    assert destination.read_text(encoding="utf-8") == output
    assert len(calls) == 1
    command, options = calls[0]
    assert command[:5] == [audit.sys.executable, "-m", "pip_audit", "-r", str(ROOT / "backend/requirements.txt")]
    assert "--strict" in command
    assert not {"--no-deps", "--disable-pip", "--ignore-vuln"}.intersection(command)
    assert options["timeout"] == 600
    assert options["capture_output"] and options["text"]


@pytest.mark.parametrize("status,output", [
    (2, '{"dependencies": [{"name": "x", "version": "1.0", "vulns": []}]}'),
    (0, "not-json"),
    (0, '{"dependencies": []}'),
    (1, '{"dependencies": [{"name": "x", "version": "1.0", "skip_reason": "network"}]}'),
])
def test_cli_errors_replace_stale_report_and_fail(tmp_path, monkeypatch, capsys, status, output):
    destination = tmp_path / "report.json"
    destination.write_text('{"dependencies": [{"name": "old", "version": "1.0", "vulns": []}]}')
    monkeypatch.setattr(audit.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess([], status, output, "scanner diagnostic"))
    assert audit.main(["--report", str(destination)]) == 2
    assert destination.read_text(encoding="utf-8") == output
    diagnostic = capsys.readouterr().err
    assert "AUDIT ERROR" in diagnostic and "scanner diagnostic" in diagnostic


@pytest.mark.parametrize("failure", [subprocess.TimeoutExpired("pip_audit", 600), OSError("scanner unavailable")])
def test_cli_process_failure_is_not_success(tmp_path, monkeypatch, capsys, failure):
    def scan(*args, **kwargs):
        raise failure

    monkeypatch.setattr(audit.subprocess, "run", scan)
    assert audit.main(["--report", str(tmp_path / "report.json")]) == 2
    assert "AUDIT ERROR" in capsys.readouterr().err


def test_cli_expired_policy_fails_even_on_clean_scan(tmp_path, monkeypatch, capsys, policy, report):
    for item in policy["exceptions"]:
        item["expires"] = "2026-09-25"
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(policy))
    report["dependencies"][0]["vulns"] = []
    monkeypatch.setattr(audit.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess([], 0, json.dumps(report), ""))
    assert audit.main(["--report", str(tmp_path / "report.json"), "--policy", str(policy_path)]) == 1
    assert "EXPIRED" in capsys.readouterr().out
