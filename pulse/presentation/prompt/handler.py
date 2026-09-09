from __future__ import annotations

from typing import Any, Literal

import questionary
from rich.console import Console
from rich.panel import Panel

from pulse.presentation.prompt.ask_question import (
    DEFAULT_QUESTIONNAIRE_TITLE,
    OTHER_OPTION_ID,
    build_ask_question_answers,
    build_ask_question_cancelled,
    format_option_label,
    is_other_option,
    option_requires_description,
    parse_ask_question_params,
    parse_questionnaire_meta,
    resolve_question_progress,
    should_add_other_option,
)
from pulse.presentation.prompt.text_questionnaire import (
    TextQuestion,
    TextQuestionnaire,
    format_questionnaire_answers,
    parse_text_questionnaire,
)
from pulse.terminal.styles import MENU_STYLE

PermissionPolicy = Literal["ask", "auto_approve", "deny_writes"]


def _permission_selected(option_id: str) -> dict[str, Any]:
    return {"outcome": {"outcome": "selected", "optionId": option_id}}


def _permission_cancelled() -> dict[str, Any]:
    return {"outcome": {"outcome": "cancelled"}}


def _pick_permission_option(options: list[Any], *, prefer: str) -> str | None:
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


class PromptHandler:
    def __init__(self, *, console: Console | None = None) -> None:
        self._console = console or Console(highlight=False, soft_wrap=True)

    def respond_to_ask_question(self, params: dict[str, Any]) -> dict[str, Any]:
        questions = parse_ask_question_params(params)
        if not questions:
            return build_ask_question_cancelled()

        meta = parse_questionnaire_meta(params)
        answers: list[dict[str, Any]] = []
        batch_size = len(questions)

        for position, question in enumerate(questions, start=1):
            result = self._ask_single_question(
                question,
                meta=meta,
                position=position,
                batch_size=batch_size,
            )
            if result is None:
                return build_ask_question_cancelled()
            answers.append(result)

        return build_ask_question_answers(answers)

    def run_text_questionnaire(self, text: str) -> str | None:
        questionnaire = parse_text_questionnaire(text)
        if questionnaire is None:
            return None
        return self.run_parsed_questionnaire(questionnaire)

    def run_parsed_questionnaire(self, questionnaire: TextQuestionnaire) -> str | None:
        meta = {"title": questionnaire.title}
        total = len(questionnaire.questions)
        collected: list[tuple[TextQuestion, str]] = []

        for position, question in enumerate(questionnaire.questions, start=1):
            question_payload = {
                "id": question.id,
                "prompt": question.prompt,
                "options": [
                    {"id": letter, "label": label}
                    for letter, label in question.options
                ],
            }
            result = self._ask_single_question(
                question_payload,
                meta=meta,
                position=position,
                batch_size=total,
            )
            if result is None:
                return None
            answer = self._format_answer(question, result)
            collected.append((question, answer))

        self._console.print()
        return format_questionnaire_answers(questionnaire, collected)

    def _format_answer(self, question: TextQuestion, result: dict[str, Any]) -> str:
        selected = result.get("selectedOptionIds", [])
        if not selected:
            return ""
        value = str(selected[0])
        if "::" in value:
            letter, detail = value.split("::", 1)
            for option_letter, label in question.options:
                if letter == option_letter:
                    return f"{letter}) {label} — {detail}"
            return f"{value.replace('::', ' — ')}"
        for letter, label in question.options:
            if value == letter:
                return f"{letter}) {label}"
        return value

    def respond_to_create_plan(self, params: dict[str, Any]) -> dict[str, Any]:
        name = str(params.get("name") or "Plano").strip()
        overview = str(params.get("overview") or "").strip()
        plan = str(params.get("plan") or "").strip()

        lines = [f"[bold]{name}[/bold]"]
        if overview:
            lines.append(overview)
        if plan:
            lines.append("")
            lines.append(plan[:1200])

        questionary.print("\n".join(lines), style="")
        approved = questionary.confirm("Aprovar plano?", default=True, style=MENU_STYLE).ask()
        if approved is None:
            return {"outcome": {"outcome": "cancelled"}}
        if approved:
            return {"outcome": {"outcome": "accepted"}}
        return {"outcome": {"outcome": "rejected"}}

    def _ask_single_question(
        self,
        question: dict[str, Any],
        *,
        meta: dict[str, Any],
        position: int,
        batch_size: int,
    ) -> dict[str, Any] | None:
        question_id = str(question.get("id", ""))
        prompt = str(question.get("prompt", "Pergunta")).strip()
        options = question.get("options", [])
        allow_multiple = bool(
            question.get("allow_multiple", question.get("allowMultiple", False))
        )
        index, total = resolve_question_progress(
            question=question,
            position=position,
            batch_size=batch_size,
            meta=meta,
        )

        self._render_question_header(meta=meta, index=index, total=total)
        self._console.print()

        if not isinstance(options, list) or not options:
            free_text = questionary.text(prompt, style=MENU_STYLE).ask()
            if free_text is None:
                return None
            return {
                "questionId": question_id,
                "selectedOptionIds": [free_text.strip()],
            }

        choices = self._build_choices(options, prompt=prompt)
        if not choices:
            return None

        select_prompt = prompt
        if allow_multiple:
            select_prompt = f"{prompt}\n(escolha uma ou mais)"

        if allow_multiple:
            selected = questionary.checkbox(select_prompt, choices=choices, style=MENU_STYLE).ask()
            if selected is None:
                return None
            selected_ids = [str(item) for item in selected]
            if OTHER_OPTION_ID in selected_ids:
                custom = self._prompt_other_text(prompt)
                if custom is None:
                    return None
                selected_ids = [
                    custom if item == OTHER_OPTION_ID else item for item in selected_ids
                ]
            if not selected_ids:
                questionary.print("Selecione ao menos uma opção.", style="fg:yellow")
                return self._ask_single_question(
                    question,
                    meta=meta,
                    position=position,
                    batch_size=batch_size,
                )
            return {"questionId": question_id, "selectedOptionIds": selected_ids}

        selected = questionary.select(select_prompt, choices=choices, style=MENU_STYLE).ask()
        if selected is None:
            return None

        if str(selected) == OTHER_OPTION_ID:
            custom = self._prompt_other_text(prompt)
            if custom is None:
                return None
            return {"questionId": question_id, "selectedOptionIds": [custom]}

        selected_id = str(selected)
        selected_label = self._choice_label(choices, selected_id)
        if selected_label and option_requires_description(selected_label):
            custom = self._prompt_follow_up_text(prompt, selected_label)
            if custom is None:
                return None
            return {
                "questionId": question_id,
                "selectedOptionIds": [f"{selected_id}::{custom}"],
            }

        return {"questionId": question_id, "selectedOptionIds": [selected_id]}

    def _render_question_header(
        self,
        *,
        meta: dict[str, Any],
        index: int | None,
        total: int | None,
    ) -> None:
        title = str(meta.get("title") or "").strip() or DEFAULT_QUESTIONNAIRE_TITLE
        if index is not None and total is not None:
            self._console.print(
                Panel(
                    f"Pergunta {index} de {total}",
                    title=f"[bold cyan]{title}[/bold cyan]",
                    border_style="cyan",
                    padding=(0, 1),
                )
            )
        elif index is not None:
            self._console.print(
                Panel(
                    f"Pergunta {index}",
                    title=f"[bold cyan]{title}[/bold cyan]",
                    border_style="cyan",
                    padding=(0, 1),
                )
            )
        else:
            self._console.print(
                Panel(
                    f"[bold cyan]{title}[/bold cyan]",
                    border_style="cyan",
                    padding=(0, 1),
                )
            )

    def _build_choices(self, options: list[Any], *, prompt: str = "") -> list[questionary.Choice]:
        choices: list[questionary.Choice] = []
        has_other = False
        option_index = 0
        option_labels: list[str] = []

        for option in options:
            if not isinstance(option, dict):
                continue
            option_id = str(option.get("id", option.get("label", "")))
            label = str(option.get("label", option_id))
            option_labels.append(label)
            if is_other_option(option_id, label):
                has_other = True
                option_id = OTHER_OPTION_ID
                label = format_option_label(option_index, "Outro (descreva)")
                option_index += 1
            else:
                label = format_option_label(option_index, label)
                option_index += 1
            choices.append(questionary.Choice(label, value=option_id))

        if choices and not has_other and should_add_other_option(
            prompt=prompt,
            option_labels=option_labels,
        ):
            other_label = format_option_label(option_index, "Outro (descreva)")
            choices.append(questionary.Choice(other_label, value=OTHER_OPTION_ID))

        return choices

    @staticmethod
    def _choice_label(choices: list[questionary.Choice], selected_id: str) -> str | None:
        for choice in choices:
            if str(choice.value) == selected_id:
                return str(choice.title)
        return None

    def _prompt_follow_up_text(self, prompt: str, option_label: str) -> str | None:
        self._console.print()
        value = questionary.text(
            f"{prompt}\n[{option_label}]",
            style=MENU_STYLE,
        ).ask()
        if value is None:
            return None
        value = value.strip()
        if not value:
            questionary.print("Descreva a opção escolhida.", style="fg:yellow")
            return self._prompt_follow_up_text(prompt, option_label)
        return value

    def _prompt_other_text(self, prompt: str) -> str | None:
        self._console.print()
        value = questionary.text(
            f"{prompt}\n[Outro — descreva]",
            style=MENU_STYLE,
        ).ask()
        if value is None:
            return None
        value = value.strip()
        if not value:
            questionary.print("Descreva a opção escolhida.", style="fg:yellow")
            return self._prompt_other_text(prompt)
        return value

    def respond_to_permission(
        self,
        params: dict[str, Any],
        *,
        policy: PermissionPolicy,
        allow_terminal: bool = False,
    ) -> dict[str, Any]:
        permission = params.get("permission", {})
        if not isinstance(permission, dict):
            permission = {}
        options = params.get("options", [])
        if not isinstance(options, list):
            options = []

        title = str(permission.get("title") or permission.get("description") or "Permissão solicitada")
        kind = str(permission.get("kind", "")).lower()
        tool_call = params.get("toolCall", {})
        if isinstance(tool_call, dict):
            kind = kind or str(tool_call.get("kind", "")).lower()

        if not allow_terminal and (
            "terminal" in kind or "shell" in kind or "bash" in kind or "command" in kind
        ):
            option_id = _pick_permission_option(options, prefer="reject") or "reject-once"
            return _permission_selected(option_id)

        if policy == "auto_approve":
            option_id = _pick_permission_option(options, prefer="allow") or "allow-once"
            return _permission_selected(option_id)

        if policy == "deny_writes":
            if "write" in kind or "edit" in kind:
                option_id = _pick_permission_option(options, prefer="reject") or "reject-once"
                return _permission_selected(option_id)
            option_id = _pick_permission_option(options, prefer="allow") or "allow-once"
            return _permission_selected(option_id)

        approved = questionary.confirm(f"{title}\nPermitir?", default=True, style=MENU_STYLE).ask()
        if approved is None:
            return _permission_cancelled()
        prefer = "allow" if approved else "reject"
        option_id = _pick_permission_option(options, prefer=prefer)
        if option_id:
            return _permission_selected(option_id)
        return _permission_selected("allow-once" if approved else "reject-once")
