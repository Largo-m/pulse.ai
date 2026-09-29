"""Renderização de template de prompt.

O texto do prompt é dado — vem da coluna `prompt_template` do step — e o Pulse
só preenche os valores que ele conhece da run. Não há template em arquivo: o
pacote não carrega `.md` nenhum.

Placeholders usam `{{chave}}`. Chave simples (`{chave}`) não serve porque o
texto do agente costuma conter `{` literal.
"""

from __future__ import annotations

import re

PLACEHOLDER = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}", re.IGNORECASE)

#: `{{#if chave}}…{{/if}}` — o trecho some quando a chave está vazia. Existe para
#: o template não precisar de uma variante inteira só porque uma linha é
#: opcional (ex.: citar o resumo do step anterior no primeiro step).
CONDITIONAL = re.compile(
    r"\{\{#if\s+([a-z0-9_]+)\s*\}\}\n?(.*?)\{\{/if\}\}\n?",
    re.IGNORECASE | re.DOTALL,
)


class TemplateError(RuntimeError):
    """Template pedindo um valor que o Pulse não tem."""


def render(text: str, context: dict[str, str]) -> str:
    """Troca `{{chave}}` pelo valor. Chave desconhecida é erro, não buraco.

    Silenciar um placeholder faria o agente receber uma instrução truncada e
    ninguém notaria até a run sair errada.
    """
    missing: list[str] = []

    def _conditional(match: re.Match[str]) -> str:
        key, body = match.group(1), match.group(2)
        return body if context.get(key, "").strip() else ""

    text = CONDITIONAL.sub(_conditional, text)

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            missing.append(key)
            return match.group(0)
        return context[key]

    result = PLACEHOLDER.sub(_replace, text)
    if missing:
        raise TemplateError("placeholder sem valor: " + ", ".join(sorted(set(missing))))
    return result
