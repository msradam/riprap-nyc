# Security policy

## Reporting a vulnerability

If you find a security issue in Riprap, please report it privately so
it can be triaged before disclosure.

- Email: **msrahmanadam@gmail.com** (subject prefix: `[riprap-security]`)
- Or open a [GitHub Security Advisory](https://github.com/msradam/riprap-nyc/security/advisories/new)
  on this repository.

Please do not file a public GitHub issue for security reports.

We aim to acknowledge reports within 72 hours and to ship a fix or a
mitigation plan within two weeks of triage. If the report concerns a
vulnerability in an upstream model or service Riprap depends on
(IBM Granite, vLLM, Hugging Face Spaces, NYC Open Data endpoints), we
will help coordinate disclosure with the upstream maintainer.

## Threat-surface notes

Riprap is a citation-grounded synthesis layer over public-record
data. By design, the runtime:

- contacts only **public-record APIs** (NYC Open Data, FloodNet,
  USGS, NOAA, NWS, NYS DOH, MTA, NYCHA, NYC DOE, OpenStreetMap /
  Nominatim) and the configured inference Spaces;
- does **not** authenticate against user accounts or store
  user-identifying data — the address bar is the only input;
- runs the SvelteKit UI as a static SPA over a FastAPI backend
  with no persistent database.

The vulnerability surface is therefore small. Plausible categories
worth a report:

- Prompt-injection paths via document content that escape the
  Mellea grounding loop and surface unverifiable claims as cited.
- SSRF / abuse via crafted address strings that drive backend
  HTTP calls to unintended hosts.
- Token leakage in proxy headers or SSE streams
  (`inference-vllm/proxy.py`, `web/main.py`).
- Denial-of-service patterns that exceed the hosted Space's
  resource budget.
- Supply-chain issues in pinned deps (`requirements.txt`,
  `web/sveltekit/package.json`).

## Out of scope

- Self-hosted deployments running with custom configuration or
  custom datasets — please file those as regular bugs.
- Findings that require physical or local-network access to a
  user's machine.
- Issues in the lablab.ai or Hugging Face Spaces hosting platforms
  themselves; please report those upstream.
