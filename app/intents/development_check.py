"""development_check intent — "what are they building in <X> and is it risky?"

Pipeline:
  1. Resolve target text → NTA polygon
  2. Pull active DOB construction permits (NB / A1 / DM, last ~18 mo)
     inside the polygon
  3. Cross-reference each permit with the Sandy + DEP scenarios already
     loaded in memory
  4. Aggregate counts; rank flagged projects by severity
  5. Reconcile via Granite 4.1 with a development-briefing prompt that
     names specific projects and addresses
"""
from __future__ import annotations

import logging
import time
from typing import Any

from app import llm
from app.areas import nta
from app.context import dob_permits
from app.rag import retrieve as rag_retrieve

log = logging.getLogger("riprap.intent.development_check")

# Reconciler model — see app/reconcile.py for the env-var contract.
import os as _os  # noqa: E402

OLLAMA_MODEL = _os.environ.get("RIPRAP_RECONCILER_MODEL",
                                _os.environ.get("RIPRAP_OLLAMA_MODEL", "granite4.1:8b"))

EXTRA_SYSTEM_PROMPT = """Write a flood-exposure briefing about active construction in an NYC neighborhood. Use ONLY the facts in the provided documents.

Output this markdown skeleton verbatim, filling each `<...>` with content drawn only from the documents. After every numerical claim, append the document id in square brackets — e.g. `<count> [dob_permits]`. Bold at most one phrase per section using `**...**`. Omit any section whose supporting facts are absent from the documents.

```
**Status.**
<one sentence: name the neighborhood from [nta_resolve] and the headline counts from [dob_permits] (total active projects, fraction in Sandy zone, fraction in DEP scenarios)>.

**Flagged projects.**
- <project address from [dob_permits]> ([dob_permits]). <job_type_label> issued <date>; owner <owner_business>. <flood-layer summary>.
- <next project from [dob_permits], same pattern>
- <continue for each flagged project, max 6>

**Pattern.**
<1-2 sentences observing which streets concentrate the flagged projects and the new-building / major-alteration mix from [dob_permits]>.

**Policy context.**
<1 sentence per RAG hit, citing the agency name and [rag_*]>.
```

Constraints:
- Copy addresses, BBLs, dates, and owner names verbatim from the documents — no paraphrasing.
- If [dob_permits] reports 0 flagged projects, omit the **Flagged projects.** section and say so in **Status.**.
- If only [nta_resolve] is present and no [dob_permits], output exactly: `No grounded data available for this neighborhood.`
"""


def run(plan, query: str, progress_q=None, strict: bool = False) -> dict[str, Any]:  # TODO(cleanup): cc-grade-D (27)
    """Execute the development_check Plan. If progress_q is provided
    (a queue.Queue), each finalized step record is put on it so a
    streaming endpoint can render the trace live.

    strict=True routes through Mellea-validated reconciliation (rejection
    sampling against four grounding requirements). Disables token
    streaming — the briefing arrives in one shot after Mellea's loop
    settles. Trace gains a `mellea_validate` row with rerolls + which
    requirements passed.
    """
    t0 = time.time()
    trace: list[dict] = []

    def _emit(r: dict):
        if progress_q is not None:
            progress_q.put({"kind": "step", **r})

    target_text = next(
        (t["text"] for t in plan.targets if t.get("type") in ("nta", "borough")),
        None,
    )
    rec = {"step": "nta_resolve", "started_at": t0, "ok": False}
    trace.append(rec)
    # Try the planner's target first; if it didn't pick one, fall back to
    # scanning the raw query text for any known neighborhood/borough name.
    matches = nta.resolve(target_text) if target_text else []
    if not matches:
        log.info("planner gave no usable target (%r); scanning query %r",
                 target_text, query)
        matches = nta.resolve_from_text(query)
    if not matches:
        rec["err"] = f"no NTA match in target={target_text!r} or query={query!r}"
        rec["elapsed_s"] = round(time.time() - t0, 2)
        return _empty(plan, query, trace, error=rec["err"])
    target = matches[0]
    rec["ok"] = True
    rec["result"] = {"nta_code": target["nta_code"],
                     "nta_name": target["nta_name"],
                     "borough":  target["borough"],
                     "bbox":     list(target["geometry"].bounds)}
    rec["elapsed_s"] = round(time.time() - t0, 2)
    _emit(rec)

    poly = target["geometry"]
    docs: list[dict] = []
    permits_summary = None
    rag_out: list = []

    # ---- DOB permits ------------------------------------------------------
    p_t0 = time.time()
    prec = {"step": "dob_permits_nta", "started_at": p_t0, "ok": False}
    trace.append(prec)
    try:
        # top_n=5: 5 flagged projects in the doc context is the sweet spot —
        # rich enough for a journalist briefing, cheap enough to stay under
        # ~25 s reconcile on T4 with the 8b model.
        permits_summary = dob_permits.summary_for_polygon(poly, top_n=5)
        prec["ok"] = True
        prec["result"] = {
            "n_total":      permits_summary["n_total"],
            "n_in_sandy":   permits_summary["n_in_sandy"],
            "n_in_dep_any": permits_summary["n_in_dep_any"],
            # Pin data so the UI can render permits the moment this step
            # finishes, instead of waiting for the `final` event.
            "all_pins":     permits_summary["all_pins"],
        }
    except Exception as e:
        prec["err"] = str(e)
        log.exception("dob_permits failed")
    prec["elapsed_s"] = round(time.time() - p_t0, 2)
    _emit(prec)

    # ---- RAG --------------------------------------------------------------
    if "rag" in plan.specialists:
        r_t0 = time.time()
        rrec = {"step": "rag_dev", "started_at": r_t0, "ok": False}
        trace.append(rrec)
        try:
            q = (f"flood resilience new construction development {target['nta_name']} "
                 f"{target['borough']} hardening building code")
            rag_out = rag_retrieve(q, k=2, min_score=0.50)
            rrec["ok"] = True
            rrec["result"] = {"hits": len(rag_out)}
        except Exception as e:
            rrec["err"] = str(e)
        rrec["elapsed_s"] = round(time.time() - r_t0, 2)
        _emit(rrec)

    # ---- documents --------------------------------------------------------
    docs.append(_doc("nta_resolve", [
        "Source: NYC DCP Neighborhood Tabulation Areas 2020.",
        f"Target neighborhood: {target['nta_name']} (NTA {target['nta_code']}), "
        f"in the borough of {target['borough']}.",
    ]))
    if permits_summary:
        ps = permits_summary
        body = [
            "Source: NYC DOB Permit Issuance (Socrata ipu4-2q9a), filtered to "
            "active New Building / Major Alteration / Demolition jobs in the "
            "trailing 18 months. Cross-referenced with NYC Sandy 2012 "
            "inundation extent and 3 DEP Stormwater scenarios.",
            f"Total active major-construction projects in {target['nta_name']}: "
            f"{ps['n_total']}.",
            f"Of these: {ps['n_in_sandy']} fall inside the 2012 Sandy "
            f"inundation zone; {ps['n_in_dep_any']} fall inside at least one "
            f"DEP Stormwater scenario; {ps['n_in_dep_severe']} fall in the "
            f"deeper DEP bands (1-4 ft or >4 ft).",
        ]
        if ps.get("by_job_type"):
            mix = "; ".join(f"{n} {k}" for k, n in ps["by_job_type"].items())
            body.append(f"Job-type mix: {mix}.")
        for p in ps["flagged_top"]:
            scen_str = (", ".join(p["dep_scenarios"]) or "none")
            body.append(
                f"- {p['address']}, {p['borough']} (BBL {p.get('bbl') or 'unknown'}). "
                f"{p['job_type_label']}, permit issued {p['issuance_date']}, "
                f"status {p['permit_status']}. "
                f"Owner: {p.get('owner_business') or 'unknown'}. "
                f"In Sandy zone: {p['in_sandy']}; in DEP scenarios: {scen_str}; "
                f"max DEP depth class: {p['dep_max_class']}."
            )
        docs.append(_doc("dob_permits", body))
    for h in rag_out:
        docs.append(_doc(h["doc_id"], [
            f"Source: {h['citation']}, page {h.get('page', '')}.",
            f"Retrieved passage (verbatim): {h['text']}",
        ]))

    # ---- reconcile --------------------------------------------------------
    rec_t0 = time.time()
    rec_step = {"step": "reconcile_development", "started_at": rec_t0, "ok": False}
    trace.append(rec_step)
    paragraph = ""
    audit = {"raw": "", "dropped": []}
    mellea_meta = None
    if len(docs) <= 1:
        paragraph = ("**Status.** No active construction permit data available "
                     f"for {target['nta_name']} [nta_resolve].")
        audit = {"raw": paragraph, "dropped": []}
        rec_step["ok"] = True
    elif strict:
        # Streaming Mellea path: tokens stream during each attempt; on
        # validation failure we emit a mellea_attempt event and reroll.
        rec_step["step"] = "mellea_reconcile_development"
        try:
            from app.framing import augment_system_prompt
            from app.mellea_validator import DEFAULT_LOOP_BUDGET, reconcile_strict_streaming
            from app.reconcile import trim_docs_to_plan as _trim
            docs = _trim(docs, set(plan.specialists or []))
            def _on_token(delta: str, attempt_idx: int):
                if progress_q is not None:
                    progress_q.put({"kind": "token", "delta": delta,
                                    "attempt": attempt_idx})
            def _on_attempt_end(attempt_idx, passed, failed):
                if progress_q is not None:
                    progress_q.put({"kind": "mellea_attempt",
                                    "attempt": attempt_idx,
                                    "passed": passed, "failed": failed})
            framed_prompt = augment_system_prompt(
                EXTRA_SYSTEM_PROMPT, query=query, intent=plan.intent,
            )
            mres = reconcile_strict_streaming(
                docs, framed_prompt,
                user_prompt="Write the development briefing now.",
                model=OLLAMA_MODEL, loop_budget=DEFAULT_LOOP_BUDGET,
                on_token=_on_token if progress_q else None,
                on_attempt_end=_on_attempt_end if progress_q else None,
            )
            paragraph = mres["paragraph"]
            audit = {"raw": paragraph, "dropped": []}
            mellea_meta = {
                "rerolls": mres["rerolls"],
                "n_attempts": mres["n_attempts"],
                "requirements_passed": mres["requirements_passed"],
                "requirements_failed": mres["requirements_failed"],
                "requirements_total": mres["requirements_total"],
                "model": mres["model"],
                "loop_budget": mres["loop_budget"],
            }
            rec_step["ok"] = True
            rec_step["result"] = {
                "rerolls": mellea_meta["rerolls"],
                "passed": f"{len(mellea_meta['requirements_passed'])}/{mellea_meta['requirements_total']}",
                "paragraph_chars": len(paragraph),
            }
        except Exception as e:
            rec_step["err"] = str(e)
            log.exception("Mellea-validated reconcile failed")
            paragraph = ""
            audit = {"raw": "", "dropped": []}
    else:
        def _on_token(delta: str):
            if progress_q is not None:
                progress_q.put({"kind": "token", "delta": delta})
        try:
            paragraph, audit = _reconcile(docs, on_token=_on_token if progress_q else None)
            rec_step["ok"] = True
            rec_step["result"] = {"paragraph_chars": len(paragraph),
                                  "dropped": len(audit["dropped"])}
        except Exception as e:
            rec_step["err"] = str(e)
            log.exception("development reconcile failed")
    rec_step["elapsed_s"] = round(time.time() - rec_t0, 2)
    _emit(rec_step)

    target_safe = {k: v for k, v in target.items() if k != "geometry"}
    target_safe["bbox"] = list(target["geometry"].bounds)
    return {
        "intent":          "development_check",
        "query":           query,
        "plan": {
            "intent": plan.intent,
            "targets": plan.targets,
            "specialists": plan.specialists,
            "rationale": plan.rationale,
        },
        "target":          target_safe,
        "n_matches":       len(matches),
        "dob_summary":     permits_summary,
        "rag":             rag_out,
        "paragraph":       paragraph,
        "audit":           audit,
        "mellea":          mellea_meta,
        "trace":           trace,
        "total_s":         round(time.time() - t0, 2),
    }


def _doc(doc_id: str, body_lines: list[str]) -> dict:
    return {"role": f"document {doc_id}", "content": "\n".join(body_lines)}


def _reconcile(docs: list[dict], on_token=None) -> tuple[str, dict]:
    from app.reconcile import verify_paragraph
    messages = docs + [
        {"role": "system", "content": EXTRA_SYSTEM_PROMPT},
        {"role": "user", "content": "Write the development briefing now."},
    ]
    # num_ctx 6144 covers a typical dev_check prompt: system ~700 + nta
    # doc + DOB body with 5 flagged projects ~3000 + RAG hits ~1000.
    # 12288 was over-allocating KV cache — costly on T4. num_predict caps
    # the briefing at ~600 tokens (4 sections + 5 bullet projects).
    OPTS = {"temperature": 0, "num_ctx": 6144, "num_predict": 600}
    if on_token is None:
        resp = llm.chat(model=OLLAMA_MODEL, messages=messages, options=OPTS)
        raw = resp["message"]["content"].strip()
    else:
        chunks: list[str] = []
        for chunk in llm.chat(model=OLLAMA_MODEL, messages=messages,
                                 stream=True, options=OPTS):
            delta = (chunk.get("message") or {}).get("content") or ""
            if delta:
                chunks.append(delta)
                on_token(delta)
        raw = "".join(chunks).strip()
    cleaned, dropped = verify_paragraph(raw, docs)
    return cleaned, {"raw": raw, "dropped": dropped}


def _empty(plan, query, trace, error):
    return {
        "intent":    "development_check",
        "query":     query,
        "error":     error,
        "plan":      {"intent": plan.intent, "targets": plan.targets,
                      "specialists": plan.specialists, "rationale": plan.rationale},
        "trace":     trace,
        "paragraph": f"Could not resolve target to an NTA: {error}",
    }
