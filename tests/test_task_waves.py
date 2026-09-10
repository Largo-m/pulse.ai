from pathlib import Path

from pulse.plan.task_waves import (
    TaskSpec,
    Wave,
    build_waves,
    collect_wave_gate_commands,
    parse_task_specs,
    run_gate_command,
)


SAMPLE_TASKS_MD = """
# Feature Tasks

### T1: Configurar deps

**What**: pubspec
**Where**: `pubspec.yaml`
**Depends on**: None

**Done when**:

- [ ] `flutter pub get` executa sem erros

**Tests**: none
**Gate**: build

### T2: Criar enum

**What**: period
**Where**: `lib/a.dart`, `lib/b.dart`
**Depends on**: None

**Done when**:

- [ ] Gate check passes: `flutter analyze lib/features/home/`

**Tests**: unit
**Gate**: quick

### T3: Entities

**What**: entities
**Where**: `lib/entities/`
**Depends on**: None

**Done when**:

- [ ] Gate check passes: `flutter analyze lib/features/home/domain/`

### T4: Repository

**What**: interface
**Where**: `lib/repo.dart`
**Depends on**: T3

**Done when**:

- [ ] Gate check passes: `flutter analyze lib/features/home/domain/repository/`

### T5: Use case

**What**: get dashboard
**Where**: `lib/usecase.dart`
**Depends on**: T4

**Done when**:

- [ ] Gate check passes: `flutter test test/features/home/domain/usecase/get_dashboard_test.dart`

**Verify**:

```bash
flutter test test/features/home/domain/usecase/get_dashboard_test.dart
```

### T12: Bar chart [P]

**What**: chart
**Where**: `lib/ds_bar.dart`
**Depends on**: T1

**Done when**:

- [ ] Gate check passes: `flutter test test/ds_bar_chart_test.dart`

### T13: Donut chart [P]

**What**: chart
**Where**: `lib/ds_donut.dart`
**Depends on**: T1

**Done when**:

- [ ] Gate check passes: `flutter test test/ds_donut_chart_test.dart`

### T14: Docs

**What**: docs
**Where**: `docs/DESIGN_SYSTEM.md`
**Depends on**: T12, T13

**Done when**:

- [ ] Docs updated
"""


def test_parse_task_specs_extracts_deps_parallel_and_gates():
    specs = parse_task_specs(SAMPLE_TASKS_MD)
    by_id = {spec.task_id: spec for spec in specs}

    assert list(by_id) == ["T1", "T2", "T3", "T4", "T5", "T12", "T13", "T14"]
    assert by_id["T1"].depends_on == ()
    assert by_id["T4"].depends_on == ("T3",)
    assert by_id["T14"].depends_on == ("T12", "T13")
    assert by_id["T12"].parallel is True
    assert by_id["T13"].parallel is True
    assert by_id["T2"].parallel is False
    assert by_id["T2"].gate_commands == ("flutter analyze lib/features/home/",)
    assert by_id["T5"].gate_commands == (
        "flutter test test/features/home/domain/usecase/get_dashboard_test.dart",
    )


def test_build_waves_groups_ready_sequential_and_parallel():
    specs = parse_task_specs(SAMPLE_TASKS_MD)
    waves = build_waves(specs)

    assert [wave.task_ids for wave in waves] == [
        ["T1", "T2", "T3"],
        ["T4"],
        ["T5"],
        ["T12", "T13"],
        ["T14"],
    ]
    assert waves[0].parallel is False
    assert waves[3].parallel is True
    assert waves[4].parallel is False


def test_build_waves_respects_done_ids_and_max_size():
    specs = parse_task_specs(SAMPLE_TASKS_MD)
    waves = build_waves(specs, done_ids={"T1", "T2", "T3"}, max_wave_size=2)

    assert waves[0].task_ids == ["T4"]
    assert ["T12", "T13"] in [wave.task_ids for wave in waves]


def test_build_waves_breaks_on_max_wave_size():
    specs = [
        TaskSpec(task_id="T1", title="A"),
        TaskSpec(task_id="T2", title="B"),
        TaskSpec(task_id="T3", title="C"),
        TaskSpec(task_id="T4", title="D"),
    ]
    waves = build_waves(specs, max_wave_size=2)
    assert [wave.task_ids for wave in waves] == [["T1", "T2"], ["T3", "T4"]]


def test_collect_wave_gate_commands_dedupes():
    wave = Wave(
        wave_id=1,
        tasks=(
            TaskSpec(task_id="T1", title="A", gate_commands=("flutter analyze",)),
            TaskSpec(task_id="T2", title="B", gate_commands=("flutter analyze", "flutter test")),
        ),
    )
    assert collect_wave_gate_commands(wave) == ["flutter analyze", "flutter test"]


def test_run_gate_command_success(tmp_path: Path):
    result = run_gate_command(workspace=tmp_path, command="true")
    assert result.ok is True
    assert result.exit_code == 0


def test_run_gate_command_failure(tmp_path: Path):
    result = run_gate_command(workspace=tmp_path, command="false")
    assert result.ok is False
    assert result.exit_code != 0


def test_verify_prose_does_not_pollute_gate_command():
    content = """
### T1: Deps

**Depends on**: None

**Done when**:

- [ ] fl_chart declared

**Verify**:
`flutter pub get` exit 0; pacote listado em `.dart_tool/package_config.json`.

### T2: Period

**Depends on**: None

**Done when**:

- [ ] Gate check passes: `flutter test test/features/home/domain/entities/dashboard_period_test.dart`

**Verify**:
Testes cobrem `apiValue` e `fromApi`.

### T3: Widget

**Depends on**: None

**Verify**:
`dart analyze` no arquivo sem issues.
"""
    specs = parse_task_specs(content)
    by_id = {spec.task_id: spec for spec in specs}
    assert by_id["T1"].gate_commands == ("flutter pub get",)
    assert by_id["T2"].gate_commands == (
        "flutter test test/features/home/domain/entities/dashboard_period_test.dart",
    )
    assert by_id["T3"].gate_commands == ()


def test_run_execute_phase_continues_all_waves(monkeypatch, tmp_path: Path):
    from rich.console import Console

    from pulse.plan import new_issue_flow
    from pulse.plan.specify_state import TaskState, WorkflowState
    from pulse.plan.task_waves import GateResult

    state = WorkflowState.create_new(feature_slug="feat", user_prompt="x")
    state.tasks = [
        TaskState(task_id="T1", title="One"),
        TaskState(task_id="T2", title="Two"),
        TaskState(task_id="T3", title="Three"),
    ]
    state.save(tmp_path)

    feature = tmp_path / state.feature_dir
    feature.mkdir(parents=True, exist_ok=True)
    (feature / "tasks.md").write_text(
        """
### T1: One

**Depends on**: None

### T2: Two

**Depends on**: None

### T3: Three

**Depends on**: T1
""",
        encoding="utf-8",
    )

    calls: list[str] = []

    class FakeRunner:
        _stream = None

        def run_isolated_prompt(self, **kwargs):
            calls.append(str(kwargs.get("phase_label") or ""))
            return {"stopReason": "end_turn"}

    monkeypatch.setattr(
        new_issue_flow,
        "run_wave_gates",
        lambda **_kwargs: [GateResult(ok=True, command="true", exit_code=0)],
    )

    code = new_issue_flow._run_execute_phase(
        runner=FakeRunner(),
        console=Console(force_terminal=False),
        workspace=tmp_path,
        user_prompt="x",
        skill_dir=tmp_path,
        state=state,
        preferred_model=None,
    )
    assert code == 0
    assert len(calls) >= 2
    assert all(label.startswith("Execute — Wave") for label in calls)
    assert {task.status for task in state.tasks} == {"done"}
