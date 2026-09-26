# Python dependency security gate

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
