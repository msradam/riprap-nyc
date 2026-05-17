"""Top-level Burr Application — Riprap's runtime entry point.

Composes the four pieces of the briefing pipeline:

  intake     (plan_intent → geocode_target)        — what does the user want?
  stones     (cornerstone | touchstone | lodestone | keystone)  — what does the city say?
  capstone   (assemble_legacy_state → rag → gliner → reconcile)  — write the briefing

Each Stone is a Burr `MapActions` parallel fan-out over its manifest
pebbles (`riprap/core/burr/stones.py`). The Capstone reuses the existing
`step_rag` / `step_gliner` / `step_reconcile` actions from `app/fsm.py`
unchanged — the Mellea grounding loop stays inside `mellea_validator`.

Replaces the linear ~20-action graph in `app/fsm.py:build_app`. The new
graph is 9 actions wide (4 of which fan out internally), with one
conditional transition at intake (geocode failure short-circuits to
reconcile so the user still gets a "couldn't locate" briefing).
"""
from __future__ import annotations

from burr.core import ApplicationBuilder, expr
from burr.tracking import LocalTrackingClient

from app.fsm import (
    _HEAVY_SPECIALISTS_ENABLED,
    StepEventHook,  # reuse — same hook semantics
    step_eo_chip,
    step_terramind,
    step_terramind_buildings,
    step_terramind_lulc,
)
from riprap.core.burr.capstone import (
    assemble_legacy_state,
    step_policy_corpus,
    step_reconcile,
)
from riprap.core.burr.intake import (
    geocode_target,
    plan_heuristic,
    plan_intent,
    select_deployment,
)
from riprap.core.burr.stones import (
    CornerstoneAction,
    KeystoneAction,
    LodestoneAction,
    TouchstoneAction,
)
from riprap.core.burr.templated_reconciler import reconcile_templated


def _reconciler_tier() -> str:
    """`llm` (default) or `no_llm`.

    no-LLM mode disables ONLY the two Granite calls — the planner and
    the reconciler. Specialist ML (Prithvi, TerraMind, TTM, GLiNER,
    RAG embeddings) still runs unchanged: those are data producers,
    not the prose layer. The briefing is synthesized deterministically
    from each pebble's `narration.template`; the response carries
    every probe value the UI needs.

    Legacy value `templated` is accepted as an alias for `no_llm`.
    """
    import os
    raw = os.environ.get("RIPRAP_RECONCILER_TIER", "llm").lower()
    return "no_llm" if raw == "templated" else raw


def _planner_action():
    """Select between LLM-backed planner and the regex heuristic.

    no-LLM mode disables both Granite calls — planner and reconciler.
    The heuristic planner matches the query against a small set of
    regex patterns (single_address / neighborhood) to set intent +
    first_target. LLM tier uses the Granite-driven planner which gives
    richer target classification and rationale."""
    return plan_heuristic if _reconciler_tier() == "no_llm" else plan_intent


def _capstone_actions() -> dict:
    """Returns the right Capstone action set for the active tier.

    Both tiers run `step_policy_corpus` — the text-mining pebble that
    owns retrieval + NER in one Burr action (replaced step_rag +
    step_gliner). Specialist ML still runs regardless of LLM mode.

    Only the terminal `reconcile` differs:
      - `llm`     — step_reconcile (Granite + Mellea grounded synthesis)
      - `no_llm`  — reconcile_templated (deterministic prose from
                    manifest narration templates)
    """
    reconciler = reconcile_templated if _reconciler_tier() == "no_llm" else step_reconcile
    return {"policy_corpus": step_policy_corpus, "reconcile": reconciler}


def _capstone_transitions(prev: str) -> list[tuple]:
    """Capstone edges. policy_corpus runs once, then the active
    reconciler (LLM or templated)."""
    return [
        (prev, "policy_corpus"),
        ("policy_corpus", "reconcile"),
    ]


def _chip_cluster_actions() -> dict:
    """Optional EO chip cluster — eo_chip produces a shared chip used by
    terramind_lulc + terramind_buildings. Returns an empty dict when
    heavy specialists are disabled (e.g. on disk-constrained Spaces)."""
    if not _HEAVY_SPECIALISTS_ENABLED:
        return {}
    return {
        "terramind_synthesis": step_terramind,
        "eo_chip": step_eo_chip,
        "terramind_lulc": step_terramind_lulc,
        "terramind_buildings": step_terramind_buildings,
    }


def _chip_cluster_transitions(prev: str, next_: str) -> list[tuple]:
    """Chip-cluster transitions inserted between `prev` and `next_` when
    heavy specialists are enabled. When disabled, the caller chains
    `prev → next_` directly."""
    if not _HEAVY_SPECIALISTS_ENABLED:
        return [(prev, next_)]
    return [
        (prev, "terramind_synthesis"),
        ("terramind_synthesis", "eo_chip"),
        ("eo_chip", "terramind_lulc"),
        ("terramind_lulc", "terramind_buildings"),
        ("terramind_buildings", next_),
    ]


def _tracking_dir() -> str:
    """Where the Burr LocalTrackingClient writes run artifacts."""
    import os
    from pathlib import Path
    return os.environ.get(
        "RIPRAP_BURR_TRACKING_DIR",
        str(Path(__file__).resolve().parent.parent.parent.parent / ".burr"),
    )


def build_app_from_plan(
    query: str,
    plan: dict | None,
    intent: str,
    first_target: str = "",
    *,
    project: str = "riprap",
    step_queue=None,
):
    """Build a Burr app that starts at `geocode_target` with the plan already
    in state. Used by the SSE endpoint, which runs the planner directly so
    it can stream plan tokens — skipping the duplicate plan_intent call.

    Internally the wiring is identical to `build_app`; only the
    entrypoint + initial state differ.
    """
    tracker = LocalTrackingClient(project=project, storage_dir=_tracking_dir())
    return (
        ApplicationBuilder()
        .with_state(
            query=query, trace=[],
            plan=plan, intent=intent, first_target=first_target,
        )
        .with_entrypoint("geocode_target")
        .with_tracker(tracker)
        .with_hooks(StepEventHook(step_queue))
        .with_actions(
            geocode_target=geocode_target,
            select_deployment=select_deployment,
            cornerstone=CornerstoneAction(),
            touchstone=TouchstoneAction(),
            lodestone=LodestoneAction(),
            keystone=KeystoneAction(),
            assemble_legacy_state=assemble_legacy_state,
            **_capstone_actions(),
            **_chip_cluster_actions(),
        )
        .with_transitions(
            ("geocode_target", "select_deployment"),
            ("select_deployment", "cornerstone"),
            ("cornerstone", "touchstone"),
            ("touchstone", "lodestone"),
            ("lodestone", "keystone"),
            # Optional EO chip cluster between keystone and assemble_legacy.
            *_chip_cluster_transitions("keystone", "assemble_legacy_state"),
            *_capstone_transitions("assemble_legacy_state"),
        )
        .build()
    )


def iter_steps_from_plan(query: str, plan: dict | None, intent: str,
                         first_target: str = ""):
    """SSE-friendly event generator that starts after the planner has
    already run. Yields the same shape as `iter_steps` minus the
    plan_intent event."""
    import logging
    import queue
    import threading

    from app import emissions
    from app.fsm import (
        _current_mellea_attempt_callback,
        _current_planned_specialists,
        _current_strict_mode,
        _current_token_callback,
        set_mellea_attempt_callback,
        set_planned_specialists,
        set_strict_mode,
        set_token_callback,
    )

    log = logging.getLogger("riprap.burr.iter_steps_from_plan")
    q: queue.Queue = queue.Queue()
    app = build_app_from_plan(query, plan, intent, first_target, step_queue=q)
    final_state_holder: dict = {}

    _captured_strict = _current_strict_mode()
    _captured_planned = _current_planned_specialists()
    _captured_token_cb = _current_token_callback()
    _captured_mellea_cb = _current_mellea_attempt_callback()
    _captured_tracker = emissions.current()

    def _run_iterate():
        set_strict_mode(_captured_strict)
        set_planned_specialists(_captured_planned)
        set_token_callback(_captured_token_cb)
        set_mellea_attempt_callback(_captured_mellea_cb)
        emissions.install(_captured_tracker)
        try:
            for _action, _result, state in app.iterate(halt_after=["reconcile"]):
                final_state_holder["state"] = state
        except Exception as e:  # noqa: BLE001
            log.exception("burr iterate (from-plan) raised")
            q.put(("error", {"err": f"{type(e).__name__}: {e}"}))
        finally:
            set_strict_mode(False)
            set_planned_specialists(None)
            set_token_callback(None)
            set_mellea_attempt_callback(None)
            emissions.install(None)
            q.put(None)

    runner = threading.Thread(target=_run_iterate, name="riprap-burr-iter-plan",
                              daemon=True)
    runner.start()

    while True:
        item = q.get()
        if item is None:
            break
        kind, payload = item
        if kind == "step":
            yield {
                "kind": "step",
                "step": payload.get("step"),
                "ok": payload.get("ok"),
                "elapsed_s": payload.get("elapsed_s"),
                "result": payload.get("result"),
                "err": payload.get("err"),
            }
        elif kind == "error":
            yield {"kind": "error", **payload}

    runner.join(timeout=5)
    state = final_state_holder.get("state")
    if state is None:
        yield {"kind": "final", "paragraph": "",
               "error": "FSM failed before any action completed"}
        return
    yield {
        "kind": "final",
        **_state_to_final(state),
        "trace": state.get("trace", []),
    }


def build_app(query: str, *, project: str = "riprap", step_queue=None):
    """Build the top-level Burr Application for one briefing run.

    Wiring:
      intake.plan_intent
        ├─ intent == "not_implemented" → straight to reconcile
        └─ default → intake.geocode_target
              └─ cornerstone → touchstone → lodestone → keystone
                    └─ capstone (assemble_legacy → rag → gliner → reconcile)
    """
    tracker = LocalTrackingClient(project=project, storage_dir=_tracking_dir())
    return (
        ApplicationBuilder()
        .with_state(query=query, trace=[])
        .with_entrypoint("plan_intent")
        .with_tracker(tracker)
        .with_hooks(StepEventHook(step_queue))
        .with_actions(
            plan_intent=_planner_action(),
            geocode_target=geocode_target,
            select_deployment=select_deployment,
            cornerstone=CornerstoneAction(),
            touchstone=TouchstoneAction(),
            lodestone=LodestoneAction(),
            keystone=KeystoneAction(),
            assemble_legacy_state=assemble_legacy_state,
            **_capstone_actions(),
            **_chip_cluster_actions(),
        )
        .with_transitions(
            # Intent-level branching: a not_implemented intent shouldn't
            # waste pebble work — go straight to reconcile to produce an
            # honest "we don't handle this kind of query" message.
            ("plan_intent", "reconcile", expr("intent == 'not_implemented'")),
            ("plan_intent", "geocode_target"),
            ("geocode_target", "select_deployment"),
            ("select_deployment", "cornerstone"),
            ("cornerstone", "touchstone"),
            ("touchstone", "lodestone"),
            ("lodestone", "keystone"),
            *_chip_cluster_transitions("keystone", "assemble_legacy_state"),
            *_capstone_transitions("assemble_legacy_state"),
        )
        .build()
    )


def iter_steps(query: str):
    """SSE-friendly event generator — same contract as app.fsm.iter_steps.

    Yields one dict per FSM event:
      - {"kind": "step", "step", "ok", "elapsed_s", "result", "err"}
      - {"kind": "error", "err"}
      - {"kind": "final", ...full state snapshot...}

    Internally drives Burr's `app.iterate(halt_after=["reconcile"])` on a
    background thread so per-action events reach the SSE client live
    (each Stone's MapActions reduce produces N trace records at once —
    the hook drains them in order).
    """
    import logging
    import queue
    import threading

    from app import emissions
    from app.fsm import (
        _current_mellea_attempt_callback,
        _current_planned_specialists,
        _current_strict_mode,
        _current_token_callback,
        set_mellea_attempt_callback,
        set_planned_specialists,
        set_strict_mode,
        set_token_callback,
    )

    log = logging.getLogger("riprap.burr.iter_steps")
    q: queue.Queue = queue.Queue()
    app = build_app(query, step_queue=q)
    final_state_holder: dict = {}

    # The streaming reconciler reads token / mellea-attempt callbacks +
    # planner-strict-mode flags from threadlocals set by the request
    # thread. Burr's iterate runs in this generator thread; snapshot
    # those and re-install on the worker thread so step_reconcile sees
    # them. (Same pattern as app.fsm.iter_steps.)
    _captured_strict = _current_strict_mode()
    _captured_planned = _current_planned_specialists()
    _captured_token_cb = _current_token_callback()
    _captured_mellea_cb = _current_mellea_attempt_callback()
    _captured_tracker = emissions.current()

    def _run_iterate():
        set_strict_mode(_captured_strict)
        set_planned_specialists(_captured_planned)
        set_token_callback(_captured_token_cb)
        set_mellea_attempt_callback(_captured_mellea_cb)
        emissions.install(_captured_tracker)
        try:
            for _action_obj, _result, state in app.iterate(halt_after=["reconcile"]):
                final_state_holder["state"] = state
        except Exception as e:  # noqa: BLE001
            log.exception("burr iterate raised")
            q.put(("error", {"err": f"{type(e).__name__}: {e}"}))
        finally:
            set_strict_mode(False)
            set_planned_specialists(None)
            set_token_callback(None)
            set_mellea_attempt_callback(None)
            emissions.install(None)
            q.put(None)

    runner = threading.Thread(target=_run_iterate, name="riprap-burr-iter",
                              daemon=True)
    runner.start()

    while True:
        item = q.get()
        if item is None:
            break
        kind, payload = item
        if kind == "step":
            yield {
                "kind": "step",
                "step": payload.get("step"),
                "ok": payload.get("ok"),
                "elapsed_s": payload.get("elapsed_s"),
                "result": payload.get("result"),
                "err": payload.get("err"),
            }
        elif kind == "error":
            yield {"kind": "error", **payload}

    runner.join(timeout=5)
    state = final_state_holder.get("state")
    if state is None:
        yield {"kind": "final", "paragraph": "",
               "error": "FSM failed before any action completed"}
        return
    yield {
        "kind": "final",
        **_state_to_final(state),
        "trace": state.get("trace", []),
    }


_PIPELINE_KEYS = (
    "intent", "plan", "geocode", "lat", "lon", "deployment",
    "trace",
    "rag", "gliner", "policy_corpus",
    "paragraph", "audit", "mellea", "citations",
    "terramind", "eo_chip", "terramind_lulc", "terramind_buildings",
)


def _state_to_final(state) -> dict:
    """Pluck the public state slice for the SSE final event.

    Returns every pipeline-level field plus every pebble id that has a
    value set in state. Pebble keys vary per deployment now (Boston
    writes `boston_311`, Chicago writes `chicago_311`, etc.), so a
    hand-curated whitelist would drift; this scans state instead.
    """
    out: dict = {k: state.get(k) for k in _PIPELINE_KEYS}
    # Sweep up any pebble-id state keys whose value is non-None. With
    # the writes-union, every Stone declares every place-routed pebble
    # id; only the active deployment's pebbles get non-None values.
    for k in state.keys():
        if k in _PIPELINE_KEYS or k in ("query", "first_target"):
            continue
        v = state.get(k)
        if v is not None:
            out[k] = v
    return out


def _attach_compliance_audit(out: dict) -> dict:
    """Run the briefing-standards compliance predicates on the final
    paragraph and attach a `compliance` field to the response.

    Predicates are documented in docs/briefing-standards.md; the
    implementation lives in riprap.core.compliance.
    """
    from riprap.core.compliance import check_briefing
    paragraph = out.get("paragraph") or ""
    if not paragraph:
        out["compliance"] = {"passed": False, "n_passed": 0, "n_total": 0,
                             "failed": [], "note": "no paragraph"}
        return out
    report = check_briefing(paragraph)
    out["compliance"] = {
        "passed": report.passed,
        "n_passed": len(report.passed_results),
        "n_total": len(report.results),
        "failed": [
            {"name": r.name, "rule": r.rule, "description": r.description,
             "reason": r.reason, "evidence": r.evidence[:3]}
            for r in report.failed
        ],
    }
    return out


def run(query: str) -> dict:
    """Run the app to completion. Returns the same flat dict shape the
    existing `app.fsm.run` returns so the web layer's response shape is
    unchanged. Web/main.py can switch its imports here without touching
    the SvelteKit cardAdapter.

    Deployment-aware: pebble keys come from the active registry, so a
    Chicago / heat / air deployment gets its own pebbles in the response
    without code edits.
    """
    from riprap.core.pebbles.bridge import get_registry

    app = build_app(query)
    _, _, final = app.run(halt_after=["reconcile"])

    # `deployment` is the routing decision — None when no shipped deployment
    # covers the geocoded point (sentinel "__none__" → presented as None).
    chosen = final.get("deployment")
    if chosen == "__none__":
        chosen = None
    out: dict = {
        "query": query,
        "intent": final.get("intent"),
        "plan": final.get("plan"),
        "geocode": final.get("geocode"),
        "lat": final.get("lat"),
        "lon": final.get("lon"),
        "deployment": chosen,
    }

    # Pull every pebble's state value from the deployment that was
    # actually selected for this query (per-query routing). Falling back
    # to the env-var registry would re-introduce the cross-city leak —
    # a Boston query routed to the Boston deployment would surface NYC
    # pebble keys (all None) and drop boston_311.
    try:
        from riprap.core.pebbles.deployments import deployment_by_name
        from riprap.core.pebbles import load_registry as _load_registry
        dep_for_out = deployment_by_name(chosen) if chosen else None
        if dep_for_out is not None:
            reg = _load_registry(dep_for_out.root)
            for pid in reg.ids():
                out[pid] = final.get(pid)
        else:
            # Out-of-coverage queries: still surface any pebble keys
            # state happens to carry (federal pebbles fire even without
            # a deployment — they're CONUS-wide).
            for k in final.keys():
                if k.startswith(("plan", "geocode", "intent", "trace",
                                 "lat", "lon", "deployment", "query",
                                 "rag", "gliner", "paragraph", "audit",
                                 "mellea", "citations", "dep",
                                 "terramind", "eo_chip")):
                    continue
                v = final.get(k)
                if v is not None:
                    out[k] = v
    except Exception:  # noqa: BLE001 — registry load is defensive
        pass

    # Pipeline state keys the registry doesn't own. `dep` is the legacy
    # compound assembled by assemble_legacy_state; `rag` / `gliner` are
    # backward-compat mirrors of policy_corpus; chip-cluster keys come
    # from app.fsm actions, not pebbles.
    for k in ("dep", "rag", "gliner",
              "terramind", "eo_chip", "terramind_lulc", "terramind_buildings",
              "paragraph", "audit", "mellea", "citations"):
        out[k] = final.get(k)
    out["trace"] = final.get("trace", [])

    return _attach_compliance_audit(out)
