"""Per-query emissions tracker for inference calls.

Records every LLM and ML-inference call made during a single query and
summarizes:
  - wallclock duration per call
  - prompt + completion tokens (LLM)
  - energy in watt-hours, **measured from the L4 GPU when available**
    (the inference proxy reports per-call `X-GPU-Power-W` /
    `X-GPU-Energy-J` headers from a 100 ms-cadence NVML sampler).
    Falls back to a duration × data-sheet-power estimate when the
    proxy is unreachable / NVML init failed / call went to a backend
    that doesn't surface power readings.

Each call record carries a `measured: bool` flag indicating which path
was used, so the UI can disclose. `summarize()` aggregates total Wh,
total tokens, by-kind and by-hardware splits — no cloud comparison.

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

# (label, fallback_sustained_power_w, source). Used only when the
# proxy doesn't surface a real measurement (NVML disabled, backend
# unreachable, local-fallback path). The fallback figure is a
# conservative public-record estimate; the `measured: bool` flag on
# each call record indicates whether the row used the fallback.
HARDWARE: dict[str, tuple[str, float, str]] = {
    "nvidia_l4": (
        "NVIDIA L4",
        60.0,
        "NVIDIA L4 Tensor Core GPU data sheet (72 W TGP, Ada Lovelace, "
        "24 GB); ~60 W sustained during transformer inference. The "
        "active backend for the Riprap inference Space "
        "(msradam/riprap-vllm). When the proxy is reachable and NVML "
        "is initialized, real per-call power is read off the device "
        "via nvmlDeviceGetPowerUsage and this fallback is unused.",
    ),
    "amd_mi300x": (
        "AMD MI300X",
        600.0,
        "AMD Instinct MI300X data sheet (750 W TDP); ~600 W sustained "
        "during vLLM generation. Selected only when an operator deploys "
        "against an MI300X droplet and sets RIPRAP_HARDWARE_LABEL=AMD "
        "MI300X explicitly. The hackathon submission used to run on "
        "this hardware; the droplet was decommissioned 2026-05-06.",
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
        "during Granite 4.1 q4_K_M inference on Apple M3/M4 (the "
        "local-dev path, no remote backend configured).",
    ),
    "cpu_server": (
        "x86 CPU",
        30.0,
        "Typical sustained x86 server-core load (~30 W) for CPU-only "
        "inference fallbacks.",
    ),
}


def _wh(power_w: float, duration_s: float) -> float:
    return power_w * max(duration_s, 0.0) / 3600.0


class Tracker:
    """Append-only call ledger for one query. Thread-safe."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def _record(self, *, base: dict[str, Any], hardware: str,
                duration_s: float,
                joules_real: float | None,
                power_w_real: float | None) -> None:
        """Shared body of record_llm / record_ml.

        When `joules_real` is provided (NVML-derived from the proxy),
        we use it directly and stamp `measured=True`. Otherwise we
        fall back to the data-sheet sustained-power estimate.
        """
        hw_label, fallback_w, _src = HARDWARE.get(hardware,
                                                  HARDWARE["cpu_server"])
        if joules_real is not None and joules_real >= 0:
            joules = float(joules_real)
            wh = joules / 3600.0
            measured = True
            avg_w = (joules / duration_s) if duration_s > 0 else (
                power_w_real if power_w_real is not None else fallback_w)
        else:
            avg_w = fallback_w
            wh = _wh(avg_w, duration_s)
            joules = wh * 3600.0
            measured = False
        record = {
            **base,
            "hardware": hardware,
            "hardware_label": hw_label,
            "power_w": round(avg_w, 2),
            "duration_s": round(duration_s, 3),
            "measured": measured,
            "wh": round(wh, 5),
            "joules": round(joules, 3),
        }
        with self._lock:
            self.calls.append(record)

    def record_llm(self, *, model: str, backend: str, hardware: str,
                   prompt_tokens: int | None,
                   completion_tokens: int | None,
                   duration_s: float,
                   stream: bool = False,
                   joules_real: float | None = None,
                   power_w_real: float | None = None) -> None:
        total = None
        if prompt_tokens is not None or completion_tokens is not None:
            total = (prompt_tokens or 0) + (completion_tokens or 0)
        self._record(
            base={
                "kind": "llm",
                "model": model,
                "backend": backend,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total,
                "stream": stream,
            },
            hardware=hardware,
            duration_s=duration_s,
            joules_real=joules_real,
            power_w_real=power_w_real,
        )

    def record_ml(self, *, endpoint: str, backend: str, hardware: str,
                  duration_s: float,
                  joules_real: float | None = None,
                  power_w_real: float | None = None) -> None:
        self._record(
            base={
                "kind": "ml",
                "endpoint": endpoint,
                "backend": backend,
            },
            hardware=hardware,
            duration_s=duration_s,
            joules_real=joules_real,
            power_w_real=power_w_real,
        )

    def summarize(self) -> dict[str, Any]:
        with self._lock:
            calls = list(self.calls)
        total_wh = sum(c["wh"] for c in calls)
        total_dur = sum(c["duration_s"] for c in calls)
        n_measured = sum(1 for c in calls if c.get("measured"))
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
                "wh": 0.0, "n": 0, "duration_s": 0.0,
            })
            slot["wh"] += c["wh"]
            slot["n"] += 1
            slot["duration_s"] += c["duration_s"]
        for slot in by_hw.values():
            slot["wh"] = round(slot["wh"], 5)
            slot["mwh"] = round(slot["wh"] * 1000, 2)
            slot["duration_s"] = round(slot["duration_s"], 3)

        return {
            "n_calls": len(calls),
            "n_measured": n_measured,
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
            "method": (
                "Energy is read off the L4 GPU per call via "
                "nvmlDeviceGetPowerUsage on the inference proxy "
                "(X-GPU-Energy-J response header). Calls flagged "
                "measured=false fall back to "
                "(data-sheet sustained_power_w × duration_s ÷ 3600) "
                "— see app/emissions.HARDWARE for sources. Tokens "
                "are reported by the backend (LiteLLM usage) when "
                "available, else estimated from response text length "
                "(~4 chars/token)."
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
