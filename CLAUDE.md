# Riprap — Claude Code orientation

Citation-grounded NYC flood-exposure briefings. Granite 4.1 via a
LiteLLM Router (Ollama for local/T4, vLLM-on-ROCm for the AMD MI300X
demo path), Mellea-validated reconciliation, vanilla JS + Svelte 5
custom elements, FastAPI on T4 (HF Spaces).
**AMD hackathon demo: May 4–10, 2026.**

`ARCHITECTURE.md` is the source of truth for *what the system does*.
This file is for *how to work on it*.

---

## Critical constraints

- **HF Spaces base image is Python 3.10.** This pins:
  - `mellea<0.4` (0.4+ requires 3.11+) — no `find_citations` /
    `flag_hallucinated_content` intrinsics in production.
  - `transformers>=4.55,<5` + `huggingface_hub>=0.34,<1` — coexistence
    with `granite-tsfm 0.3.x` (which calls `transformers.utils.download_url`,
    removed in transformers 5.x).
  - Don't bump these without testing the full HF rebuild end-to-end.
  - Local venv is Python 3.12 — Mellea 0.4.x is installed there but
    its RAG intrinsics need a HuggingFace transformers backend (LoRA
    loading); they don't work over Ollama. Don't accidentally rely on
    them.

- **All LLM calls go through `app/llm.py`.** Never `import ollama`
  in new code. The shim exposes `chat(model, messages, options,
  stream, format)` with the same return shape as `ollama.chat`, and
  routes through a LiteLLM Router. Two backends are wired:
  - `RIPRAP_LLM_PRIMARY=ollama` (default) — local + HF Space path.
    Quant override: `RIPRAP_OLLAMA_8B_TAG=granite4.1:8b-q3_K_M`
    saves ~1 GB resident vs the default Q4_K_M.
  - `RIPRAP_LLM_PRIMARY=vllm` + `RIPRAP_LLM_BASE_URL` +
    `RIPRAP_LLM_API_KEY` — AMD MI300X demo path. Auto-fails over to
    Ollama if vLLM is unreachable. Same env vars work for local dev,
    HF Space → AMD, or AMD droplet → AMD self-host.

  An mlx-lm-backed third backend was prototyped (Apple-Silicon-native
  via `mlx_lm.server` with speculative decoding) but reverted — the
  install bumped torch internals in a way that broke `terratorch`'s
  Prithvi backbone with a `meta vs cpu` device mismatch. Stick with
  Ollama on local; switch to vLLM for the AMD demo. mlx-lm can be
  revisited once the EO toolchain isolates its torch state.

- **Ollama and vLLM use different chat templates.** Ollama's
  Modelfile recognises `role: "document <doc_id>"` and bundles those
  into a `<documents>` block. The HF tokenizer chat template (used
  by vLLM) silently drops non-standard roles. `app/llm.py` papers
  over this: extracts document-role messages into
  `extra_body.documents` / `chat_template_kwargs.documents` for vLLM,
  while leaving them in `messages` for the Ollama fallback. It also
  normalizes vLLM's `[doc_id=X]` emissions back to `[X]` so Mellea
  checks and frontend chips see the same format from both paths.

- **The vLLM deployment serves only the 8B.** One served-name per
  vLLM process and we don't run two containers. The planner alias
  (`granite-3b`) is mapped to the same served name as the reconciler
  (`granite-4.1-8b`) when primary=vllm. On Ollama, 3B and 8B are
  distinct. Override per-alias with `RIPRAP_LLM_VLLM_3B_NAME` /
  `RIPRAP_LLM_VLLM_8B_NAME` if you stand up a second vLLM.

- **No LoRA / aLoRA / Granite Citation LoRA in production.** Even
  with vLLM available, we don't load LoRAs at runtime — Mellea's
  Ollama backend raises `NotImplementedError` for activated LoRAs,
  and we deliberately keep the call path identical across backends.
  Hand-rolled `[doc_id]` regex + reroll is the citation discipline
  mechanism. See §6 of ARCHITECTURE.md.

- **Two committed JS bundles, two source dirs.** HF Spaces does not
  run Node, so we ship pre-built artefacts:
  - `web/sveltekit/build/` — **the new design-system UI** (SvelteKit +
    adapter-static, IBM Plex, four-tier glyphs, MapLibre). Sources in
    `web/sveltekit/src/`. Rebuild with `cd web/sveltekit && npm run
    build`. FastAPI serves it at `/`, `/q/sample`, `/q/<query>`.
  - `web/static/dist/riprap.js` — legacy custom-element bundle. Sources
    in `web/svelte/src/`. Rebuild with `cd web/svelte && npm run
    build`. FastAPI serves it at `/legacy`, `/single`, `/compare`,
    `/register/*` while the new UI is being filled in.
  Commit both build outputs after editing the corresponding sources.

- **Models baked into the Docker image.** Both `granite4.1:3b` and
  `granite4.1:8b` are pulled at build time (~10 GB), so HF rebuilds
  take ~10 min. `entrypoint.sh` pre-warms the 8b into VRAM after
  Ollama is up so the first reconcile doesn't pay a cold-load.

---

## Run / build / test

```bash
# Local server (default: routes to local Ollama)
cd /Users/amsrahman/riprap-nyc
.venv/bin/uvicorn web.main:app --host 127.0.0.1 --port 7860 --log-level info
# → http://127.0.0.1:7860/  (primary UI; agent.html is the canonical home)

# Local server pointed at AMD MI300X (vLLM primary, Ollama fallback)
RIPRAP_LLM_PRIMARY=vllm \
RIPRAP_LLM_BASE_URL=http://<droplet-ip>:8000/v1 \
RIPRAP_LLM_API_KEY=<token> \
.venv/bin/uvicorn web.main:app --host 127.0.0.1 --port 7860 --log-level info
# Pill in the top-right shows "AMD MI300X · Granite 4.1 / vLLM" when
# the primary is reachable; flips amber on Ollama fallback, red if
# everything is down. Backed by GET /api/backend.

# Frontend rebuilds (only when sources change)
cd web/sveltekit && npm run build  # writes web/sveltekit/build/   (new UI)
cd web/svelte && npm run build      # writes web/static/dist/riprap.js (legacy)

# Static checks (all should be clean)
.venv/bin/ruff check app/ web/ scripts/
.venv/bin/vulture app/ web/main.py --min-confidence 90
.venv/bin/radon cc app/ web/main.py -s -n C   # complexity hotspots

# Programmatic Mellea probe (server must be running)
.venv/bin/python scripts/probe_mellea.py --query "Hollis" --runs 5
# Outputs outputs/probe_*.csv with per-attempt pass/fail, paragraph,
# elapsed time, reroll count.

# Smoke-test the streaming endpoint directly
curl -sN "http://127.0.0.1:7860/api/agent/stream?q=Hollis" --max-time 120

# Local-tuning env knobs (independent of backend):
#   OLLAMA_KEEP_ALIVE=24h          keep granite4.1:8b resident across requests
#   OLLAMA_NUM_PARALLEL=1          stop Ollama loading a 2nd copy under contention
#   RIPRAP_MELLEA_MAX_ATTEMPTS=2   cap rejection-sampling rerolls (default 2 local, 3 remote)
#   RIPRAP_TRIM_DOCS=1             drop doc messages whose specialist isn't in plan (default on)
#   RIPRAP_OLLAMA_8B_TAG=granite4.1:8b-q3_K_M   ~1 GB lighter than default Q4_K_M
```

**Don't restart uvicorn while a model is mid-generation** — Ollama will
keep the request alive but the FastAPI handler dies, leaving the user
staring at a dead stream. Pre-flight: `pkill -f "uvicorn web.main:app"`.

---

## Deploy

Single command for both remotes:

```bash
git push && git push huggingface main
```

GitHub remote = `origin` (msradam/riprap-nyc). HF Space remote =
`huggingface` (msradam/riprap-nyc on huggingface.co).

HF rebuild status:

```bash
curl -sf "https://huggingface.co/api/spaces/msradam/riprap-nyc/runtime" \
  | python3 -m json.tool
# stage: BUILDING | RUNNING_APP_STARTING | RUNNING
# sha:   should match the latest local commit when RUNNING
```

Live URL: <https://msradam-riprap-nyc.hf.space>

---

## Repo map (high-signal files)

```
app/
  llm.py                    LiteLLM Router shim. chat(model, messages, options,
                            stream, format) — drop-in for ollama.chat. Routes
                            to vLLM (AMD MI300X) when RIPRAP_LLM_PRIMARY=vllm,
                            with Ollama fallback. Extracts role="document <id>"
                            into extra_body.documents for vLLM's HF chat
                            template; normalizes [doc_id=X] -> [X]. backend_info()
                            powers the UI pill via web/main.py:/api/backend.
  fsm.py                    Burr FSM. Threadlocal hooks: set_strict_mode,
                            set_token_callback, set_mellea_attempt_callback.
                            step_reconcile() routes to reconcile_strict_streaming
                            when strict mode is on.
  reconcile.py              EXTRA_SYSTEM_PROMPT (the 4-section skeleton + citation
                            discipline). build_documents() is the doc_id ride-along.
                            verify_paragraph() is the legacy non-strict guardrail.
  mellea_validator.py       reconcile_strict_streaming() — the streaming rejection
                            sampler with 4 grounding checks (numerics_grounded,
                            no_placeholder_tokens, citations_dense,
                            citations_resolve). Reroll feedback names the specific
                            failing sentences.
  planner.py                Granite 4.1:3b intent router → live_now / single_address
                            / neighborhood / development_check / compare.
  intents/                  Per-intent orchestration. Each run() takes
                            (plan, query, progress_q, strict). Strict path uses
                            reconcile_strict_streaming via either threadlocal
                            (single_address, fsm-based) or direct call (neighborhood,
                            dev_check).
  rag.py                    Granite Embedding 278M retrieval over corpus/*.pdf.
  flood_layers/             Sandy zone, DEP scenarios, Ida HWMs, Prithvi polygons.
  context/                  Microtopo (HAND/TWI), 311, FloodNet, NOAA, NWS, DOB.
  live/ttm_forecast.py      Granite TTM r2 surge residual nowcast.

web/
  main.py                   FastAPI; SSE stream at /api/agent/stream emits
                            plan_token, plan, step, token, mellea_attempt,
                            final, error, done events.
  static/
    agent.html              Primary UI. Mounts <r-briefing>, <r-trace>,
                            <r-sources-footer> (Svelte custom elements).
    agent.js                EventSource client. setBriefingText() sets the
                            .text property on <r-briefing>; pushTraceStep()
                            calls .pushStep() on <r-trace>. Form binding is
                            BEFORE ensureMap() so a WebGL throw doesn't
                            strand the Ask button.
    dist/riprap.js          Built Svelte bundle (committed).
    components/             OLD Lit components — kept for reference but
                            not loaded by agent.html anymore.
  main.py                   Adds GET /api/backend (live LLM-backend descriptor
                            + reachability ping for the pill). All other LLM
                            traffic goes through app/llm.py — don't add
                            ollama.chat calls here.
  svelte/src/lib/           Svelte 5 sources. customElement: true globally
                            via vite.config.js.
    stores.js               highlightedDocId, citeIndex (writable). The
                            cross-component chip ↔ source-row highlight
                            reacts via these.

scripts/
  probe_mellea.py           Drives the SSE stream N times, dumps CSV.
  run_prithvi_ida.py        Offline Prithvi-EO 2.0 segmentation (one-shot).
  build_*_register.py       Bulk-mode register builders (offline).

corpus/                     5 LFS-tracked NYC policy PDFs (NPCC4 etc).
data/                       LFS-tracked baked fixtures (Sandy, DEP, Prithvi
                            polygons, DEM/HAND/TWI rasters, registers).
```

---

## Project conventions

### Document message convention

Specialists emit data as chat messages with `role="document <doc_id>"`.
Granite 4.1's Ollama template recognises this prefix and bundles them
into a `<documents>` block + auto-injects IBM's grounded-generation
system message. Don't reinvent — `app/reconcile.py:build_documents()`
already wires it. `app/llm.py` additionally extracts the same messages
into `chat_template_kwargs.documents` so vLLM's HF tokenizer template
sees them too — both backends honour the same grounding contract from
identical caller code.

### The four Mellea grounding requirements

1. **`numerics_grounded`** — every non-trivial number in the output
   appears verbatim in a source document.
2. **`no_placeholder_tokens`** — output contains no leaked
   `[source]` / `<document>` template fragments.
3. **`citations_dense`** — every non-trivial number has a `[doc_id]`
   citation **somewhere in the same sentence**. Sentence scope, not a
   character window. Identifier codes (`QN1206`, BBL parcels, `B12`)
   are skipped via `\b` word-boundary regex so they don't get treated
   as numeric claims.
4. **`citations_resolve`** — cited `doc_id`s ⊆ input `doc_id`s.

If you change the regex or sentence boundary, **re-run the probe**:

```bash
.venv/bin/python scripts/probe_mellea.py --query "Hollis" --runs 5
.venv/bin/python scripts/probe_mellea.py --query "100 Gold St Manhattan" --runs 3
.venv/bin/python scripts/probe_mellea.py --query "what are they building in Gowanus and is it risky" --runs 3
```

### Threadlocal hooks in `app/fsm.py`

The FSM is sync code called from a threadpool executor. To plumb
streaming callbacks without changing every action signature, we use
threadlocals:
- `set_strict_mode(bool)` → `_current_strict_mode()` decides whether
  `step_reconcile` routes to Mellea or the legacy reconciler.
- `set_token_callback(fn)` → `_current_token_callback()` for streaming
  tokens out of the reconciler.
- `set_mellea_attempt_callback(fn)` → fires after each Mellea attempt
  with `(attempt_idx, passed, failed)`.

**Always reset in a `finally:`.** `app/intents/single_address.py:run()`
is the canonical example.

### SSE event vocabulary (`/api/agent/stream`)

| event | payload | when |
|-------|---------|------|
| `hello` | `{query}` | connection open |
| `plan_token` | `{delta}` | each token of the planner JSON |
| `plan` | `{intent, targets, specialists, rationale}` | planner finished |
| `step` | `{step, ok, started_at, elapsed_s, result?, err?}` | each FSM action |
| `token` | `{delta, attempt?}` | each Granite reconcile token |
| `mellea_attempt` | `{attempt, passed, failed}` | end of each Mellea attempt |
| `final` | full result dict (`paragraph`, `mellea`, `audit`, `tier`, `score`, ...) | reconcile done |
| `error` | `{err}` | exception in the runner |
| `done` | `{}` | stream closing |

Frontend resets the briefing buffer when `token.attempt` changes
(handles reroll cleanly).

### Frontend property convention

Svelte custom elements take props via JS property setters:

```js
const el = document.getElementById("paragraph");  // <r-briefing>
await customElements.whenDefined("r-briefing");
el.sourceLabels = SOURCE_LABELS;
el.text = "...streaming markdown...";
```

`<r-trace>` exposes imperative methods on the host:

```js
el.pushStep({ step: "geocode", ok: true, elapsed_s: 0.3, result: {...} });
el.clear();
```

`<r-sources-footer>` reads `citeIndex` from the shared store; the
Briefing populates it whenever its `bodyHtml` is computed.

---

## Decisions worth remembering

These are paths we explored and either chose or ruled out. Don't
re-litigate them without new information.

- **Lit → Svelte (May 2026).** Three Lit components were live first
  (`web/static/components/`) but the user wanted a full Svelte
  rewrite. Migrated to Svelte 5 custom-element bundle (drop-in
  replacement — same tag names, same property API). The Lit files
  are still on disk for reference but not loaded.

- **Granite 4.x native inline citations are deprecated.** We
  investigated the `<|start_of_cite|>...<|end_of_cite|>` mode. The
  official Ollama template removed it for 4.x; `granite_common` ships
  no `granite4/` package; `granite-io` has no 4.x processor.
  4.1 emits citation tokens only in an end-of-response list, never
  inline. IBM's expected 4.x citation path is a separate LoRA on
  granite-4.0-micro that produces post-hoc JSON — needs HF
  transformers, not Ollama. **Hand-rolled `[doc_id]` regex + reroll
  is the right pattern for our setup.**

- **Mellea 0.4 RAG intrinsics aren't reachable.** `find_citations`,
  `flag_hallucinated_content`, `check_context_relevance` all route
  through `GraniteCommonAdapter` → activated LoRA on the HF
  transformers backend. `mellea/backends/ollama.py:357-359` literally
  raises `NotImplementedError` for activated LoRAs. To use them we'd
  swap the serving layer, eat ~5GB more RAM, lose Ollama's
  optimizations. Not worth it for the demo.

- **CARTO Voyager basemap (not Stadia).** Tried Stadia Alidade
  Smooth — looks great, but they 401 without an API key and
  domain allowlist. Voyager is auth-free, retina-tiled, more
  editorial than Positron.

- **Speculative streaming Mellea.** `reconcile_strict_streaming`
  streams every attempt's tokens to the user (visible at t≈30s
  instead of after t≈95s of validation silence). Inline banner
  shows reroll status. Felt latency drops dramatically even when
  total wall-clock is the same.

- **Sentence-scoped `citations_dense` + identifier-aware `\b` regex.**
  The combo killed the chronic 3/4 reroll loop on neighborhood
  queries. Hollis: was 3/4 with 2 rerolls every run; now 4/4 with
  ≤1 reroll. Don't tighten the regex back to a fixed-width window
  without re-running the probe across all three intent types.

- **LiteLLM Router for backend abstraction (May 2026).** Considered
  hand-rolling an OpenAI-vs-Ollama dispatch ourselves. LiteLLM's
  Router gives us model aliasing + fallback for free, and Mellea
  has a litellm backend if we ever need it. The shim is ~250 lines
  total (`app/llm.py`); the entire production code path stayed in
  the `ollama.chat`-shaped call signature. Don't replace this with
  the openai SDK directly — the failover behaviour is load-bearing.

- **Granite 4.1 is dense decoder-only.** Earlier confusion: the
  hybrid Mamba variants are in **Granite 4.0-H**, not 4.1. vLLM
  0.17 serves 4.1 as a vanilla LLaMA-style model — no architecture
  risk, no special flags. If a future bump introduces a hybrid 4.x,
  re-verify vLLM compatibility before deploying.

- **vLLM HF chat template emits `[doc_id=X]`, Ollama Modelfile emits
  `[X]`.** The rest of Riprap (Mellea regex, frontend chip parser,
  citations footer) was written against `[X]`. `app/llm.py` runs a
  one-line regex normalize on every response and stream chunk. Don't
  remove it without changing every other consumer.

- **HF Space → AMD GPU as primary, T4 Ollama as fallback.** Considered
  using the HF Space's bundled Ollama as a remote inference server
  (proxy `/v1/chat/completions` from FastAPI to localhost:11434) so
  that local dev could use the T4. Rejected: T4 is slower than
  MI300X, surface area is bigger, and the AMD path already covers
  the "fast remote inference" use case. The proxy idea is recoverable
  in ~25 lines of FastAPI if we ever want it.

---

## Common tasks playbook

### Add a new specialist

1. Add a module under `app/context/` or `app/flood_layers/`.
2. Add an action in `app/fsm.py` (`step_yourname`) with `@action(reads=[...], writes=[...])`.
3. Wire it into the FSM graph in the `Application.with_actions(...)` chain.
4. Add a doc message builder in `app/reconcile.py:build_documents()`.
5. Update `STEP_LABELS` in `web/static/agent.js` for the trace label.
6. Update `SOURCE_LABELS` / `SOURCE_URLS` / `SOURCE_VINTAGES` in
   `web/static/agent.js` for the chip + footer rendering.
7. Double-gate the new specialist: run the SSE probe against both
   `RIPRAP_LLM_PRIMARY=ollama` and `=vllm` and confirm the briefing
   cites the new doc_id with no Mellea regressions.

### Prototype a new specialist (experimental)

For exploratory work that isn't yet ready to land in `app/`:

1. Scaffold `experiments/<NN>_<name>/` with its own `RESULTS.md`,
   smoke tests, and cached fixtures. Don't import from `app/` except
   `app.llm.chat` — keeps the experiment portable.
2. License-check the model: confirm Apache-2.0 / MIT / BSD on the
   actual `LICENSE` file in the model repo (not the HF metadata
   field — they sometimes disagree). Add a row to
   `experiments/shared/licenses.md`.
3. Validate against both `RIPRAP_LLM_PRIMARY=ollama` and
   `=vllm` before proposing integration. Specialist behaviour must
   be backend-independent — never branch on backend in specialist
   code.
4. Only after the experiment passes both gates and produces a
   demo-safe trace UI rendering, propose a PR-style summary for
   integration into `app/`.

### Change the briefing markdown structure

1. Edit `EXTRA_SYSTEM_PROMPT` in `app/reconcile.py`.
2. Edit `renderMarkdownPure()` in `web/svelte/src/lib/Briefing.svelte`
   if you add new block syntax.
3. Rebuild Svelte: `cd web/svelte && npm run build`.
4. Re-run the probe to confirm Mellea still passes.

### Tune the Mellea checks

`app/mellea_validator.py`:
- `_NUM_RE` — number recognition. Use `\b` boundaries to skip
  identifiers.
- `_TRIVIAL_NUMS` — set of numbers exempt from citation requirement
  (small integers, NYC service line numbers like 311/911).
- `_check_every_claim_cited()` — sentence-scoped; uses `_SENT_END`
  for boundaries.
- `_failing_sentences_for_citations()` — feeds the reroll feedback
  prompt with surgical corrections.

After any change here: probe across 3 intent types (above).

### Add a new Svelte component

1. Create `web/svelte/src/lib/MyComponent.svelte` with
   `<svelte:options customElement={{ tag: "r-mycomp", props: {...} }} />`.
2. Side-effect import it in `web/svelte/src/main.js`.
3. Mount `<r-mycomp>` in `agent.html`.
4. `cd web/svelte && npm run build`.
5. Commit `web/static/dist/riprap.js` and `riprap.js.map`.

---

## Known sharp edges

- **`build_documents` complexity (radon F=101).** It's a giant
  `if`/`elif` per specialist. Don't refactor pre-demo; touching it
  risks subtle regressions in doc message ordering, which Granite is
  sensitive to.

- **Static assets cache hard.** When iterating on Svelte or `agent.js`,
  the user must hard-reload (⌘⇧R). Cache-busting query strings are
  not in place.

- **Ollama keeps stale models loaded across rebuilds locally.** If
  you change a Modelfile or pull a new tag, restart `ollama serve`
  to be sure.

- **Burr FSM `iter_steps` mutates global state.** Don't run two
  concurrent `single_address` queries against the same uvicorn
  worker — strict-mode threadlocal makes it safer than it was, but
  there's no per-request isolation.

- **Mellea 0.3 vs 0.4 API differences.** Local venv has 0.4 (3.12),
  HF has 0.3 (3.10). `start_session`, `RejectionSamplingStrategy`,
  `MelleaSession.instruct(strategy, requirements,
  return_sampling_results)` are stable across both. Don't import
  anything from `mellea.stdlib.components.intrinsic.*` — that
  package only exists in 0.4 and won't import on HF.

- **HF Space sleeps after idle.** Free tier; first request after
  sleep is a 30–90 s cold start. Ping the space before a demo.

- **vLLM cold compile / first-call slowdown.** First few requests
  against a fresh `vllm serve` container can log surprisingly low
  throughput (single-digit tokens/s prompt, ~4 tokens/s gen on a
  MI300X) while ROCm kernels JIT-compile and the prefix cache
  warms. Subsequent requests are 30–50× faster. If a benchmark
  reads "vLLM is slow" on the first run, run it three more times
  before believing it.

- **Backend pill auto-detection.** `app/llm.py:_default_hardware_label`
  picks `AMD MI300X` when `RIPRAP_LLM_PRIMARY=vllm`, `NVIDIA T4`
  when `SPACE_ID` is set (HF Spaces injects this), `Local` otherwise.
  Override with `RIPRAP_HARDWARE_LABEL` / `RIPRAP_ENGINE_LABEL`
  if you bring up a different GPU.

---

## Useful one-liners

```bash
# Tail the local server log
tail -f /tmp/riprap-local.log

# Inspect the live HF Space's deployed SHA + stage
curl -sf "https://huggingface.co/api/spaces/msradam/riprap-nyc/runtime" | python3 -m json.tool

# Confirm both remotes have the same HEAD
git log --oneline -1 && git ls-remote huggingface main | head -1

# Force-re-pull Granite weights locally if Ollama seems wrong
ollama rm granite4.1:8b && ollama pull granite4.1:8b

# What backend is the running server on? (live reachability + label)
curl -s http://127.0.0.1:7860/api/backend | python3 -m json.tool

# Bring up vLLM on a fresh AMD ROCm droplet (one-shot)
docker run -d --name vllm \
  --device=/dev/kfd --device=/dev/dri --group-add=video \
  --ipc=host --shm-size=16g -p 8000:8000 \
  -v /root/hf-cache:/root/.cache/huggingface \
  -e GLOO_SOCKET_IFNAME=eth0 -e VLLM_HOST_IP=127.0.0.1 \
  vllm/vllm-openai-rocm:v0.17.1 \
  --model ibm-granite/granite-4.1-8b \
  --host 0.0.0.0 --port 8000 --api-key "$TOKEN" \
  --max-model-len 8192 --served-model-name granite-4.1-8b
# Without GLOO_SOCKET_IFNAME, gloo fails to bind 0.0.0.0 and the
# engine core never initialises.

# Check what doc_ids the briefing should contain for an intent
.venv/bin/python -c "from app.reconcile import build_documents; \
  print([m['role'] for m in build_documents({'sandy':{'inside':True}, 'nyc311':{'n':5}})])"
```
