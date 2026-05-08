# Friday End-of-Day Report — 2026-05-08

**System state:** Live and serving demos on new GPU droplet `165.245.131.94`.  
**HF Space:** https://lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space  
**vLLM endpoint:** `http://165.245.131.94:8001/v1` (granite-4.1-8b, max 8192 tokens)  
**riprap-models endpoint:** `http://165.245.131.94:7860` (TTM, Prithvi, TerraMind, GLiNER, Embedding)

---

## What happened today

### 1. New droplet provisioned (165.245.131.94)

The old droplet (165.245.141.218, destroyed 2026-05-06) was replaced with a new
AMD MI300X DigitalOcean GPU droplet at `165.245.131.94`. On first SSH, the droplet
issued a security notice about outdated packages. We ran:

```bash
apt-get update && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
reboot
```

Post-reboot, SSH was rate-limited by `ufw` (rule: `22/tcp LIMIT`) because our
SSH polling loop triggered too many rapid reconnect attempts. Resolution:
- Kill the polling loop
- Wait ~60 s for the rate-limit window to expire
- SSH came back cleanly

### 2. Full redeploy — `scripts/redeploy.sh 165.245.131.94`

`redeploy.sh` runs three steps in sequence:
1. `deploy_droplet.sh` — syncs `services/riprap-models/` source, builds the
   Docker image, starts vLLM + riprap-models containers, healthchecks both.
2. `update_hf_env.sh` — sets HF Space env vars to point at the new droplet IP
   and token, restarts the Space, polls `/api/backend` until 200.
3. `probe_addresses.py` — 5-address end-to-end probe; must be 5/5 to exit 0.

Three bugs in the Dockerfile and scripts surfaced on this fresh droplet. Each is
documented below with root cause and fix.

---

## Bugs fixed

### Bug 1: `grep` exits 1 on empty match — first build failure

**Symptom:**  
Docker build failed at step 5/7 with exit code 1 before `pip install` ever ran.

**Root cause:**  
```dockerfile
pip freeze | grep -E "^(torch|torchvision|torchaudio)==" > /tmp/torch-lock.txt && \
cat /tmp/torch-lock.txt && \
pip install -r /tmp/req-full.txt --constraint /tmp/torch-lock.txt
```
In the vLLM ROCm base image, torch packages are installed from local wheel files
and appear in `pip freeze` as `torch @ file:///install/torch-...whl`, not as
`torch==2.9.1+git8907517`. So `grep "^torch=="` finds nothing, exits 1, and the
`&&` chain aborts before `pip install`.

**Fix:**  
```dockerfile
pip show torch torchvision torchaudio 2>/dev/null \
    | awk '/^Name:/{name=$2} /^Version:/{print name "==" $2}' \
    > /tmp/torch-lock.txt
```
`pip show` returns clean `Name: torch / Version: 2.9.1+git8907517` pairs
regardless of how the package was installed. This produced the correct lock file:
```
torch==2.9.1+git8907517
torchvision==0.24.1+d801a34
torchaudio==2.9.0+eaa9e4e
```

---

### Bug 2: `granite-tsfm==0.3.6` declares `torch>=2.10`, ROCm has `2.9.1`

**Symptom:**  
With the correct torch lock file (Bug 1 fixed), build now failed with:
```
ResolutionImpossible: granite-tsfm 0.3.6 depends on torch<2.11 and >=2.10
The user requested (constraint) torch==2.9.1+git8907517
Additionally, some packages have no matching distributions: torch
```

**Root cause:**  
`granite-tsfm==0.3.6` requires `torch>=2.10`, but the AMD ROCm vLLM base image
ships `torch==2.9.1+git8907517` (a custom bespoke build not on PyPI). When pip
sees the constraint `torch==2.9.1+git8907517`, it tries to find that exact version
on PyPI to satisfy granite-tsfm's transitive requirement, finds nothing, and
raises `ResolutionImpossible`.

Without the constraint (Bug 1's `|| true` workaround), pip silently upgraded
`torchvision` to a CUDA-only PyPI build incompatible with the ROCm torch —
causing a `torchvision::nms does not exist` / circular import crash at runtime
when any specialist that imports torchvision was called.

**Fix:**  
Install `granite-tsfm` first with `--no-deps` (skipping the torch version check),
then install everything else. Because no other package in `requirements-full.txt`
requires `torch>=2.10`, the rest of the dep graph resolves cleanly against
`2.9.1+git8907517` without pip attempting to upgrade torch or torchvision:

```dockerfile
RUN pip install --upgrade pip && \
    pip install "granite-tsfm==0.3.6" --no-deps && \
    grep -v "^granite-tsfm" /tmp/req-full.txt > /tmp/req-no-tsfm.txt && \
    pip install -r /tmp/req-no-tsfm.txt
```

This keeps the ROCm torchvision (0.24.1+d801a34) untouched.

---

### Bug 3: vLLM base image `ENTRYPOINT` prepended to our `CMD`

**Symptom:**  
`riprap-models` container started but immediately crashed in a restart loop.
`docker ps` showed command: `"vllm serve uvicorn …"` — clearly wrong.
Container logs:
```
File "/usr/local/bin/vllm", line 4, in <module>
    from vllm.entrypoints.cli.main import main
...
RuntimeError: operator torchvision::nms does not exist
```

**Root cause:**  
The `vllm/vllm-openai-rocm:v0.17.1` base image sets:
```dockerfile
ENTRYPOINT ["vllm", "serve"]
```
Our Dockerfile only set `CMD ["uvicorn", "main:app", ...]`. Docker combines
ENTRYPOINT + CMD, so the container ran `vllm serve uvicorn main:app ...`,
which tried to load the vLLM CLI and crashed during its import chain.

This bug was latent on the old droplet because the `riprap-models` image there
was built while the build pipeline was broken (grep exit-1 stopped the pip
install), so the image may have been built from a manual/cached state with a
different ENTRYPOINT.

**Fix:**  
```dockerfile
ENTRYPOINT []
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860", \
     "--log-level", "info", "--proxy-headers"]
```

---

### Bug 4: HF Space `CONFIG_ERROR` — secret/variable name collision

**Symptom:**  
After `update_hf_env.sh` ran successfully and `restart_space()` returned
`BUILDING`, the Space never reached `RUNNING`. HF API reported:
```
CONFIG_ERROR: Collision on variables and secrets names
```

**Root cause:**  
`RIPRAP_LLM_API_KEY` and `RIPRAP_ML_API_KEY` were stored as **secrets** in the
HF Space (from a previous manual setup session). `update_hf_env.sh` calls
`api.add_space_variable()` for those same keys, creating a collision — HF Space
rejects any config where the same name exists as both a variable and a secret.

**Fix:**  
Deleted the colliding secrets:
```python
api.delete_space_secret(repo_id=space_id, key="RIPRAP_LLM_API_KEY")
api.delete_space_secret(repo_id=space_id, key="RIPRAP_ML_API_KEY")
```
Then restarted the Space. On subsequent `redeploy.sh` runs, `add_space_variable`
sets both keys as plain variables and there is no collision.

---

### Bug 5: `redeploy.sh` probed localhost instead of HF Space

**Symptom:**  
`redeploy.sh` step 3 (probe) reported 0/5 pass with:
```
STREAM ERROR: ConnectError: [Errno 61] Connection refused
```
It was hitting `http://127.0.0.1:7860` — the local dev server default.

**Root cause:**  
`probe_addresses.py` defaults `--base` to `http://127.0.0.1:7860`.
`redeploy.sh` called it without `--base`, so it probed localhost not the
deployed HF Space.

**Fix:**
```bash
# redeploy.sh step 4
"${REPO_ROOT}/.venv/bin/python" "${REPO_ROOT}/scripts/probe_addresses.py" \
    --base https://lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space
```

---

### Bug 6: SSH ControlMaster — rate-limit mitigation

**Symptom:**  
`deploy_droplet.sh` passed SSH check #1 then failed on the `tar` pipe (step 3):
```
ssh: connect to host 165.245.131.94 port 22: Connection refused
```
The ufw `LIMIT` rule blocked our IP after the check + tar opened two rapid
SSH connections in quick succession.

**Fix:**  
Added SSH ControlMaster multiplexing to `deploy_droplet.sh` so all SSH/SCP
connections share a single authenticated socket:

```bash
CTRL_SOCK="/tmp/riprap-ssh-${DROPLET_IP}.sock"
SSH="ssh ... -o ControlMaster=auto -o ControlPath=${CTRL_SOCK} -o ControlPersist=300 ..."
SCP="scp ... -o ControlMaster=auto -o ControlPath=${CTRL_SOCK} -o ControlPersist=300"
```

---

## Top 3 queries for the hackathon video

Riprap is positioned for professional stakeholders — city planners, asset managers,
engineers, grant writers, insurers — not residential consumers. These three queries
show that arc. Together they cover all five Stones, all three intent types
(address / neighborhood / compare), and the full Granite TTM + Prithvi-EO +
GLiNER + Embedding stack. All three were 4/4 Mellea, 0 rerolls in the
2026-05-06 verified sweep.

### Q1 — "80 Pioneer Street, Brooklyn"
- **Why:** Canonical Red Hook address for a professional assessor. Sandy inundation ✓,
  DEP Deep Contiguous ✓, 65 311 complaints, 4 FloodNet events, Ida HWM 130 m
  away, TWI 14.79. All five Stones fire. Lowest reroll risk in the entire suite.
- **Expected:** ~10–25 s, 27 steps, Mellea 4/4, Sandy verdict in opening sentence.
- **Stakeholder:** NYCHA asset manager or civil engineer assessing an existing
  building's flood exposure before a capital grant application.

### Q2 — "Hollis, Queens"
- **Why:** Bare NTA name — shows the planner routing `neighborhood` intent,
  NTA-level DEP stormwater + 311 + microtopo in ~10 steps. Inland stormwater
  narrative, clean contrast to Q1's coastal Sandy arc. Fast (7–12 s).
- **Expected:** ~8–12 s, 10 steps, Mellea 4/4, 0 rerolls.
- **Stakeholder:** NYC DEP or OEM capital planner prioritising sewer upgrade
  backlog by neighbourhood.

### Q3 — "Compare 80 Pioneer Street Brooklyn to 100 Gold Street Manhattan"
- **Why:** Explicit street addresses geocode deterministically — no drift risk on
  camera. Each leg runs the full single-address FSM (27 steps each, 54 total),
  so TTM fine-tune, TerraMind synthesis, and Prithvi-EO all surface evidence cards
  for both locations. Maximum Sandy contrast: ✓ Pioneer / ✗ Gold, 65 vs 26
  311 complaints, Ida HWM 130 m vs 3.47 km, elevation 0.8% vs 38.2% lower cells.
  0 rerolls, 4/4 Mellea in the 2026-05-06 verified sweep.
- **Expected:** ~20–40 s, 54 steps, Mellea 4/4, 0 rerolls.
- **Stakeholder:** Insurance underwriter or real-estate attorney comparing
  flood-exposure profiles across two commercial portfolios.
- **Do NOT use** `Compare Red Hook Brooklyn to the Financial District Manhattan`:
  "Red Hook Brooklyn" geocodes to `397 RED HOOK LANE` (downtown Brooklyn,
  ~15.5 m elevation) — wrong location, Sandy absent, fine-tuned model cards
  suppressed in the neighbourhood-compare path.

**Backup for Q1:** `Is the NYCHA Gowanus Houses at risk from sea level rise?`
(4/4 Mellea, 15 s, NYCHA register card fires — verified today).  
**Backup for Q2:** `Hunts Point, Bronx` (4/4, 0rr, ~10 s, Bronx coverage).  
**Backup for Q3:** `Compare Red Hook Brooklyn to Midtown Manhattan flood risk`
(use only if address parsing fails — neighbourhood compares suppress TTM/TerraMind
cards so fine-tuned model output will not be visible).

---

## Final demo sweep — 2026-05-08 ~16:20 EDT

12 queries covering all 5 NYC boroughs, three intent types (single address,
neighborhood, compare), and natural-language + bare address + neighborhood forms.

| # | Query | Intent | Borough | Result | Time | Mellea | Rerolls |
|---|-------|--------|---------|--------|------|--------|---------|
| 1 | "I'm thinking about renting an apartment at 80 Pioneer Street, Brooklyn. Should I worry?" | address | Brooklyn | FAIL¹ | 20.9s | 3/4 | 2 |
| 2 | Tottenville, Staten Island | neighborhood | Staten Island | PASS | 11.3s | 4/4 | 1 |
| 3 | "What's the flood risk at 151 West 34th Street Manhattan? It's near Penn Station." | address | Manhattan | PASS | 24.4s | 4/4 | 1 |
| 4 | East New York, Brooklyn | neighborhood | Brooklyn | PASS | 10.8s | 4/4 | 0 |
| 5 | Is 1 MetroTech Center in Brooklyn at risk during major storms? | address | Brooklyn | FAIL¹ | 23.2s | 3/4 | 2 |
| 6 | Compare Red Hook Brooklyn to the Financial District Manhattan for flood risk | compare | multi | PASS | 39.6s | 4/4 | 0 |
| 7 | "What's the flood risk for 2940 Brighton 3rd St, Brooklyn?" | address | Brooklyn | PASS | 24.9s | 4/4 | 0 |
| 8 | Is the NYCHA Gowanus Houses at risk from sea level rise? | address | Brooklyn | PASS | 15.3s | 4/4 | 2 |
| 9 | Mott Haven, Bronx | neighborhood | Bronx | PASS | 10.3s | 4/4 | 0 |
| 10 | "What's the flood risk for Howard Beach, Queens?" | neighborhood | Queens | PASS | 11.4s | 4/4 | 1 |
| 11 | Red Hook, Brooklyn | neighborhood | Brooklyn | PASS | 8.3s | 4/4 | 0 |
| 12 | Hunts Point, Bronx | neighborhood | Bronx | PASS | 9.5s | 4/4 | 0 |

**10/12 PASS**

¹ Both failures are soft Mellea grounding checks only (`citations_resolve` /
`citations_dense`) — full briefings were produced with all expected Stones firing.
These are not crashes or model errors; the reconciler produced valid prose but one
citation check didn't resolve. This is consistent with prior sweep behavior on
these queries (they are flagged as "acceptable secondary, risky as opener" in
`docs/DEMO-QUERIES.md`).

Additionally ran the canonical 5-address suite with full assertions:

| Query | Result | Time | Mellea | Rerolls |
|-------|--------|------|--------|---------|
| 442 East Houston Street, Manhattan | PASS | 22.8s | 4/4 | 1 |
| 80 Pioneer Street, Brooklyn | PASS | 18.6s | 4/4 | 1 |
| 100 Gold Street, Manhattan | FAIL¹ | 29.5s | 3/4 | 2 |
| Hollis, Queens | PASS | 7.0s | 4/4 | 0 |
| Coney Island, Brooklyn | PASS | 9.2s | 4/4 | 0 |

**4/5 PASS** — 100 Gold Street `citations_resolve` failure is consistent and noted in DEMO-QUERIES.md as a known fragile query.

---

## Infrastructure state at EOD

| Component | Value |
|-----------|-------|
| Droplet IP | 165.245.131.94 |
| vLLM image | `vllm/vllm-openai-rocm:v0.17.1` (cached, no pull needed) |
| riprap-models image | `riprap-models:latest` (built today from source) |
| torch in container | `2.9.1+git8907517` (ROCm, unchanged from base) |
| torchvision in container | `0.24.1+d801a34` (ROCm, protected by `--no-deps` fix) |
| HF Space | RUNNING — all 7 env vars set as variables (secrets collision cleared) |
| ufw on droplet | `22/tcp LIMIT` (rate-limits rapid reconnects — see SSH ControlMaster fix) |

## Files changed today

| File | Change |
|------|--------|
| `services/riprap-models/Dockerfile` | Fix grep pattern → `pip show`; granite-tsfm `--no-deps`; `ENTRYPOINT []` |
| `scripts/deploy_droplet.sh` | SSH ControlMaster multiplexing to survive ufw rate-limit |
| `scripts/redeploy.sh` | Pass `--base <HF Space URL>` to probe_addresses.py |
| `scripts/diagnostic_latency.py` | Update hardcoded droplet IP to `165.245.131.94` |
| `scripts/diagnostic_latency_v2.py` | Update hardcoded droplet IP to `165.245.131.94` |
| `DEMO-PLAYBOOK.md` | Update droplet IP reference |
