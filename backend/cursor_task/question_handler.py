from __future__ import annotations

import json
import re
from typing import Callable, TextIO

from cursor_task.stream_renderer import StreamRenderer
from cursor_task.types import ClarifyingQuestion

APPROVAL_MARKERS = (
    r"revise o rascunho",
    r"informe:\s*$",
    r"aprovado.*salvar",
    r"descartar e recomeçar",
    r"ajustar seções específicas",
    r"aguardo sua aprovação",
    r"breakdown proposto",
    r"não gerei.*_tasks",
    r"responda com.*aprovação",
    r"próximo passo \(após sua aprovação\)",
)

OPTION_PATTERNS = (
    re.compile(r"(?m)^\*\*([A-D])\)\*\*\s*(.+)$"),
    re.compile(r"(?m)^([A-D])\)\s+(.+)$"),
)


class QuestionHandler:
    def __init__(
        self,
        input_fn: Callable[[str], str] | None = None,
        renderer: StreamRenderer | None = None,
    ) -> None:
        self._input_fn = input_fn or self._default_input
        self._renderer = renderer or StreamRenderer()

    def extract_from_tool_call(self, name: str, args: object, status: str) -> ClarifyingQuestion | None:
        normalized = name.lower().replace("_", "").replace("-", "")
        if "askquestion" not in normalized and "askuser" not in normalized:
            return None
        if status not in ("running", "pending", "started"):
            return None
        payload = self._coerce_mapping(args)
        if not payload:
            return None
        return self._from_payload(payload)

    def extract_from_acp(self, params: dict) -> ClarifyingQuestion:
        questions = params.get("questions") or []
        parts: list[str] = []
        options: list[str] = []
        title = params.get("title")
        if title:
            parts.append(str(title))
        for item in questions:
            prompt = item.get("prompt") or item.get("question") or ""
            if prompt:
                parts.append(str(prompt))
            for option in item.get("options") or []:
                label = option.get("label") or option.get("id") or ""
                if label:
                    options.append(str(label))
        text = "\n".join(parts).strip() or "Informe sua resposta:"
        allow_multiple = any(bool(q.get("allowMultiple")) for q in questions)
        return ClarifyingQuestion(text=text, options=options, allow_multiple=allow_multiple, raw=params)

    def extract_from_assistant_text(self, text: str) -> ClarifyingQuestion | None:
        return self.extract_pending_question(text)

    def extract_pending_question(self, text: str) -> ClarifyingQuestion | None:
        stripped = text.strip()
        if not stripped:
            return None

        approval = self.extract_approval_question(stripped)
        if approval:
            return approval

        scan_text = self._tail_for_scan(stripped)
        options = self._extract_options(scan_text)
        has_question = self._has_real_question(scan_text)
        if has_question or options:
            body = self._strip_options_from_text(scan_text).strip() if options else scan_text.strip()
            return ClarifyingQuestion(text=body, options=options)
        return None

    def extract_approval_question(self, text: str) -> ClarifyingQuestion | None:
        scan_text = self._tail_for_scan(text)
        lowered = scan_text.lower()
        has_marker = any(re.search(marker, lowered) for marker in APPROVAL_MARKERS)
        options = self._extract_options(scan_text)
        if not has_marker and len(options) < 2:
            return None
        body = self._strip_options_from_text(scan_text).strip() if options else scan_text.strip()
        return ClarifyingQuestion(
            text=body,
            options=options,
            raw={"kind": "approval"},
        )

    def is_approval_prompt(self, question: ClarifyingQuestion) -> bool:
        if question.raw and question.raw.get("kind") == "approval":
            return True
        lowered = question.text.lower()
        return any(re.search(marker, lowered) for marker in APPROVAL_MARKERS)

    def is_approval_granted(self, answer: str) -> bool:
        normalized = answer.strip().lower()
        if normalized in {"a", "aprovado", "approved", "sim", "yes", "ok"}:
            return True
        return normalized.startswith("a)") or normalized.startswith("a )")

    def is_discard_requested(self, answer: str) -> bool:
        normalized = answer.strip().lower()
        return normalized in {"d", "descartar", "recomeçar", "recomecar"}

    def prompt_user(self, question: ClarifyingQuestion, *, display: bool = True) -> str:
        if display:
            self._renderer.question(self._format_question_prompt(question))
        answer = self._input_fn("> ").strip()
        if not answer:
            raise ValueError("resposta do usuário não pode ser vazia")
        self._renderer.user_answer(answer)
        return answer

    def format_acp_response(self, question: ClarifyingQuestion, answer: str) -> dict:
        params = question.raw or {}
        questions = params.get("questions") or []
        if not questions:
            return {"outcome": {"outcome": "answered", "answers": []}}
        selected_ids = self._map_answer_to_option_ids(answer, questions[0])
        return {
            "outcome": {
                "outcome": "answered",
                "answers": [
                    {
                        "questionId": questions[0].get("id") or "q1",
                        "selectedOptionIds": selected_ids,
                    }
                ],
            }
        }

    def _from_payload(self, payload: dict) -> ClarifyingQuestion:
        questions = payload.get("questions")
        if isinstance(questions, list) and questions:
            return self.extract_from_acp({"questions": questions, "title": payload.get("title")})
        for key in ("question", "prompt", "text", "message"):
            if payload.get(key):
                return ClarifyingQuestion(text=str(payload[key]), raw=payload)
        return ClarifyingQuestion(text=json.dumps(payload, ensure_ascii=False), raw=payload)

    def _map_answer_to_option_ids(self, answer: str, question: dict) -> list[str]:
        options = question.get("options") or []
        if not options:
            return [answer]
        normalized = answer.strip().upper()
        if len(normalized) == 1 and normalized.isalpha():
            index = ord(normalized) - ord("A")
            if 0 <= index < len(options):
                option = options[index]
                return [str(option.get("id") or option.get("label") or normalized)]
        for option in options:
            option_id = str(option.get("id") or "")
            label = str(option.get("label") or "")
            if answer == option_id or answer == label:
                return [option_id or label]
        return [answer]

    @staticmethod
    def _coerce_mapping(value: object) -> dict | None:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                loaded = json.loads(value)
            except json.JSONDecodeError:
                return None
            return loaded if isinstance(loaded, dict) else None
        if hasattr(value, "__dict__"):
            return dict(vars(value))
        return None

    @staticmethod
    def _default_input(prompt: str) -> str:
        return input(prompt)

    @staticmethod
    def _tail_for_scan(text: str, max_chars: int = 2500) -> str:
        if len(text) <= max_chars:
            return text
        return text[-max_chars:]

    @staticmethod
    def _has_real_question(text: str) -> bool:
        scrubbed = re.sub(r"\?\:", ":", text)
        scrubbed = re.sub(r"\?\?", "", scrubbed)
        return "?" in scrubbed

    @classmethod
    def _extract_options(cls, text: str) -> list[str]:
        for pattern in OPTION_PATTERNS:
            matches = pattern.findall(text)
            if matches:
                return [label.strip() for _, label in matches]
        return []

    def _format_question_prompt(self, question: ClarifyingQuestion) -> str:
        body = question.text.strip()
        if not question.options:
            return body
        lines = [body, ""]
        for index, option in enumerate(question.options):
            letter = chr(ord("A") + index)
            lines.append(f"{letter}) {option}")
        return "\n".join(lines).strip()

    @classmethod
    def _strip_options_from_text(cls, text: str) -> str:
        lines: list[str] = []
        for line in text.splitlines():
            if any(pattern.match(line.strip()) for pattern in OPTION_PATTERNS):
                continue
            lines.append(line)
        result = "\n".join(lines).strip()
        while result.endswith("---"):
            result = result[:-3].strip()
        return result
