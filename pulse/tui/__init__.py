from __future__ import annotations

__all__ = ["PulseApp", "run_pulse_app"]


def __getattr__(name: str) -> object:
    if name in {"PulseApp", "run_pulse_app"}:
        from pulse.tui.app import PulseApp, run_pulse_app

        return {"PulseApp": PulseApp, "run_pulse_app": run_pulse_app}[name]
    raise AttributeError(name)
