"""50-query validation sweep against the live HF Space.

Usage:
    python3 scripts/probe_50.py [--base URL] [--concurrency N] [--timeout S]

Default base: https://lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space
"""

import argparse
import asyncio
import json
import time
from pathlib import Path
from urllib.parse import quote

import aiohttp

BASE = "https://lablab-ai-amd-developer-hackathon-riprap-nyc.hf.space"
QUERIES_FILE = Path("tests/queries_50.json")
RESULTS_FILE = Path("tests/probe_50_results.json")
CONCURRENCY = 3
TIMEOUT_S = 120

STEP_STONE_MAP = {
    "sandy_inundation": "sandy",
    "dep_stormwater": "dep",
    "nyc311": "311",
    "floodnet": "floodnet",
    "floodnet_forecast": "floodnet",
    "noaa_tides": "noaa",
    "nws_alerts": "nws",
    "nws_obs": "nws",
    "microtopo_lidar": "microtopo",
    "ida_hwm_2021": "ida",
    "ttm_forecast": "ttm",
    "ttm_battery_surge": "ttm",
    "ttm_311_forecast": "ttm",
    "prithvi_eo_v2": "prithvi_v2",
    "prithvi_eo_live": "prithvi_live",
    "gliner_extract": "gliner",
    "rag_granite_embedding": "rag",
    "mellea_reconcile_address": "mellea",
    "geocode": None,
    "mta_entrance_exposure": "mta",
    "terramind_synthesis": "terramind",
}


def _parse_sse(chunk: str):
    events = []
    event_type = "message"
    data_lines = []
    for line in chunk.splitlines():
        if line.startswith("event:"):
            event_type = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].strip())
        elif line == "" and data_lines:
            raw = " ".join(data_lines)
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"raw": raw}
            events.append((event_type, payload))
            event_type = "message"
            data_lines = []
    return events


async def stream_query(session: aiohttp.ClientSession, query_obj: dict, base: str, timeout_s: float) -> dict:
    qid = query_obj["id"]
    query = query_obj["query"]
    url = f"{base}/api/agent/stream?q={quote(query)}"

    result = {
        "id": qid,
        "query": query,
        "status": "ERROR",
        "wall_clock_s": None,
        "intent_returned": None,
        "mellea_passed": None,
        "mellea_rerolls": 0,
        "stones_fired": [],
        "stones_errored": [],
        "stones_silent": [],
        "citations_resolved": None,
        "compare_targets": None,
        "error": None,
    }

    t0 = time.monotonic()
    buf = ""
    plan_seen = False
    final_seen = False

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout_s + 10)) as resp:
            if resp.status != 200:
                result["error"] = f"HTTP {resp.status}"
                result["wall_clock_s"] = round(time.monotonic() - t0, 2)
                return result

            deadline = t0 + timeout_s
            async for chunk in resp.content.iter_any():
                if time.monotonic() > deadline:
                    result["status"] = "TIMEOUT"
                    result["wall_clock_s"] = round(time.monotonic() - t0, 2)
                    return result

                buf += chunk.decode("utf-8", errors="replace")
                # process complete SSE blocks (separated by double-newline)
                while "\n\n" in buf:
                    block, buf = buf.split("\n\n", 1)
                    for evt_type, payload in _parse_sse(block + "\n\n"):
                        if evt_type == "plan":
                            plan_seen = True
                            result["intent_returned"] = payload.get("intent")
                            targets = payload.get("targets", [])
                            if result["intent_returned"] == "compare":
                                result["compare_targets"] = len(targets)

                        elif evt_type == "step":
                            step = payload.get("step", "")
                            ok = payload.get("ok")
                            if step in STEP_STONE_MAP and STEP_STONE_MAP[step]:
                                stone = STEP_STONE_MAP[step]
                                if ok is True:
                                    if stone not in result["stones_fired"]:
                                        result["stones_fired"].append(stone)
                                elif ok is False:
                                    if stone not in result["stones_errored"]:
                                        result["stones_errored"].append(stone)

                        elif evt_type == "final":
                            final_seen = True
                            mellea = payload.get("mellea") or {}
                            req_passed = len(mellea.get("requirements_passed") or [])
                            req_total = mellea.get("requirements_total") or 4
                            result["mellea_passed"] = f"{req_passed}/{req_total}"
                            result["mellea_rerolls"] = (mellea.get("rerolls") or 0)
                            audit = payload.get("audit") or {}
                            result["citations_resolved"] = audit.get("citations_resolved")

                        elif evt_type == "error":
                            result["error"] = payload.get("err", "unknown error")

                        elif evt_type == "done":
                            result["wall_clock_s"] = round(time.monotonic() - t0, 2)
                            if final_seen:
                                result["status"] = "PASS"
                            else:
                                result["status"] = "ERROR"
                                if not result["error"]:
                                    result["error"] = "done without final event"
                            return result

    except asyncio.TimeoutError:
        result["status"] = "TIMEOUT"
    except Exception as exc:
        result["status"] = "ERROR"
        result["error"] = str(exc)

    result["wall_clock_s"] = round(time.monotonic() - t0, 2)
    return result


async def run_all(queries: list, base: str, timeout_s: float, concurrency: int) -> list:
    sem = asyncio.Semaphore(concurrency)
    results = []
    early_stop = False

    connector = aiohttp.TCPConnector(limit=concurrency + 2)
    async with aiohttp.ClientSession(connector=connector) as session:

        async def bounded(qobj):
            nonlocal early_stop
            if early_stop:
                return {**qobj, "status": "SKIPPED", "wall_clock_s": None, "error": "early stop"}
            async with sem:
                r = await stream_query(session, qobj, base, timeout_s)
                tag = f"[{r['id']}]"
                wc = f"{r['wall_clock_s']:.1f}s" if r["wall_clock_s"] else "?"
                mel = r.get("mellea_passed") or "-"
                rr = r.get("mellea_rerolls") or 0
                print(f"{tag} {r['status']} {wc} mellea={mel} rerolls={rr}", flush=True)
                return r

        tasks = [asyncio.create_task(bounded(q)) for q in queries]

        done_count = 0
        for coro in asyncio.as_completed(tasks):
            r = await coro
            results.append(r)
            done_count += 1
            # Check early-stop: >10 failures in first 20
            if done_count <= 20:
                bad = sum(1 for x in results if x["status"] in ("TIMEOUT", "ERROR"))
                if bad > 10:
                    print(f"\nEARLY STOP: {bad} failures in first {done_count} queries — Space appears degraded.", flush=True)
                    early_stop = True

    # Sort by original query order
    id_order = {q["id"]: i for i, q in enumerate(queries)}
    results.sort(key=lambda r: id_order.get(r["id"], 999))
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE)
    ap.add_argument("--concurrency", type=int, default=CONCURRENCY)
    ap.add_argument("--timeout", type=float, default=TIMEOUT_S)
    args = ap.parse_args()

    queries = json.loads(QUERIES_FILE.read_text())
    print(f"Running {len(queries)} queries against {args.base} (concurrency={args.concurrency}, timeout={args.timeout}s)\n", flush=True)

    results = asyncio.run(run_all(queries, args.base, args.timeout, args.concurrency))

    # Write results
    RESULTS_FILE.write_text(json.dumps(results, indent=2))
    print(f"\nResults written to {RESULTS_FILE}")

    # Update verified flags in queries file
    passed_ids = {r["id"] for r in results if r["status"] == "PASS"}
    for q in queries:
        if q["id"] in passed_ids:
            q["verified"] = True
    QUERIES_FILE.write_text(json.dumps(queries, indent=2))
    print(f"Updated verified flags in {QUERIES_FILE}")

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    timed_out = sum(1 for r in results if r["status"] == "TIMEOUT")
    errored = sum(1 for r in results if r["status"] == "ERROR")
    skipped = sum(1 for r in results if r["status"] == "SKIPPED")
    wall_clocks = [r["wall_clock_s"] for r in results if r["status"] == "PASS" and r["wall_clock_s"]]
    avg_wall = sum(wall_clocks) / len(wall_clocks) if wall_clocks else 0
    max_wall = max(wall_clocks) if wall_clocks else 0
    mellea_perfect = sum(1 for r in results if r.get("mellea_passed") == "4/4")

    print(f"\n{'='*60}")
    print(f"Total:          {total}")
    print(f"PASS:           {passed} ({100*passed//total if total else 0}%)")
    print(f"TIMEOUT:        {timed_out}")
    print(f"ERROR:          {errored}")
    if skipped:
        print(f"SKIPPED:        {skipped} (early stop)")
    print(f"Avg wall-clock: {avg_wall:.1f}s  (passing queries)")
    print(f"Max wall-clock: {max_wall:.1f}s")
    print(f"Mellea 4/4:     {mellea_perfect} ({100*mellea_perfect//total if total else 0}%)")

    failures = [r for r in results if r["status"] != "PASS"]
    if failures:
        print("\n--- FAILURES ---")
        for r in failures:
            print(f"  [{r['id']}] {r['status']} — {r['query'][:60]}")
            if r.get("error"):
                print(f"           err: {r['error'][:80]}")

    slowest = sorted([r for r in results if r.get("wall_clock_s")], key=lambda x: x["wall_clock_s"], reverse=True)[:5]
    print("\n--- SLOWEST 5 ---")
    for r in slowest:
        print(f"  [{r['id']}] {r['wall_clock_s']:.1f}s — {r['query'][:60]}")

    high_rr = [r for r in results if (r.get("mellea_rerolls") or 0) > 1]
    if high_rr:
        print("\n--- HIGH REROLLS (>1) ---")
        for r in high_rr:
            print(f"  [{r['id']}] rerolls={r['mellea_rerolls']} — {r['query'][:60]}")

    print(f"{'='*60}")


if __name__ == "__main__":
    main()
