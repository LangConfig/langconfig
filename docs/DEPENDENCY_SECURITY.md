# Dependency security checks

## Python dependency security gate

The September 25 CI failures came from inherited dependency constraints:
`cryptography<49` selected vulnerable 48.0.1, and Sentence Transformers 3
required the vulnerable Transformers 4 line. This compatibility prerequisite
now pins cryptography 50.0.1, Sentence Transformers 6.0.1, Transformers 5.16.1,
and Hugging Face Hub 1.30.0. The local CLI cleanup also declares its psutil 7.2.2
dependency directly. Other runtime ranges remain unchanged.

The Python dependency security job is enforcing. It no longer has
`continue-on-error`, and no advisory is hidden with `--ignore-vuln`.
`scripts/check-python-advisories.py` resolves the full requirements manifest
with pip-audit 2.10.1 and retains the complete JSON report as a CI artifact.
Unassessed findings, different package versions, newly available fixes,
expired assessments, scanner errors, and incomplete reports fail the job.
Exit codes are 0 for clean or explicitly assessed results, 1 for a policy
failure, and 2 for scanner/report errors. A passing gate is not a claim of
zero vulnerabilities.

## Remaining assessed finding

Only NLTK 3.10.3 / `GHSA-8mgp-746c-j5xp` remains in fresh Windows and Linux
scans. Its [maintainer advisory](https://github.com/nltk/nltk/security/advisories/GHSA-8mgp-746c-j5xp)
lists no patched release as of September 25. The affected functions accept
model-artifact paths; no calls to those functions or reliance on NLTK pathsec
were found in the application or its installed ingestion adapters. Current
Unstructured uses spaCy; LlamaIndex uses fixed stopwords and Punkt tokenization.
This review does not prove arbitrary transitive use is unreachable.

The existing exact-version assessment in `security/dependency-exceptions.json`
retains its original **October 8, 2026** expiry. No deadline was extended.
Upgrade and remove the assessment when a patched release becomes available;
the gate fails if the scanner reports a fix before the policy is reassessed.
Do not expose caller-selected NLTK model import/export paths or treat pathsec
as an application sandbox. The obsolete Accelerate exception was omitted:
current resolution selects 1.15.0 with no reported advisory.

## Reproduce and validate compatibility

```console
python -m pip install -r backend/requirements.txt
python -m pip check
python -m pip install pip-audit==2.10.1
python -m pytest --noconftest backend/tests/test_python_advisory_policy.py -q
python scripts/check-python-advisories.py
```

CI also sets `LANGCONFIG_TEST_EMBEDDINGS=1` for the backend suite. The embedding
test downloads a fixed public MiniLM model revision if absent and compares four
normalized 384-dimensional vectors against the preserved pre-upgrade fixture,
both directly and through LlamaIndex, on CPU with absolute tolerance 1e-6.
Local runs can set `LANGCONFIG_EMBEDDING_CACHE` to reuse a model cache. This
limited regression does not establish equivalence for custom models, GPUs,
or an entire historical corpus. No user vectors or application database are
rewritten by this dependency update.

The broader dependency refresh still owns the universal hashed lock and other
SDK upgrades. This initial gate resolves the manifest for its runner platform;
the Windows and Linux checks do not replace the future supported-OS matrix.

## October 1, 2026: npm security reconciliation

The starting `main` commit `7503c22` had 34 open npm Dependabot alerts.
A fresh `npm audit` reported 11 affected packages, including Nano ID findings
that were not yet in that GitHub alert snapshot. The following compatible
updates produce a report with **zero npm vulnerabilities**, including development
dependencies. Counts reflect the databases available at scan time, not a claim
that the application has no security risks.

| Dependabot PR | Package | Starting version → validated update |
| --- | --- | --- |
| [#77](https://github.com/LangConfig/langconfig/pull/77) | Axios | 1.16.1 → 1.20.0 |
| [#71](https://github.com/LangConfig/langconfig/pull/71) | baseline-browser-mapping | 2.10.33 → 2.11.27 |
| [#70](https://github.com/LangConfig/langconfig/pull/70) | Browserslist | 4.26.3 → 4.29.3 |
| [#69](https://github.com/LangConfig/langconfig/pull/69) | fflate, both dependency copies | 0.8.2 → 0.8.3; 0.6.10 → 0.6.11 |
| [#68](https://github.com/LangConfig/langconfig/pull/68) | React Router / React Router DOM | 7.17.0 → 7.18.4 |
| [#67](https://github.com/LangConfig/langconfig/pull/67) | DOMPurify | 3.4.12 → 3.4.16 |
| [#66](https://github.com/LangConfig/langconfig/pull/66) | PostCSS | 8.5.15 → 8.5.28 |
| [#65](https://github.com/LangConfig/langconfig/pull/65) | concurrently / shell-quote | 10.0.3 → 10.0.5; 1.8.4 → 1.9.0 |
| Fresh npm scan | Nano ID | 3.3.12 → 3.3.19 |

DOMPurify 3.4.13, proposed by its original PR, is affected by the newer
[GHSA-p98j-92pf-mc4p](https://github.com/advisories/GHSA-p98j-92pf-mc4p);
3.4.16 covers that finding too. Both fflate copies are updated. Browserslist's
associated compatibility datasets update with its dependency requirements.
The direct Axios, router, PostCSS and concurrently manifest floors move with
their tested lockfile versions. No force-upgrade or major framework migration
is needed for these fixes.

These older fixes were already integrated in `7503c22`:

- [#59](https://github.com/LangConfig/langconfig/pull/59): form-data 4.0.6.
- [#46](https://github.com/LangConfig/langconfig/pull/46): follow-redirects 1.16.0.
- [#48](https://github.com/LangConfig/langconfig/pull/48): python-dotenv `>=1.2.2,<2`.

[#61](https://github.com/LangConfig/langconfig/pull/61) proposes Vite 8 and
plugin-react 6. Current Vite 7.3.6 already contains the relevant security fixes;
that optional major migration remains in the separate dependency-refresh plan.

CI now runs `npm audit --audit-level=low --json` after `npm ci`, without
omitting development dependencies or ignoring advisories. Any reported
vulnerability fails the frontend job, and its full report is retained as the
`npm-advisories` artifact. Reproduce with `npm ci` followed by
`npm audit --audit-level=low`; run the lint/type/build and Hermes browser checks
documented in [QUALITY_GATES.md](QUALITY_GATES.md) before landing updates.

## October 1, 2026: Rust and Python follow-up

A fresh scan of the experimental desktop lockfile found two fixable Rust
vulnerabilities and an additional fixable unsoundness warning beyond GitHub's
initial alert list. Cargo generated these compatible updates:

| Package | Starting version → update | Reason |
| --- | --- | --- |
| h2 | 0.4.15 → 0.4.16 | [RUSTSEC-2026-0258](https://rustsec.org/advisories/RUSTSEC-2026-0258.html) |
| rustls | 0.23.42 → 0.23.45 | [RUSTSEC-2026-0285](https://rustsec.org/advisories/RUSTSEC-2026-0285.html) |
| rustls-webpki | 0.103.13 → 0.103.15 | Required by the updated rustls dependency range |
| event-listener | 5.4.1 → 5.4.2 | [RUSTSEC-2026-0221](https://rustsec.org/advisories/RUSTSEC-2026-0221.html) |

No direct Tauri dependency changed. Cargo also selected the already-locked
windows-sys 0.59.0 for five dependencies whose published ranges permit it;
0.61.2 remains locked for other consumers. No other package version changed.

With cargo-audit 0.22.2 and the October 1 RustSec database, the updated lockfile
has zero vulnerability errors, but still has **one unsoundness warning and six
unmaintained-package warnings**. The default successful exit code must not be
interpreted as a clean desktop security result:

- GLib 0.18.5: [RUSTSEC-2024-0429 / GHSA-wrw7-89jp-8q8g](https://rustsec.org/advisories/RUSTSEC-2024-0429.html),
  also tracked by Dependabot alert 114, remains unresolved.
- proc-macro-error 1.0.4: RUSTSEC-2024-0370 (unmaintained).
- unic-char-property, unic-char-range, unic-common, unic-ucd-ident, and
  unic-ucd-version 0.9.0: RUSTSEC-2025-0081, RUSTSEC-2025-0075,
  RUSTSEC-2025-0080, RUSTSEC-2025-0100, and RUSTSEC-2025-0098 (unmaintained).

The verified Linux dependency paths include Tauri 2.11.5 → GTK 0.18.2 → GLib
0.18.5 and Tauri's Wry → WebKit2GTK 2.0.2 → GLib 0.18.5. The fix starts at
GLib 0.20.0, outside GTK's `^0.18` requirement; a precise upgrade dry run fails
dependency resolution. Even the current stable
[Tauri 2.12.1 dependency metadata](https://crates.io/api/v1/crates/tauri/2.12.1/dependencies)
still requires GTK `^0.18`. GTK 0.19 exists with newer GLib, but adopting it
requires a compatible desktop-stack migration or a maintained backport. A
broad Tauri 2 update does not resolve this alert. No advisory was dismissed,
ignored, or treated as unreachable merely because the shell is experimental.

Reproduce the Rust scan from the repository root:

```console
cargo audit --file src-tauri/Cargo.lock
cargo audit --file src-tauri/Cargo.lock --deny unsound
cargo check --manifest-path src-tauri/Cargo.toml --locked
```

The second audit deliberately returns nonzero while GLib remains affected.
These are manual desktop checks, not new CI gates. A Windows compile check
does not validate Linux GTK runtime behavior, desktop installation, or
end-to-end packaging; this task does not establish desktop release readiness.

The October 1 fresh Python 3.12 Windows resolution audited all 314 selected
dependencies. NLTK 3.10.3 remains its only finding, with no published fix in
the scanner or maintainer advisory. The exact existing assessment passes the
policy gate and still expires **October 8, 2026**. No Python manifest change
or exception extension was needed. The python-dotenv constraint already on
main resolves to 1.2.4. Linux resolution is checked again by the security PR's
existing Python CI job; its full report is retained independently of npm.

Local validation on Windows passed a clean `npm ci`, full npm audit,
`npm run check:interfaces`, production build with the lazy-import guard, all
eight Hermes Chromium tests, and the locked Rust check for
`x86_64-pc-windows-msvc` with Rust 1.93.0. The initial browser run had one
30-second page-load timeout while Vite's dependency files were pending; the
unchanged eight-test suite passed on rerun in 10.7 seconds. No retries or
timeouts were loosened. Linux CI supplies the independent clean-install,
backend, and advisory-policy verification before merge.
