from __future__ import annotations

from typing import Any, Literal

PermissionPolicy = Literal["ask", "auto_approve", "deny_writes"]

_PATH_KEYS = frozenset({"path", "filepath", "file_path", "uri", "absolute_path"})


def permission_selected(option_id: str) -> dict[str, Any]:
    return {"outcome": {"outcome": "selected", "optionId": option_id}}


def permission_cancelled() -> dict[str, Any]:
    return {"outcome": {"outcome": "cancelled"}}


def pick_permission_option(options: list[Any], *, prefer: str) -> str | None:
    for option in options:
        if not isinstance(option, dict):
            continue
        kind = str(option.get("kind", ""))
        option_id = str(option.get("optionId", ""))
        if not option_id:
            continue
        if prefer == "allow" and kind.startswith("allow"):
            return option_id
        if prefer == "reject" and kind.startswith("reject"):
            return option_id
    return None


def permission_kind(params: dict[str, Any]) -> str:
    """O que o agente quer fazer, como o ACP nomeia: `edit`, `execute`…"""
    permission = params.get("permission")
    if not isinstance(permission, dict):
        permission = {}
    kind = str(permission.get("kind", "")).lower()
    if kind:
        return kind
    tool_call = params.get("toolCall")
    if not isinstance(tool_call, dict):
        tool_call = {}
    return str(tool_call.get("kind", "")).lower()


def decide_permission(
    params: dict[str, Any],
    *,
    policy: PermissionPolicy,
    allow_terminal: bool = False,
) -> dict[str, Any] | None:
    """A resposta que a política dá sozinha. `None` = só uma pessoa decide.

    Isto vive fora da TUI porque **não é pergunta**: `auto_approve`,
    `deny_writes` e o veto a terminal são regra, e regra o Pulse aplica onde a
    run roda. Enquanto essa decisão morava só no cliente, uma run cujo cockpit
    tinha sido fechado parava para sempre num `edit` que ninguém precisava ver —
    o daemon publicava a pergunta, não havia tela para respondê-la, e a run
    ficava "precisando de você" para decidir o que a política já tinha decidido.

    Só `ask` devolve `None`, que é quando perguntar é o ponto.
    """
    options = params.get("options")
    if not isinstance(options, list):
        options = []
    kind = permission_kind(params)

    def chosen(prefer: str, fallback: str) -> dict[str, Any]:
        return permission_selected(pick_permission_option(options, prefer=prefer) or fallback)

    if not allow_terminal and (
        "terminal" in kind or "shell" in kind or "bash" in kind or "command" in kind
    ):
        return chosen("reject", "reject-once")

    if policy == "auto_approve":
        return chosen("allow", "allow-once")

    if policy == "deny_writes":
        # Sem exceção por caminho: o Pulse não sabe qual pasta é "dele".
        # Step que precisa escrever é step com `ask` ou `auto_approve`.
        if "write" in kind or "edit" in kind:
            return chosen("reject", "reject-once")
        return chosen("allow", "allow-once")

    return None


def permission_target_paths(params: dict[str, Any]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        text = str(value or "").strip()
        if not text or text in seen:
            return
        seen.add(text)
        found.append(text)

    def walk(node: Any, *, depth: int = 0) -> None:
        if depth > 6 or node is None:
            return
        if isinstance(node, dict):
            for key, value in node.items():
                if str(key).lower() in _PATH_KEYS:
                    add(value)
                walk(value, depth=depth + 1)
            return
        if isinstance(node, list):
            for item in node:
                walk(item, depth=depth + 1)

    walk(params)
    permission = params.get("permission")
    if isinstance(permission, dict):
        add(permission.get("title"))
    return found


