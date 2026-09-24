from pathlib import Path
from types import SimpleNamespace

from pulse.plan.runner import run_plan
from pulse.plan.spec_flow import run_spec
from pulse.plan.spec_prompt import route_file


class _Stream:
    cockpit = True

    def __init__(self) -> None:
        self.routes: list[str] = []
        self.infos: list[str] = []
        self.errors: list[tuple[str, str]] = []

    def apply_routed_flow(self, flow: str) -> None:
        self.routes.append(flow)

    def info(self, title: str) -> None:
        self.infos.append(title)

    def error(self, title: str, reason: str = "") -> None:
        self.errors.append((title, reason))


class _Runner:
    summary = ""

    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def start(self) -> None:
        return None

    def initialize(self) -> None:
        return None

    def authenticate(self) -> None:
        return None

    def run_isolated_prompt(self, **_kwargs) -> dict[str, str]:
        return {"stopReason": "end_turn", "phaseSummary": self.summary}

    def close(self) -> None:
        return None


def _patch_classify(monkeypatch, tmp_path: Path, flow: str) -> None:
    monkeypatch.setattr("pulse.plan.spec_flow.is_interactive", lambda: False)
    monkeypatch.setattr("pulse.plan.spec_flow.check_runtime_ready", lambda _runtime: None)
    monkeypatch.setattr(
        "pulse.plan.spec_flow.resolve_config",
        lambda **_k: SimpleNamespace(
            workspace_dir=tmp_path,
            permission_policy="ask",
            acp_command=["agent", "acp"],
            model="auto",
        ),
    )
    monkeypatch.setattr("pulse.plan.spec_flow.cleanup_legacy_pulse_questions", lambda **_k: None)
    monkeypatch.setattr("pulse.plan.spec_flow.resolve_spec_skill", lambda: tmp_path)
    monkeypatch.setattr("pulse.plan.spec_flow.AcpSessionRunner", _Runner)
    path = route_file(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"flow: {flow}\nreason: teste\n", encoding="utf-8")


def test_run_spec_dispatches_quick(monkeypatch, tmp_path: Path):
    _patch_classify(monkeypatch, tmp_path, "quick")
    captured: dict[str, object] = {}

    def fake_quick(**kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr("pulse.plan.spec_flow.run_quick", fake_quick)
    monkeypatch.setattr("pulse.plan.spec_flow.run_new_issue", lambda **_k: 99)
    stream = _Stream()
    code = run_spec(
        user_prompt="Corrigir token",
        workspace=tmp_path,
        stream=stream,
        render_header=False,
    )
    assert code == 0
    assert captured["user_prompt"] == "Corrigir token"
    assert stream.routes == ["quick"]
    assert any("quick" in item for item in stream.infos)


def test_run_spec_dispatches_full(monkeypatch, tmp_path: Path):
    _patch_classify(monkeypatch, tmp_path, "full")
    captured: dict[str, object] = {}

    def fake_full(**kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr("pulse.plan.spec_flow.run_new_issue", fake_full)
    monkeypatch.setattr("pulse.plan.spec_flow.run_quick", lambda **_k: 99)
    code = run_spec(
        user_prompt="Login social",
        workspace=tmp_path,
        stream=_Stream(),
        render_header=False,
    )
    assert code == 0
    assert captured["user_prompt"] == "Login social"


def test_run_plan_spec_id(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("pulse.plan.runner.run_spec", lambda **_k: 7)
    assert run_plan(spec_type_id="spec", user_prompt="x", workspace=tmp_path) == 7


def test_run_spec_asks_when_route_missing(monkeypatch, tmp_path: Path):
    _patch_classify(monkeypatch, tmp_path, "quick")
    route_file(tmp_path).unlink()
    captured: dict[str, object] = {}

    class Handler:
        def select_choice(self, *_args, **_kwargs):
            return "full"

    def fake_full(**kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr("pulse.plan.spec_flow.run_new_issue", fake_full)
    code = run_spec(
        user_prompt="Algo ambíguo",
        workspace=tmp_path,
        stream=_Stream(),
        prompt_handler=Handler(),
        render_header=False,
    )
    assert code == 0
    assert captured["user_prompt"] == "Algo ambíguo"


def test_run_spec_uses_agent_summary_when_route_file_missing(monkeypatch, tmp_path: Path):
    _patch_classify(monkeypatch, tmp_path, "quick")
    route_file(tmp_path).unlink()
    _Runner.summary = "flow: full\nreason: feature grande\n"
    captured: dict[str, object] = {}

    def fake_full(**kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr("pulse.plan.spec_flow.run_new_issue", fake_full)
    monkeypatch.setattr("pulse.plan.spec_flow.run_quick", lambda **_k: 99)
    code = run_spec(
        user_prompt="Login social",
        workspace=tmp_path,
        stream=_Stream(),
        render_header=False,
    )
    _Runner.summary = ""
    assert code == 0
    assert captured["user_prompt"] == "Login social"


def test_run_spec_returns_error_when_route_missing(monkeypatch, tmp_path: Path):
    _patch_classify(monkeypatch, tmp_path, "quick")
    route_file(tmp_path).unlink()
    stream = _Stream()
    code = run_spec(
        user_prompt="Algo ambíguo",
        workspace=tmp_path,
        stream=stream,
        render_header=False,
    )
    assert code == 1
    assert stream.errors
    assert stream.errors[0][0] == "Classificação cancelada"
    assert "flow" in stream.errors[0][1]
