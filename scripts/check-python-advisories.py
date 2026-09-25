"""Fail closed on pip-audit errors and findings without a current exact exception.

Exit status: 0 assessed/clean, 1 policy failure, 2 scanner or malformed input.
The complete scanner report is retained, including accepted findings.
This initial gate resolves the requirements.txt manifest with pip-audit, including
transitive dependencies. It does not assume a complete dependency lock exists.
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def assess(report, policy, scanner_status, today):
    """Return visible decisions; malformed/partial scans raise ValueError/TypeError."""
    if scanner_status not in (0, 1):
        raise ValueError(f"Scanner failed with exit status {scanner_status}")
    if not isinstance(report, dict) or not isinstance(report.get("dependencies"), list):
        raise TypeError("Scanner report must contain dependencies")
    if not report["dependencies"]:
        raise ValueError("Scanner returned no dependencies")
    if not isinstance(policy, dict) or policy.get("schema_version") != 1:
        raise ValueError("Unsupported exception policy schema")
    exceptions = policy.get("exceptions")
    if not isinstance(exceptions, list):
        raise TypeError("Policy must contain exceptions")
    failures, accepted = [], []
    for item in exceptions:
        if not isinstance(item, dict) or any(not nonempty(item.get(field)) for field in (
            "package", "version", "reason", "exposure_assessment", "reviewed_on", "expires"
        )):
            raise ValueError("Exception requires exact package/version, assessment, and dates")
        if not re.fullmatch(r"[0-9]+(?:\.[0-9A-Za-z]+)*(?:[+.-][0-9A-Za-z]+)*", item["version"]):
            raise ValueError("Exception version must be exact")
        aliases = item.get("aliases")
        if not isinstance(aliases, list) or not aliases or not all(nonempty(x) for x in aliases):
            raise ValueError("Exception requires advisory aliases")
        assessed_fixes = item.get("assessed_fix_versions", [])
        if not isinstance(assessed_fixes, list) or not all(nonempty(x) for x in assessed_fixes):
            raise ValueError("Assessed fixes must be exact scanner fix entries")
        reviewed, expires = date.fromisoformat(item["reviewed_on"]), date.fromisoformat(item["expires"])
        if not reviewed < expires or (expires - reviewed).days > 30 or reviewed > today:
            raise ValueError("Exception review window must be current and at most 30 days")
        if expires <= today:
            failures.append(f"EXPIRED {item['package']}=={item['version']} ({item['expires']})")
    finding_count = 0
    for dependency in report["dependencies"]:
        if not isinstance(dependency, dict) or any(not nonempty(dependency.get(key)) for key in ("name", "version")):
            raise ValueError("Malformed or skipped dependency in scanner report")
        if "skip_reason" in dependency or not isinstance(dependency.get("vulns"), list):
            raise ValueError(f"Incomplete scan for {dependency['name']}")
        for finding in dependency["vulns"]:
            if not isinstance(finding, dict) or not nonempty(finding.get("id")):
                raise ValueError("Malformed advisory")
            aliases = finding.get("aliases")
            fixes = finding.get("fix_versions")
            if not isinstance(aliases, list) or not all(nonempty(x) for x in aliases) or not isinstance(fixes, list) or not all(nonempty(x) for x in fixes):
                raise ValueError("Malformed advisory aliases/fixes")
            finding_count += 1
            identifiers = {finding["id"], *aliases}
            label = f"{dependency['name']}=={dependency['version']}: {finding['id']}"
            matching = [item for item in exceptions if (
                normalize(item["package"]) == normalize(dependency["name"])
                and item["version"] == dependency["version"]
                and identifiers.intersection(item["aliases"])
                and date.fromisoformat(item["expires"]) > today
            )]
            if len(matching) != 1:
                failures.append(f"UNASSESSED {label}")
            elif fixes and sorted(fixes) != sorted(matching[0].get("assessed_fix_versions", [])):
                failures.append(f"FIX AVAILABLE {label}: {', '.join(fixes)}; review exception")
            else:
                accepted.append(f"ACCEPTED until {matching[0]['expires']} {label}: {matching[0]['reason']}")
    if (scanner_status == 1) != bool(finding_count):
        raise ValueError("Scanner exit status disagrees with report; possible incomplete scan")
    return failures, accepted


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requirements", type=Path, default=ROOT / "backend/requirements.txt")
    parser.add_argument("--policy", type=Path, default=ROOT / "security/dependency-exceptions.json")
    parser.add_argument("--report", type=Path, default=ROOT / "python-advisories.json")
    args = parser.parse_args(argv)
    try:
        # Resolve the manifest fully: --no-deps and --disable-pip are unsafe here
        # because unlisted transitive dependencies also require assessment.
        # Capture stdout ourselves so a stale report can never masquerade as a new scan.
        result = subprocess.run([
            sys.executable, "-m", "pip_audit", "-r", str(args.requirements),
            "--strict", "--format", "json",
            "--aliases", "on", "--progress-spinner", "off", "--timeout", "30",
        ], capture_output=True, text=True, timeout=600, check=False)
        args.report.write_text(result.stdout, encoding="utf-8")
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        failures, accepted = assess(
            json.loads(result.stdout), json.loads(args.policy.read_text(encoding="utf-8")),
            result.returncode, datetime.now(timezone.utc).date(),
        )
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired) as exc:
        print(f"AUDIT ERROR: {exc}", file=sys.stderr)
        return 2
    for decision in [*accepted, *failures]:
        print(decision)
    print(f"Audit complete: {len(accepted)} accepted finding(s), {len(failures)} policy failure(s). Report: {args.report}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
