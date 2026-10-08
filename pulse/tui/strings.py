"""Every user-visible text of the TUI, in one place.

The product speaks Portuguese to the user while code, errors and logs are in
English; keeping the copy here keeps the screens free of Portuguese literals
(enforced by `tests/tui/test_strings.py`) and lets wording change without
touching behavior. Parametrized texts are `str.format` templates: the
placeholder names document what each one receives.
"""

from __future__ import annotations

from pulse.domain import ui_text

# Shared: actions, answers and hints reused across screens
BACK = "Voltar"
BACK_ARROW = "← Voltar"
CANCEL = "Cancelar"
CONFIRM = "Confirmar"
REMOVE = "Remover"
QUIT = "Sair"
# Dialog and error words the engine also records in the run history: one
# source, so the live screen and the reopened run never disagree.
YES = ui_text.ANSWER_YES
NO = ui_text.ANSWER_NO
CANCELLED = ui_text.ANSWER_CANCELLED
QUESTION = ui_text.QUESTION_TITLE
ANSWER = ui_text.ANSWER_TITLE
ERROR = ui_text.ERROR_TITLE
AGENT = "Agent"
ENVIRONMENT = "Ambiente"
HINT_CONFIRM_OR_CANCEL = "Enter confirma · Esc cancela"
HINT_CONFIRM_OR_BACK = "Enter confirma · Esc volta"
CURRENT_MARK = "{label}  · atual"
RUN_SUMMARY = "{current} · steps {done}/{total}"

# Apps
APP_TITLE = "Pulse // ACP Cockpit"
ONBOARDING_APP_TITLE = "Pulse // Setup"

# Cockpit and history detail: key bindings
BINDING_MENU = "Menu"
BINDING_STOP = "Parar"
BINDING_RESUME = "Retomar"
BINDING_REMOVE_WORKTREE = "Remover worktree"
BINDING_FOCUS = "Focus"
BINDING_ARTIFACTS = "Artifacts"
BINDING_BACK = "Back"
BINDING_PREV_FILE = "Prev file"
BINDING_NEXT_FILE = "Next file"
BINDING_UP = "Up"
BINDING_DOWN = "Down"

# Cockpit: run lifecycle messages in the stream
WORKFLOW_FAILED = ui_text.WORKFLOW_FAILED_TITLE
WORKFLOW_EXIT_CODE = "O fluxo encerrou com código {code}."
WORKFLOW_DONE = "Workflow concluído"
RUN_STOPPED = "Run parada — dá para retomar de onde parou"
RUN_BLOCKED = "Run bloqueada — resolva o que o step pediu e retome de onde parou"
RUN_RESUMABLE_FROM_FAILURE = "Dá para retomar do step que falhou"
RUN_STOPPING = "Parando — cortando o step em execução"

# Header
HEADER_BRAND = "PULSE // ACP COCKPIT"
HEADER_PIPELINE_BADGE = "SYS.PIPELINE"
HEADER_RUN_EMPTY = "RUN 0/0"
HEADER_STOPPED = "PARADA"
HEADER_AWAITING_INPUT = "PRECISA DE VOCÊ"

# Footer
FOOTER_MENU = "MENU"
FOOTER_BACK = "VOLTAR"
FOOTER_FOCUS = "FOCUS"
FOOTER_FOCUS_PHASES = "PHASES"
FOOTER_FOCUS_STREAM = "STREAM"
FOOTER_FOCUS_ARTIFACT = "ARTIFACT"
FOOTER_CLOSE = "FECHAR"
FOOTER_FILE = "FILE"
FOOTER_OPEN = "ABRIR"
FOOTER_STOP = "PARAR"
FOOTER_NAV = "NAV"

# Phase sidebar
SIDEBAR_NO_STEPS = "Nenhum step configurado"

# Log stream
STREAM_DEFAULT_SURFACE = "RUNTIME MODE & WORKSPACE CONFIG SURFACE"
STREAM_HEADER = "{surface} [backend]"
STREAM_META = "{count} entries · step {position}/{total}          {right}"
STREAM_ASSISTANT = "Assistente"
STREAM_WORKFLOW_FAILURE = "Falha no workflow"
STREAM_NO_ACTIVITY = "Nenhuma atividade neste item."
STREAM_WAITING = "Aguardando atividade do agente…"
STREAM_LOADING = "carregando…"
ENTRY_ASSISTANT_TITLE = "Assistant"
NO_PERSISTED_LOGS = "Nenhum log persistido para esta run."
# Artifact pane
ARTIFACT_OPEN_RAIL = "▸\nABRIR"
ARTIFACT_HEADER = "ARTEFATOS  {count}"
ARTIFACT_NONE_IN_PHASE = "Nenhum artefato nesta fase"
ARTIFACT_NONE_IN_PHASE_MARKDOWN = "_Nenhum artefato nesta fase._"
ARTIFACT_LIVE = "live"
ARTIFACT_PAUSED = "paused"
ARTIFACT_WRITING = "escrevendo"
ARTIFACT_WRITING_MARKDOWN = "_Escrevendo `{name}`…_"
ARTIFACT_EMPTY_MARKDOWN = "_`{name}` está vazio._"
ARTIFACT_TRUNCATED = "\n\n[… artefato truncado …]"

# Prompt dock and prompt bridge
PROMPT_BINDING_CANCEL = "Cancel"
PROMPT_DEFAULT_TITLE = "Prompt"
PROMPT_HINT_MULTI_SELECT = "Espaço marca · Enter confirma · Esc cancela"
PROMPT_HINT_SELECT = "↑↓ escolhe · letra vai direto · Enter confirma · Esc cancela"
PROMPT_INPUT_PLACEHOLDER = "Resposta…"
PERMISSION_TITLE = "Permissão"
OTHER_OPTION_PROMPT = "{prompt}\n[Outro — descreva]"

# Confirm modal
CONFIRM_TITLE_REMOVE_FROM_HISTORY = "REMOVER DO HISTÓRICO"
CONFIRM_TITLE_REMOVE_WORKTREE = "REMOVER WORKTREE"

# Resume choice modal
RESUME_TITLE = "WORKFLOW NÃO CONCLUÍDO"
RESUME_STOPPED_AT = "parou em: {summary}"
RESUME_OPTION = "Retomar de onde parou"

# Home
HOME_SUBTITLE = "Orquestrador de agentes de IA · v{version}"
HOME_ROOT_HINT = "↑↓ navega · Enter seleciona · Q sai"
HOME_TASK_PLACEHOLDER = "Descreva a tarefa e tecle Enter · Esc cancela"
HOME_ALERTS_ONE = "{count} sessão precisa de você"
HOME_ALERTS_MANY = "{count} sessões precisam de você"
HOME_ALERTS_HINT = "Enter abre a sessão para responder · Esc volta"
HOME_START_NOW = "Enter inicia agora"
HOME_DESCRIBE_TASK = "Enter para descrever a tarefa"
HOME_SESSION_HINT = "{description}\n{keys} · Esc volta"
HOME_SETUP = "Configurar Pulse"
HOME_ANSWER_ONE = "Responder 1 sessão pendente"
HOME_ANSWER_MANY = "Responder {count} sessões pendentes"
HOME_NEW_SESSION = "Nova sessão"
HOME_HISTORY = "Histórico"
HOME_SETTINGS = "Configurações"
HOME_EXIT_RUNNING_ONE = (
    "[pulse] {count} sessão continua rodando em segundo plano. "
    "Rode `pulse` e abra Histórico para acompanhar."
)
HOME_EXIT_RUNNING_MANY = (
    "[pulse] {count} sessões continuam rodando em segundo plano. "
    "Rode `pulse` e abra Histórico para acompanhar."
)

# History list
HISTORY_BINDING_SEARCH = "Buscar"
HISTORY_TITLE = "HISTÓRICO"
HISTORY_SEARCH_PLACEHOLDER = "Buscar runs…"
HISTORY_HINT = "/ busca  ·  Enter abre  ·  d remove"
HISTORY_EMPTY = "Nenhuma run encontrada"
HISTORY_RUN_REMOVED = "Run removida: {title}"
HISTORY_RUN_ALREADY_GONE = "Essa run já não estava mais no histórico"
HISTORY_REMOVE_DETAIL = (
    "Apaga a run, os logs e a lista de artefatos. Os arquivos no workspace ficam."
)
HISTORY_REMOVE_LIVE_WARNING = "Atenção: esta run consta em andamento — remover pode derrubá-la."

# History detail: worktree removal
WORKTREE_KEPT_RUN_ACTIVE = "Worktree mantido — a run está em andamento"
WORKTREE_BRANCH = "Branch: {branch}"
WORKTREE_DIRTY = (
    "Há mudança não commitada aqui. O git vai recusar a remoção — commite ou descarte antes."
)
WORKTREE_CLEAN = "A branch continua no repositório; só o diretório sai."
WORKTREE_REMOVED = "Worktree removido"
WORKTREE_GIT_REFUSED = "Worktree mantido — o git recusou a remoção"

# Onboarding
ONBOARD_TITLE = "CONFIGURAR PULSE"
ONBOARD_WORKSPACE_PLACEHOLDER = "Caminho do workspace…"
ONBOARD_HINT_KEYS = "Enter confirma  ·  Esc cancela"
ONBOARD_CONFIG_EXISTS = "Config já existe"
ONBOARD_RECONFIGURE = "Sim — reconfigurar"
ONBOARD_KEEP = "Não — manter"
ONBOARD_DEFAULT_AGENT = "Agente padrão"
ONBOARD_RUNTIME_OPTION = "{label} — `{binary}`"
ONBOARD_ENVIRONMENT_FOR = "Ambiente — {runtime}"
ONBOARD_QUIT_INSTALL = "Sair — {hint}"
ONBOARD_RETRY = "Tentar de novo"
ONBOARD_AUTH_LATER = "Usar {env_var} depois"
ONBOARD_WORKSPACE_STATUS = "Diretório padrão do workspace"
ONBOARD_WORKSPACE_INPUT = "Caminho absoluto do workspace"
ONBOARD_INVALID_DIRECTORY = "Diretório inválido. Escolha uma pasta existente."
ONBOARD_EXPORT_KEY = "Exporte {env_var} e rode `pulse` de novo."
ONBOARD_OPENING_LOGIN = "Abrindo {login}…"
ONBOARD_LOGIN_FAILED = "Login não concluído"
ONBOARD_TESTING_ACP = "Testando conexão ACP…"
ONBOARD_ACP_CONNECTION = "Conexão ACP"
ONBOARD_CONTINUE_ANYWAY = "Continuar mesmo assim"
ONBOARD_ENGINE_UNAVAILABLE = "Engine indisponível"
ONBOARD_RUN_LOGIN = "Executar `{command}`"
ENGINE_UNAVAILABLE = "Engine indisponível: {error}"
ONBOARD_MODEL = "Modelo preferido"
ONBOARD_POLICY = "Política de permissões"
ONBOARD_READY = "Pronto"
ONBOARD_CONFIG_SAVED = "Config salvo em {path}"

# Settings
SETTINGS_TITLE = "CONFIGURAÇÕES"
SETTINGS_ROOT_STATUS = "Agents e ambiente"
SETTINGS_HINT_KEYS = "Enter seleciona  ·  Esc volta"
SETTINGS_GLOBAL_OPTION = "Global — runtime, modelo e permissões de todos os agents"
SETTINGS_AGENTS_OPTION = "Agents — runtime, modelo e permissões"
SETTINGS_WORKTREE_OPTION = "Worktree — isolar cada run em branch própria · {state}"
SETTINGS_WORKTREE_ON = "ligado"
SETTINGS_WORKTREE_OFF = "desligado"
SETTINGS_DOCTOR_OPTION = "Verificar ambiente"
SETTINGS_WORKTREE_ENABLED = (
    "As runs deste projeto passam a rodar num `git worktree` próprio, em "
    "`~/.pulse/worktrees/`, numa branch `pulse/…` por run. A árvore de "
    "trabalho do editor fica intocada."
)
SETTINGS_WORKTREE_DISABLED = (
    "As runs voltam a rodar na árvore de trabalho do projeto. "
    "Os worktrees já criados continuam onde estão."
)
SETTINGS_LOADING_MODELS = "Carregando modelos…"
SETTINGS_PICK_MODEL = "Escolha o modelo"
SETTINGS_PICK_POLICY = "Escolha a política de permissões"
SETTINGS_PICK_AGENT = "Escolha o agent"
SETTINGS_PICK_RUNTIME = "Escolha o runtime"
SETTINGS_PICK_GLOBAL = "{title} (global)"
SETTINGS_GLOBAL = "Global"
SETTINGS_GLOBAL_REPORT = (
    "O global sobrescreve todos os agents. Trocar um agent depois vale só para ele."
)
SETTINGS_FIELD_RUNTIME = "Runtime — {value}"
SETTINGS_FIELD_MODEL = "Modelo — {value}"
SETTINGS_FIELD_PERMISSIONS = "Permissões — {value}"
SETTINGS_AGENT_OPTION = "{label} — {runtime} · {model}"
SETTINGS_RUNTIME_OPTION = "{name} — {binary}"
SETTINGS_DOCTOR_GLOBAL_CONFIG = "[ok] Config global · modelo={model}"
SETTINGS_DOCTOR_PROJECT_CONFIG = "[ok] Config projeto · {source}"
SETTINGS_DOCTOR_NO_CHECKS = "Nenhum check"

# Permission policies, keyed by `PERMISSION_POLICIES`
PERMISSION_LABELS = {
    "ask": "Perguntar antes de cada permissão",
    "auto_approve": "Aprovar automaticamente",
    "deny_writes": "Permitir leitura e artefatos Pulse, bloquear escrita de código",
}
