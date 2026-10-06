"""As definições que o Pulse sabe rodar — nenhuma delas vem de arquivo."""

from __future__ import annotations

from pathlib import Path

from pulse.store.workflow_defs import (
    AgentDef,
    StepDef,
    WorkflowDef,
    delete_workflow,
    get_agent,
    get_workflow,
    list_workflows,
    save_agent,
    save_workflow,
)


def test_a_fresh_database_already_has_the_factory_loops():
    """A config de fábrica é semente do banco, não catálogo em código."""
    workflows = {item.id: item for item in list_workflows()}

    assert set(workflows) >= {
        "default",
        "new-issue",
        "quick-fix",
        "review",
        "setup-project",
        "analyze-codebase",
    }
    assert workflows["default"].is_default is True
    assert workflows["default"].steps[0].prompt_template == "{{user_prompt}}"
    assert [step.step_id for step in workflows["new-issue"].steps] == [
        "prd",
        "techspec",
        "tasks",
        "implement",
        "review",
        "review-fix",
    ]
    # O último step de um pipeline executa: não há o que aprovar depois dele.
    assert [step.requires_approval for step in workflows["new-issue"].steps] == [
        True,
        True,
        True,
        False,
        True,
        False,
    ]
    assert get_agent("prd") is not None


def test_the_review_loop_runs_outside_the_spec_pipeline():
    """Mesmos agentes do "Nova spec", outra fase: aqui não há PRD nem tasks."""
    review = get_workflow("review")

    assert review is not None
    assert review.default_prompt, "revisa a branch atual — não há o que perguntar"
    assert [step.agent_id for step in review.steps] == ["review", "review-fix"]
    assert [step.requires_approval for step in review.steps] == [True, False]
    fix = review.steps[1]
    assert (fix.repeat_from, fix.repeat_max) == ("review", 3)
    for step in review.steps:
        assert ".pulse/reviews/" in step.prompt_template
        assert "<slug>/reviews/" not in step.prompt_template


def test_every_factory_step_renders_with_what_the_engine_offers():
    """Placeholder sem valor é `TemplateError` em run — e não em produção."""
    from pulse.prompts.render import render

    context = dict.fromkeys(
        (
            "user_prompt",
            "workspace",
            "workflow_id",
            "run_id",
            "step_id",
            "step_label",
            "previous_summary",
            "previous_status",
            "artifacts",
        ),
        "x",
    )
    # Primeiro step de uma run: não há resumo anterior nem artefato ainda.
    first_step = dict(context, previous_summary="", previous_status="", artifacts="")

    for workflow in list_workflows():
        for step in workflow.steps:
            render(step.prompt_template, context)
            render(step.prompt_template, first_step)


def test_factory_agents_carry_their_playbook_and_defer_on_runtime():
    prd = get_agent("prd")

    assert prd is not None
    assert "Ambiguity Ledger" in prd.instructions
    assert prd.permission_policy == "deny_writes"
    # Runtime/model de fábrica congelariam a escolha feita no `pulse init`.
    assert (prd.runtime, prd.model) == ("", "")


def test_the_default_agent_defers_to_the_machine():
    """Campo vazio = "use o padrão"; um runtime fixo congelaria o `pulse init`."""
    agent = get_agent("default")

    assert agent is not None
    assert agent.runtime == ""
    assert agent.model == ""


def test_domain_markdown_lives_only_in_the_factory_seed():
    """O `.md` de domínio é semente, não catálogo: só `store/factory` o carrega.

    O que o refactor proíbe é o motor conhecer fase por nome. Um `.md` que vira
    linha do banco uma vez e nunca mais é lido não reintroduz isso — mas um
    `.md` lido em run reintroduziria, então a fronteira é testada.
    """
    package = Path(__file__).resolve().parent.parent / "pulse"
    seed_dir = package / "store" / "factory"
    leftovers = [
        path.relative_to(package)
        for path in package.rglob("*")
        if path.is_file()
        and path.suffix != ".py"
        and "__pycache__" not in path.parts
        and seed_dir not in path.parents
    ]

    assert leftovers == []

    readers = [
        path.relative_to(package)
        for path in package.rglob("*.py")
        if seed_dir not in path.parents and "store.factory" in path.read_text(encoding="utf-8")
    ]

    # Só quem abre o banco semeia. Ninguém mais importa a fábrica.
    assert readers == [Path("store/db.py")]


def test_saving_a_workflow_replaces_its_steps():
    save_agent(AgentDef(id="tester", label="Tester"))
    first = WorkflowDef(
        id="demo",
        label="Demo",
        steps=(
            StepDef("demo", "a", 1, "A", "tester", "{{user_prompt}}", True),
            StepDef("demo", "b", 2, "B", "tester", "{{previous_summary}}", False),
        ),
    )
    save_workflow(first)

    # Um step removido da definição tem de sumir, não virar órfão.
    save_workflow(
        WorkflowDef(
            id="demo",
            label="Demo v2",
            steps=(StepDef("demo", "a", 1, "A", "tester", "{{user_prompt}}", True),),
        )
    )

    loaded = get_workflow("demo")
    assert loaded is not None
    assert loaded.label == "Demo v2"
    assert [step.step_id for step in loaded.steps] == ["a"]


def test_steps_come_back_in_position_order():
    save_agent(AgentDef(id="tester", label="Tester"))
    save_workflow(
        WorkflowDef(
            id="demo",
            label="Demo",
            steps=(
                StepDef("demo", "third", 0, "3", "tester", "x", False),
                StepDef("demo", "first", 0, "1", "tester", "x", False),
                StepDef("demo", "second", 0, "2", "tester", "x", False),
            ),
        )
    )

    loaded = get_workflow("demo")
    assert loaded is not None
    # `save_workflow` renumera pela ordem em que os steps chegaram.
    assert [step.step_id for step in loaded.steps] == ["third", "first", "second"]


def test_deleting_a_workflow_takes_its_steps_along():
    save_agent(AgentDef(id="tester", label="Tester"))
    save_workflow(
        WorkflowDef(
            id="demo",
            label="Demo",
            steps=(StepDef("demo", "a", 1, "A", "tester", "x", False),),
        )
    )

    delete_workflow("demo")

    assert get_workflow("demo") is None
    assert "demo" not in {item.id for item in list_workflows()}


def test_unknown_ids_are_none_not_an_invented_default():
    assert get_workflow("nao-existe") is None
    assert get_agent("nao-existe") is None


def test_loops_que_olham_o_repositorio_trazem_a_tarefa_pronta():
    """Quem não depende de um pedido do usuário já nasce com `default_prompt`."""
    workflows = {item.id: item for item in list_workflows()}

    assert workflows["analyze-codebase"].default_prompt == "Mapear codebase existente"
    assert workflows["setup-project"].default_prompt == "Novo projeto"
    # Os que dependem do pedido continuam pedindo: vazio é o que abre o campo.
    assert workflows["new-issue"].default_prompt == ""
    assert workflows["quick-fix"].default_prompt == ""
    assert workflows["default"].default_prompt == ""


def test_banco_semeado_antes_da_coluna_recebe_a_tarefa_na_migracao(tmp_path: Path):
    """Quem já usava o Pulse não pode continuar vendo o campo de texto.

    O `ALTER` dá `''` a toda linha que já existia, e a semeadura não roda de novo
    num banco já semeado — o backfill é o que fecha esse buraco.
    """
    import sqlite3

    from pulse.store.db import connect

    db_path = tmp_path / "antigo.db"
    connect(db_path).close()

    # Volta o banco ao estado anterior à coluna: semeado, mas sem `default_prompt`.
    raw = sqlite3.connect(str(db_path))
    raw.execute("ALTER TABLE workflow_defs DROP COLUMN default_prompt")
    raw.commit()
    raw.close()

    connect(db_path).close()

    workflows = {item.id: item for item in list_workflows(db_path=db_path)}
    assert workflows["analyze-codebase"].default_prompt == "Mapear codebase existente"
    assert workflows["setup-project"].default_prompt == "Novo projeto"


def test_backfill_nao_desfaz_a_edicao_do_usuario(tmp_path: Path):
    from pulse.store import factory
    from pulse.store.db import connect

    db_path = tmp_path / "editado.db"
    connection = connect(db_path)
    connection.execute(
        "UPDATE workflow_defs SET default_prompt = ? WHERE id = ?",
        ("Do meu jeito", "analyze-codebase"),
    )
    factory.backfill_default_prompts(connection)
    connection.commit()
    connection.close()

    workflows = {item.id: item for item in list_workflows(db_path=db_path)}
    assert workflows["analyze-codebase"].default_prompt == "Do meu jeito"


def test_os_loops_sem_ninguem_olhando_nao_pedem_aprovacao():
    """"Analisar codebase" e "Setup do projeto" rodam do começo ao fim.

    Eles não dependem de um pedido do usuário e não param no meio para perguntar
    se pode avançar — nenhum dos seus steps aprova.
    """
    workflows = {item.id: item for item in list_workflows()}

    for workflow_id in ("analyze-codebase", "setup-project"):
        approving = [
            step.step_id for step in workflows[workflow_id].steps if step.requires_approval
        ]
        assert approving == [], f"{workflow_id} ainda para para aprovar em {approving}"

    # E o playbook acompanha: pedir aprovação sem gate viraria uma pergunta solta.
    for workflow_id, step_id in (
        ("analyze-codebase", "codebase-explore"),
        ("setup-project", "setup-interview"),
    ):
        step = next(s for s in workflows[workflow_id].steps if s.step_id == step_id)
        assert "Aprovar {{step_label}}" not in step.prompt_template

    # Os pipelines que existem para serem revisados continuam aprovando.
    assert [step.requires_approval for step in workflows["new-issue"].steps] == [
        True,
        True,
        True,
        False,
        True,
        False,
    ]


def test_banco_antigo_perde_o_pedido_de_aprovacao_na_abertura(tmp_path: Path):
    """Quem já usava o Pulse tem a linha antiga no banco — `seed` não a reescreve."""
    from pulse.store import factory
    from pulse.store.db import connect

    db_path = tmp_path / "antigo.db"
    connection = connect(db_path)
    # Volta os dois steps ao que eram: com gate e com o bloco de aprovação.
    connection.executemany(
        """
        UPDATE workflow_steps
           SET requires_approval = 1, prompt_template = prompt_template || ?
         WHERE workflow_id = ? AND step_id = ?
        """,
        [
            (f"\n\n1. {factory.APPROVAL_MARK}\n", workflow_id, step_id)
            for workflow_id, step_id in factory.UNATTENDED_STEPS
        ],
    )
    connection.commit()
    connection.close()

    connect(db_path).close()

    workflows = {item.id: item for item in list_workflows(db_path=db_path)}
    for workflow_id, step_id in factory.UNATTENDED_STEPS:
        step = next(s for s in workflows[workflow_id].steps if s.step_id == step_id)
        assert step.requires_approval is False
        assert factory.APPROVAL_MARK not in step.prompt_template


def test_template_reescrito_pelo_usuario_nao_e_tocado(tmp_path: Path):
    """Sem o bloco de fábrica, a linha é do usuário — a migração não passa por cima."""
    from pulse.store import factory
    from pulse.store.db import connect

    db_path = tmp_path / "editado.db"
    connection = connect(db_path)
    connection.execute(
        """
        UPDATE workflow_steps SET prompt_template = ?
         WHERE workflow_id = 'analyze-codebase' AND step_id = 'codebase-explore'
        """,
        ("Explore do meu jeito.",),
    )
    connection.commit()
    connection.close()

    connect(db_path).close()

    workflows = {item.id: item for item in list_workflows(db_path=db_path)}
    step = next(
        s for s in workflows["analyze-codebase"].steps if s.step_id == "codebase-explore"
    )
    assert step.prompt_template == "Explore do meu jeito."
    assert factory.APPROVAL_MARK  # o guarda existe e é o que protegeu a edição


def test_banco_ja_semeado_ganha_a_fase_de_merge_na_abertura(tmp_path: Path):
    """A camada de merge precisa chegar a quem já tinha banco.

    `seed` é `INSERT OR IGNORE` e nem chega a rodar num banco já semeado — quem
    destrava isso é o `is_seeded`, que conta os ids de fábrica e derruba o teste
    quando a fábrica ganha linhas novas. Sem esse caminho, acrescentar um agente
    de fábrica só valeria para quem instalasse o Pulse do zero.
    """
    from pulse.store.db import connect

    db_path = tmp_path / "antigo.db"
    connection = connect(db_path)
    # Volta o banco ao que era antes de `review`/`review-fix` existirem, e marca
    # um dos steps antigos para provar que a re-semeadura não o reescreve.
    connection.execute(
        "DELETE FROM workflow_steps WHERE step_id IN ('review', 'review-fix')"
    )
    connection.execute("DELETE FROM agent_defs WHERE id IN ('review', 'review-fix')")
    connection.execute(
        """
        UPDATE workflow_steps SET prompt_template = ?
         WHERE workflow_id = 'new-issue' AND step_id = 'prd'
        """,
        ("PRD do meu jeito.",),
    )
    connection.commit()
    connection.close()

    connect(db_path).close()

    workflows = {item.id: item for item in list_workflows(db_path=db_path)}
    steps = {step.step_id: step for step in workflows["new-issue"].steps}
    assert (steps["review"].position, steps["review-fix"].position) == (5, 6)
    assert steps["review"].requires_approval is True
    assert steps["review-fix"].requires_approval is False
    assert get_agent("review", db_path=db_path) is not None
    assert get_agent("review-fix", db_path=db_path) is not None
    # E o que já estava lá continua como o usuário deixou.
    assert steps["prd"].prompt_template == "PRD do meu jeito."


def test_quem_escreve_artefato_nao_roda_com_deny_writes():
    """`deny_writes` recusa `write`/`edit` sem olhar o caminho.

    A fase de review existe para produzir `reviews/round-NNN.md`; com a política
    das fases de spec, o arquivo nunca chegaria ao disco — e, sem tool-call de
    escrita, nunca apareceria no painel de artefatos. É o que
    [pulse.prompts.permission] já diz: step que precisa escrever é `ask` ou
    `auto_approve`.
    """
    from pulse.prompts.permission import decide_permission

    params = {
        "toolCall": {"kind": "write"},
        "options": [
            {"optionId": "allow-once", "kind": "allow_once"},
            {"optionId": "reject-once", "kind": "reject_once"},
        ],
    }

    for agent_id in ("review", "review-fix"):
        agent = get_agent(agent_id)
        assert agent is not None
        assert decide_permission(params, policy=agent.permission_policy) != {
            "outcome": {"outcome": "selected", "optionId": "reject-once"}
        }, f"{agent_id} não consegue escrever o que a fase dele existe para produzir"


def test_so_o_review_oferece_pular():
    """Pular a spec é outra conversa: PRD/Techspec/Tasks seguem com três opções.

    O rótulo e o motor não podem discordar — é `classify_outcome` que transforma
    a escolha em `skipped`, e ele casa por substring. Um rótulo redigido sem
    "Pular" renderizaria um menu que promete algo que o motor não faz.
    """
    from pulse.prompts.approval import SKIP, classify_outcome

    workflows = {item.id: item for item in list_workflows()}
    offering = [
        step.step_id
        for workflow in workflows.values()
        for step in workflow.steps
        if step.requires_approval and "Pular" in step.prompt_template
    ]

    # O mesmo review, no "Nova spec" e no loop avulso.
    assert offering == ["review", "review"]

    step = next(s for s in workflows["new-issue"].steps if s.step_id == "review")
    option = next(
        line.strip()
        for line in step.prompt_template.splitlines()
        if line.strip().startswith("C)")
    )
    assert classify_outcome(f"→ {option}") == SKIP


def test_a_camada_de_merge_e_um_laco_com_teto():
    """Revisa, corrige, revisa de novo — até ninguém pedir mais nada.

    O teto é o mesmo do contrato de convergência que o playbook carrega: round 2
    só aceita o que um fix quebrou, round 3 fecha, round 4 não existe. Teto e
    playbook têm de dizer a mesma coisa, senão o motor para onde o texto promete
    continuar.
    """
    steps = {step.step_id: step for step in get_workflow("new-issue").steps}

    assert steps["review-fix"].repeat_from == "review"
    assert steps["review-fix"].repeat_max == 3
    # O alvo existe e vem antes: um laço que aponta para a frente nunca fecha.
    assert steps["review"].position < steps["review-fix"].position
    # Nenhum outro step de fábrica repete — laço é exceção, não default.
    repeating = [
        step.step_id
        for workflow in list_workflows()
        for step in workflow.steps
        if step.repeat_from
    ]
    assert repeating == ["review-fix", "review-fix"]

    # E os dois lados do protocolo combinam: o review sabe que pode rodar de
    # novo, e o fix sabe como pedir — também no loop avulso, de outra fase.
    for workflow_id in ("new-issue", "review"):
        steps = {step.step_id: step for step in get_workflow(workflow_id).steps}
        assert steps["review-fix"].repeat_max == 3
        assert "repeats" in steps["review"].prompt_template.lower()
        assert "next: repeat" in steps["review-fix"].prompt_template
        # E só o review encerra: limpo, ele declara o fim em vez de pedir aprovação.
        assert "next: close" in steps["review"].prompt_template
        assert "next: close" not in steps["review-fix"].prompt_template
