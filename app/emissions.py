"""Per-query emissions tracker for inference calls.

Records every LLM and ML-inference call made during a single query and
summarizes:
  - wallclock duration per call
  - prompt + completion tokens (LLM)
  - estimated energy in watt-hours, using a sustained-power figure for
    the active hardware

Estimates are deliberately rule-of-thumb: hardware × time. The numbers
are conservative public-record figures (data sheet TDP scaled to a
sustained-inference fraction). They are not benchmark output. The intent
is a defensible, auditable footprint the UI can surface alongside the
existing `energy` block.

Thread propagation
------------------
The tracker is held in a thread-local. The dispatch layer
(web/main.py) installs one per request; `app/fsm.py:iter_steps`
captures and re-installs it on the FSM runner thread (mirroring the
existing `_captured_token_cb` pattern). Worker threads spawned inside
specialists (prithvi_live, eo_chip_cache) inherit nothing — those calls
are silently dropped, which is acceptable: those specialists do <1 s of
inference each and are off the hot path for the energy story.
"""
from __future__ import annotations

import threading
from typing import Any

# (label, sustained_power_w, source)
HARDWARE: dict[str, tuple[str, float, str]] = {
    "amd_mi300x": (
        "AMD MI300X",
        600.0,
        "AMD Instinct MI300X data sheet (750 W TDP); ~600 W sustained "
        "during vLLM generation is a conservative midpoint of public "
        "ROCm benchmarks.",
    ),
    "nvidia_t4": (
        "NVIDIA T4",
        50.0,
        "NVIDIA T4 data sheet (70 W max); ~50 W sustained during "
        "transformer inference.",
    ),
    "apple_m": (
        "Apple M-series",
        20.0,
        "ml.energy / community measurements: ~20 W package power "
        "during Granite 4.1 q4_K_M inference on Apple M3/M4.",
    ),
    "cpu_server": (
        "x86 CPU",
        30.0,
        "Typical sustained x86 server-core load (~30 W) for CPU-only "
        "inference fallbacks.",
    ),
}

# Frontier-cloud per-query reference, kept in sync with app/energy.py so
# the comparison stays consistent across both summaries.
CLOUD_PER_QUERY_WH = 0.30
CLOUD_SOURCE = (
    'Epoch AI (2025), "How much energy does ChatGPT use?", '
    "estimating ~0.3 Wh per typical GPT-4o query."
)


def _wh(power_w: float, duration_s: float) -> float:
    return power_w * max(duration_s, 0.0) / 3600.0


class Tracker:
    """Append-only call ledger for one query. Thread-safe."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def record_llm(self, *, model: str, backend: str, hardware: str,
                   prompt_tokens: int | None,
                   completion_tokens: int | None,
                   duration_s: float,
                   stream: bool = False) -> None:
        hw_label, power_w, _src = HARDWARE.get(hardware,
                                               HARDWARE["cpu_server"])
        wh = _wh(power_w, duration_s)
        total = None
        if prompt_tokens is not None or completion_tokens is not None:
            total = (prompt_tokens or 0) + (completion_tokens or 0)
        with self._lock:
            self.calls.append({
                "kind": "llm",
                "model": model,
                "backend": backend,
                "hardware": hardware,
                "hardware_label": hw_label,
                "power_w": power_w,
                "duration_s": round(duration_s, 3),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total,
                "stream": stream,
                "wh": round(wh, 5),
                "joules": round(wh * 3600, 2),
            })

    def record_ml(self, *, endpoint: str, backend: str, hardware: str,
                  duration_s: float) -> None:
        hw_label, power_w, _src = HARDWARE.get(hardware,
                                               HARDWARE["cpu_server"])
        wh = _wh(power_w, duration_s)
        with self._lock:
            self.calls.append({
                "kind": "ml",
                "endpoint": endpoint,
                "backend": backend,
                "hardware": hardware,
                "hardware_label": hw_label,
                "power_w": power_w,
                "duration_s": round(duration_s, 3),
                "wh": round(wh, 5),
                "joules": round(wh * 3600, 2),
            })

    def summarize(self) -> dict[str, Any]:
        with self._lock:
            calls = list(self.calls)
        total_wh = sum(c["wh"] for c in calls)
        total_dur = sum(c["duration_s"] for c in calls)
        prompt = sum((c.get("prompt_tokens") or 0)
                     for c in calls if c["kind"] == "llm")
        completion = sum((c.get("completion_tokens") or 0)
                         for c in calls if c["kind"] == "llm")

        by_kind: dict[str, dict[str, Any]] = {}
        for c in calls:
            slot = by_kind.setdefault(c["kind"], {"wh": 0.0, "n": 0,
                                                  "duration_s": 0.0})
            slot["wh"] += c["wh"]
            slot["n"] += 1
            slot["duration_s"] += c["duration_s"]
        for slot in by_kind.values():
            slot["wh"] = round(slot["wh"], 5)
            slot["mwh"] = round(slot["wh"] * 1000, 2)
            slot["duration_s"] = round(slot["duration_s"], 3)

        by_hw: dict[str, dict[str, Any]] = {}
        for c in calls:
            slot = by_hw.setdefault(c["hardware"], {
                "label": c["hardware_label"],
                "power_w": c["power_w"],
                "wh": 0.0, "n": 0, "duration_s": 0.0,
            })
            slot["wh"] += c["wh"]
            slot["n"] += 1
            slot["duration_s"] += c["duration_s"]
        for slot in by_hw.values():
            slot["wh"] = round(slot["wh"], 5)
            slot["mwh"] = round(slot["wh"] * 1000, 2)
            slot["duration_s"] = round(slot["duration_s"], 3)

        ratio = (round(CLOUD_PER_QUERY_WH / total_wh, 1)
                 if total_wh > 0 else None)
        return {
            "n_calls": len(calls),
            "total_wh": round(total_wh, 5),
            "total_mwh": round(total_wh * 1000, 2),
            "total_joules": round(total_wh * 3600, 1),
            "total_duration_s": round(total_dur, 3),
            "tokens": {
                "prompt": prompt or None,
                "completion": completion or None,
                "total": (prompt + completion) or None,
            },
            "by_kind": by_kind,
            "by_hardware": by_hw,
            "calls": calls,
            "comparison": {
                "cloud_per_query_wh": CLOUD_PER_QUERY_WH,
                "cloud_per_query_mwh": round(CLOUD_PER_QUERY_WH * 1000, 1),
                "ratio_cloud_over_query": ratio,
                "cloud_source": CLOUD_SOURCE,
            },
            "method": (
                "Sum over recorded inference calls of "
                "(sustained_power_w × duration_s ÷ 3600). "
                "Power figures are conservative public-record values "
                "per app/emissions.HARDWARE; tokens are reported by "
                "the backend (LiteLLM usage) when available, else "
                "estimated from response text length (~4 chars/token)."
            ),
        }


# Thread-local install. Calls made on threads without an installed
# tracker hit a no-op stub — always safe to call active().record_*().
_tl = threading.local()


class _NullTracker:
    def record_llm(self, **_kw: Any) -> None:
        return None

    def record_ml(self, **_kw: Any) -> None:
        return None


_NULL = _NullTracker()


def install(tracker: Tracker | None) -> None:
    _tl.tracker = tracker


def current() -> Tracker | None:
    return getattr(_tl, "tracker", None)


def active() -> Tracker | _NullTracker:
    """Return the installed tracker for this thread, or a no-op stub.
    Always safe to call in instrumentation hot paths."""
    return getattr(_tl, "tracker", None) or _NULL


def estimate_completion_tokens(text: str) -> int:
    """Rough char/4 estimator used when the backend doesn't report usage
    (e.g. streaming through Ollama, where LiteLLM's stream wrapper does
    not always surface a final usage block)."""
    return max(1, len(text) // 4)
