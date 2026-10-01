"""O histórico tem que mostrar o mesmo que a sessão viva mostrou.

O log gravado passa pelos mesmos rótulos do cockpit
([pulse.history.tool_detail.build_tool_labels]), e a releitura devolve cada linha ao
tipo dela. Enquanto o banco guardava `kind="Tool"` com o `title` cru do ACP, uma
run reaberta virava uma fileira de "v Tool" sem dizer o que o agente leu,
rodou ou escreveu.

O diálogo segue a mesma regra: toda pergunta feita à pessoa passa pelo proxy do
prompt port e vira os balões `Pergunta`/`Você`
([pulse.history.prompt_detail.build_prompt_qa]). Sem isso, o questionário que
decidiu o rumo da run sumia ao reabri-la — ele só existia na tela.
"""

from __future__ import annotations

from pathlib import Path

from tests.conftest import make_workflow

from pulse.acp.session_runner import AcpSessionRunner
from pulse.history.events import LogKind
from pulse.history.models import HistoryItem, HistoryStatus, HistoryStep
from pulse.prompts.ask_question import build_ask_question_answers
from pulse.prompts.permission import permission_selected
from pulse.prompts.text_questionnaire import (
    QUESTIONNAIRE_NOTICE,
    format_questionnaire_answers,
    parse_text_questionnaire,
)
from pulse.store import runs as run_store
from pulse.store.runs import StepRecord
from pulse.tui.hydrate import hydrate_history_item


def _runner(
    workspace: Path,
    run_id: str = "run-1",
    step_id: str = "plan",
    port: object | None = None,
) -> AcpSessionRunner:
    runner = AcpSessionRunner(
        ["agent", "acp"],
        cwd=str(workspace),
        enable_mcp_ask=False,
        prompt_handler=port,
    )
    runner.bind_run(run_id)
    runner._phase_id = step_id
    return runner


def _run(workspace: Path, run_id: str = "run-1") -> str:
    make_workflow("demo", steps=[("plan", "Planejar")])
    record = run_store.create_run(
        run_id=run_id,
        workflow_id="demo",
        workspace=workspace,
        user_prompt="fazer algo",
        steps=[StepRecord(step_id="plan", position=1, label="Planejar")],
    )
    return record.id


def _update(**fields) -> dict:
    return {"update": {"sessionUpdate": "tool_call", "toolCallId": "t-1", **fields}}


def _hydrated(workspace: Path, run_id: str = "run-1"):
    item = HistoryItem(
        run_id=run_id,
        workflow_id="demo",
        workflow_label="Demo",
        title="demo",
        prompt="fazer algo",
        status=HistoryStatus.DONE,
        updated_at="2026-09-30T10:00:00+00:00",
        steps=[HistoryStep(id="plan", label="Planejar", status="done")],
    )
    return hydrate_history_item(item, workspace)


def test_cada_tool_guarda_o_tipo_que_a_tela_mostrou(tmp_path: Path):
    run_id = _run(tmp_path)
    runner = _runner(tmp_path, run_id)

    runner._record_run_event(
        _update(title="Read File", kind="read", rawInput={"path": str(tmp_path / "a.py")})
    )
    runner._record_run_event(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "t-2",
                "title": "Shell",
                "kind": "execute",
                "rawInput": {"command": "pytest -q"},
            }
        }
    )

    events = run_store.list_events(run_id)
    assert [(event["kind"], event["title"]) for event in events] == [
        ("Read", "a.py"),
        ("Shell", "pytest -q"),
    ]


def test_o_historico_reabre_com_os_tipos_em_vez_de_tool_generico(tmp_path: Path):
    run_id = _run(tmp_path)
    runner = _runner(tmp_path, run_id)
    runner._record_run_event(
        _update(title="Read File", kind="read", rawInput={"path": str(tmp_path / "a.py")})
    )

    state = _hydrated(tmp_path, run_id)

    assert [(entry.kind, entry.title) for entry in state.entries] == [
        (LogKind.READ, "a.py")
    ]


def test_a_fala_do_agente_volta_inteira_no_balao(tmp_path: Path):
    run_id = _run(tmp_path)
    runner = _runner(tmp_path, run_id)
    fala = "linha um. " * 400  # bem além do antigo teto de 2000 caracteres

    runner._text_buffer.append(fala)
    runner._flush_text()

    state = _hydrated(tmp_path, run_id)
    entry = state.entries[0]
    assert entry.kind == LogKind.ASSISTANT
    assert entry.body == fala.strip()


def test_o_cabecalho_do_passo_fica_no_log(tmp_path: Path):
    run_id = _run(tmp_path)
    runner = _runner(tmp_path, run_id)

    runner._begin_phase("Planejar")

    state = _hydrated(tmp_path, run_id)
    assert [(entry.kind, entry.title) for entry in state.entries] == [
        (LogKind.INFO, "Planejar")
    ]


def test_um_update_tardio_nao_apaga_o_rotulo_do_tool(tmp_path: Path):
    """O `rawOutput` chega noutro evento; a linha já tinha o arquivo."""
    run_id = _run(tmp_path)
    runner = _runner(tmp_path, run_id)

    runner._record_run_event(
        _update(title="Write File", kind="write", rawInput={"path": str(tmp_path / "PRD.md")})
    )
    runner._record_run_event(
        {
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": "t-1",
                "status": "completed",
            }
        }
    )

    events = run_store.list_events(run_id)
    assert [(event["kind"], event["title"]) for event in events] == [("Write", "PRD.md")]


# --------------------------------------------------------------------------- #
# O diálogo
# --------------------------------------------------------------------------- #


def _dialogue(run_id: str) -> list[tuple[str, str]]:
    """As linhas de pergunta/resposta do log, na ordem."""
    return [
        (event["kind"], event["detail"])
        for event in run_store.list_events(run_id)
        if event["kind"] in {"Question", "Answer"}
    ]


def test_a_pergunta_do_agente_e_a_resposta_ficam_no_log(tmp_path: Path):
    """O `AskQuestion` é onde a pessoa decide o rumo da run — some do histórico
    e o que sobra é a fala do agente sem o porquê dela."""
    run_id = _run(tmp_path)

    class _Port:
        def respond_to_ask_question(self, params):
            return build_ask_question_answers(
                [{"questionId": "q1", "selectedOptionIds": ["B"]}]
            )

    runner = _runner(tmp_path, run_id, port=_Port())
    runner._prompt_handler.respond_to_ask_question(
        {
            "questions": [
                {
                    "id": "q1",
                    "prompt": "1. O que você está construindo?",
                    "options": [
                        {"id": "A", "label": "Produto / plataforma"},
                        {"id": "B", "label": "API / serviço backend"},
                    ],
                }
            ]
        }
    )

    assert _dialogue(run_id) == [
        ("Question", "1. O que você está construindo?"),
        # O mesmo rótulo numerado que o dock mostrou, não o id cru.
        ("Answer", "B) API / serviço backend"),
    ]


def test_o_que_a_pessoa_escreveu_em_outro_entra_na_resposta(tmp_path: Path):
    run_id = _run(tmp_path)

    class _Port:
        def respond_to_ask_question(self, params):
            return build_ask_question_answers(
                [{"questionId": "q1", "selectedOptionIds": ["B::Falta o acesso ao banco"]}]
            )

    runner = _runner(tmp_path, run_id, port=_Port())
    runner._prompt_handler.respond_to_ask_question(
        {
            "questions": [
                {
                    "id": "q1",
                    "prompt": "1. Aprovar a Techspec e avançar?",
                    "options": [
                        {"id": "A", "label": "Sim, aprovar"},
                        {"id": "B", "label": "Não, preciso de ajustes (descreva)"},
                    ],
                }
            ]
        }
    )

    assert _dialogue(run_id)[1] == (
        "Answer",
        "B) Não, preciso de ajustes (descreva) — Falta o acesso ao banco",
    )


def test_o_questionario_em_texto_vira_um_par_por_pergunta(tmp_path: Path):
    run_id = _run(tmp_path)
    questionnaire = parse_text_questionnaire(
        "Preciso de algumas informações antes de continuar.\n"
        "1. O que você está construindo?\n"
        "A) Produto\n"
        "B) Biblioteca\n"
        "2. Quem usa?\n"
        "A) Time interno\n"
        "B) Cliente final\n"
    )

    class _Port:
        def run_parsed_questionnaire(self, parsed):
            return format_questionnaire_answers(
                parsed,
                [
                    (parsed.questions[0], "A) Produto"),
                    (parsed.questions[1], "B) Cliente final"),
                ],
            )

    runner = _runner(tmp_path, run_id, port=_Port())
    runner._prompt_handler.run_parsed_questionnaire(questionnaire)

    assert _dialogue(run_id) == [
        ("Question", "1. O que você está construindo?"),
        ("Answer", "A) Produto"),
        ("Question", "2. Quem usa?"),
        ("Answer", "B) Cliente final"),
    ]


def _permission_params(kind: str = "edit") -> dict:
    return {
        "permission": {"title": "Editar app.py", "kind": kind},
        "toolCall": {"kind": kind, "title": "Write app.py"},
        "options": [
            {"optionId": "allow-once", "kind": "allow_once"},
            {"optionId": "reject-once", "kind": "reject_once"},
        ],
    }


def test_a_permissao_que_a_politica_resolve_nao_vira_linha(tmp_path: Path):
    """Regra não é pergunta: ninguém viu essa decisão, então ela não é diálogo."""
    run_id = _run(tmp_path)

    class _Port:
        def respond_to_permission(self, params, *, policy, allow_terminal=False):
            return permission_selected("allow-once")

    runner = _runner(tmp_path, run_id, port=_Port())
    runner._prompt_handler.respond_to_permission(
        _permission_params(), policy="auto_approve"
    )

    assert _dialogue(run_id) == []


def test_a_permissao_que_a_pessoa_decidiu_fica_no_log(tmp_path: Path):
    run_id = _run(tmp_path)

    class _Port:
        def respond_to_permission(self, params, *, policy, allow_terminal=False):
            return permission_selected("reject-once")

    runner = _runner(tmp_path, run_id, port=_Port())
    runner._prompt_handler.respond_to_permission(_permission_params(), policy="ask")

    assert _dialogue(run_id) == [
        ("Question", "Editar app.py\nWrite app.py"),
        ("Answer", "B) Recusar"),
    ]


def test_o_menu_de_retry_e_a_orientacao_ficam_no_log(tmp_path: Path):
    """O que o motor pergunta quando um step cai também é decisão da pessoa."""
    run_id = _run(tmp_path)

    class _Port:
        def select_choice(self, prompt, choices, *, title=""):
            return "guidance"

        def ask_text(self, prompt, *, title=""):
            return "Usar o endpoint novo"

    runner = _runner(tmp_path, run_id, port=_Port())
    runner._prompt_handler.select_choice(
        "o step quebrou",
        [("Refazer", "retry"), ("Outro — dizer o que fazer", "guidance")],
        title="Planejar",
    )
    runner._prompt_handler.ask_text("O que o agente deve fazer nesta nova tentativa?")

    assert _dialogue(run_id) == [
        ("Question", "o step quebrou"),
        ("Answer", "Outro — dizer o que fazer"),
        ("Question", "O que o agente deve fazer nesta nova tentativa?"),
        ("Answer", "Usar o endpoint novo"),
    ]


def test_o_bloco_do_questionario_nao_volta_como_fala_do_agente(tmp_path: Path):
    """Ao vivo o bloco vira dock; gravá-lo cru mostraria as perguntas duas vezes."""
    run_id = _run(tmp_path)
    runner = _runner(tmp_path, run_id)

    runner._text_buffer.append(
        "Antes de começar preciso entender o escopo.\n\n"
        "Preciso de algumas informações antes de continuar.\n"
        "1. O que você está construindo?\n"
        "A) Produto\n"
        "B) Biblioteca\n"
    )
    runner._flush_text()

    events = [(event["kind"], event["title"]) for event in run_store.list_events(run_id)]
    assert events == [
        ("Assistant", "Antes de começar preciso entender o escopo."),
        ("Info", QUESTIONNAIRE_NOTICE),
    ]


def test_o_historico_reabre_com_os_baloes_de_pergunta_e_resposta(tmp_path: Path):
    run_id = _run(tmp_path)

    class _Port:
        def ask_text(self, prompt, *, title=""):
            return "Começar pelo cadastro"

    runner = _runner(tmp_path, run_id, port=_Port())
    runner._prompt_handler.ask_text("Por onde começar?")

    state = _hydrated(tmp_path, run_id)
    assert [(entry.kind, entry.title, entry.body) for entry in state.entries] == [
        (LogKind.QUESTION, "Pergunta", "Por onde começar?"),
        (LogKind.ANSWER, "Você", "Começar pelo cadastro"),
    ]


def test_artefato_sai_do_tool_mesmo_sem_kind_do_acp(tmp_path: Path):
    """Runtime que só manda o nome do tool também rende artefato.

    A aba de artefatos do histórico vinha vazia porque o registro dependia do
    campo `kind` do ACP, que nem todo runtime preenche.
    """
    run_id = _run(tmp_path)
    runner = _runner(tmp_path, run_id)
    (tmp_path / "PRD.md").write_text("# PRD\n", encoding="utf-8")

    runner._record_run_event(
        _update(title="Write", toolName="write_file", rawInput={"path": str(tmp_path / "PRD.md")})
    )

    assert [item["path"] for item in run_store.list_artifacts(run_id)] == ["PRD.md"]

    state = _hydrated(tmp_path, run_id)
    assert [(item.path, item.has_content) for item in state.artifacts] == [("PRD.md", True)]
    assert state.phase_has_artifacts(), "a aba precisa abrir para o artefato da run"
