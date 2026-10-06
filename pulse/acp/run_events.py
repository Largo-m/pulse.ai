"""O log da run no banco do Pulse: o que o cockpit mostra, gravado para o histórico.

Vive fora do [pulse.acp.session_runner] porque não é transporte ACP: é a
tradução de `session/update` em linhas de `run_events` e em artefatos da run.
"""

from __future__ import annotations

from typing import Any

from pulse.history.events import LogKind
from pulse.history.prompt_detail import build_prompt_qa
from pulse.history.tool_detail import build_tool_labels, extract_paths, merge_tool_update
from pulse.prompts.text_questionnaire import QUESTIONNAIRE_NOTICE, strip_questionnaire_block


class RunEventRecorder:
    """Mixin do runner. Lê do runner: `_bound_run_id`, `_phase_id`,
    `_session_id`, `_cwd` e `_stream`; o estado do log (`_text_buffer`,
    `_tool_payloads`, `_tool_kinds`, `_tool_labeled`) também nasce no runner.
    """

    #: Onde cada runtime põe o caminho do arquivo no `rawInput` do tool-call.
    _PATH_KEYS = ("path", "file_path", "target_file", "filePath", "abs_path")
    #: Tool-calls que produzem artefato. É assim que o Pulse descobre o que o
    #: agente escreveu — não há convenção de pasta nem de extensão.
    _WRITE_KINDS = frozenset({"edit", "write", "create"})

    def _record_run_event(self, params: dict[str, Any]) -> None:
        """Grava no banco do Pulse o que o cockpit está mostrando.

        Ler o log do runtime não serve: só o Cursor tem um, e o Pulse é
        agnóstico ao agente que está rodando.

        O que vai para o banco passa pelo **mesmo** rótulo que a tela ao vivo
        usa ([pulse.history.tool_detail.build_tool_labels]): tipo do tool, alvo e
        detalhe. Gravar o `title` cru do ACP com um `kind` fixo "Tool" era o que
        fazia o histórico mostrar uma fileira de "v Tool" onde a sessão viva
        mostra "Read pulse/store/runs.py" ou "Shell pytest -q".
        """
        if not self._bound_run_id:
            return
        update = params.get("update", params)
        if not isinstance(update, dict):
            return
        kind = str(update.get("sessionUpdate") or "")
        if kind == "agent_message_chunk":
            content = update.get("content")
            if isinstance(content, dict) and content.get("type") == "text":
                text = str(content.get("text") or "")
                if text:
                    self._text_buffer.append(text)
            return
        if kind not in {"tool_call", "tool_call_update", "tool_result"}:
            return
        self._flush_text()
        tool_id = str(update.get("toolCallId") or "")
        merged = self._merge_tool_payload(tool_id, update)
        log_kind, title, detail = self._tool_labels(tool_id, merged)
        if title.strip() in {"", "…", "..."} and not detail.strip():
            # Tool-call que ainda não disse o que vai fazer. Regravar o
            # placeholder apagaria o rótulo bom que já está na linha: o
            # `tool_id` reescreve a existente em vez de acrescentar.
            if tool_id in self._tool_labeled:
                return
            title = "…"
        elif tool_id:
            self._tool_labeled.add(tool_id)
        self._save_event(kind=log_kind, title=title, detail=detail, tool_id=tool_id)
        self._record_artifacts(merged, log_kind)

    def _merge_tool_payload(self, tool_id: str, update: dict[str, Any]) -> dict[str, Any]:
        if not tool_id:
            return update
        merged = merge_tool_update(self._tool_payloads.get(tool_id, {}), update)
        self._tool_payloads[tool_id] = merged
        return merged

    def _tool_labels(self, tool_id: str, update: dict[str, Any]) -> tuple[str, str, str]:
        """(kind, título, detalhe) de um tool-call, como a tela viva os monta.

        Rotular é acessório ao step: qualquer tropeço aqui cai no `title` cru do
        ACP em vez de derrubar a run.
        """
        try:
            previous = self._tool_kinds.get(tool_id)
            fallback = LogKind(previous) if previous else None
            log_kind, title, detail = build_tool_labels(
                update, cwd=self._cwd, fallback_kind=fallback
            )
            if tool_id and log_kind != LogKind.TOOL:
                self._tool_kinds[tool_id] = log_kind.value
            return log_kind.value, title, detail
        except Exception:
            return "Tool", self._fallback_title(update), self._fallback_detail(update)

    @staticmethod
    def _fallback_title(update: dict[str, Any]) -> str:
        return str(update.get("title") or update.get("kind") or "tool").strip()

    def _fallback_detail(self, update: dict[str, Any]) -> str:
        raw = update.get("rawInput")
        if isinstance(raw, dict):
            for key in (*self._PATH_KEYS, "command", "pattern", "query"):
                value = raw.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return ""

    def _record_artifacts(self, update: dict[str, Any], log_kind: str = "") -> None:
        """Registra o que o tool-call escreveu.

        O `kind` do ACP nem sempre vem — vários runtimes mandam só o nome do
        tool. Por isso vale também a classificação de `build_tool_labels`, que é
        a mesma que faz a aba de artefatos aparecer na sessão viva; sem ela o
        histórico reabria sem nenhum artefato.
        """
        writes = str(update.get("kind") or "").lower() in self._WRITE_KINDS
        if not writes and log_kind not in {"Write", "Edit"}:
            return
        for path in self._artifact_paths(update):
            try:
                from pulse.store.runs import record_artifact

                record_artifact(self._bound_run_id, path, step_id=self._phase_id)
            except Exception:
                # Registrar artefato é acessório: nunca derruba o step.
                pass

    def _artifact_paths(self, update: dict[str, Any]) -> list[str]:
        """Caminhos tocados pelo tool-call, relativos ao workspace.

        A mesma extração da tela viva, para o artefato gravado abrir pela aba do
        histórico: caminho absoluto de outra máquina não resolve arquivo nenhum.
        """
        paths = extract_paths(update, cwd=self._cwd)
        if paths:
            return paths
        found: list[str] = []
        locations = update.get("locations")
        if isinstance(locations, list):
            for item in locations:
                if isinstance(item, dict):
                    value = item.get("path")
                    if isinstance(value, str) and value.strip():
                        found.append(value.strip())
        raw = update.get("rawInput")
        if isinstance(raw, dict):
            for key in self._PATH_KEYS:
                value = raw.get(key)
                if isinstance(value, str) and value.strip():
                    found.append(value.strip())
                    break
        # `locations` e `rawInput` costumam trazer o mesmo arquivo.
        return list(dict.fromkeys(found))

    def _begin_phase(self, label: str) -> None:
        """Abre o passo na tela e deixa a mesma marca no log gravado.

        A tela viva escreve uma linha de info a cada passo (e a cada
        continuação); sem gravá-la, o histórico colava dois turnos num bloco só,
        sem dizer onde um terminou.
        """
        self._flush_text()
        self._stream.begin_phase(label)
        self._save_event(kind="Info", title=label, detail=label)

    def _record_prompt_qa(
        self,
        name: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        result: Any,
    ) -> None:
        """Põe no log da run a pergunta que foi feita e a resposta que veio.

        A tela viva desenha os dois balões ([pulse.tui.state.CockpitState.add_qa]),
        mas quem os desenha não escreve no banco — gravar daqui é o que faz o
        histórico reabrir com o questionário que decidiu o rumo da run, em vez
        de só com a fala do agente e os tools.
        """
        if not self._bound_run_id:
            return
        try:
            pairs = build_prompt_qa(name, args, kwargs, result)
        except Exception as error:  # noqa: BLE001
            # Sem esta linha, um payload que o montador não entende apagaria o
            # diálogo do histórico sem rastro.
            self._save_event(
                kind="Info",
                title="Diálogo não registrado",
                detail=f"{name}: {type(error).__name__}: {error}",
            )
            return
        for question, answer in pairs:
            if not question.strip():
                continue
            # A fala que antecedeu a pergunta vai primeiro, senão ela desceria
            # para debaixo do diálogo no próximo flush.
            self._flush_text()
            self._save_event(kind="Question", title="Pergunta", detail=question)
            self._save_event(kind="Answer", title="Você", detail=answer)

    def _flush_text(self) -> None:
        """Fecha a fala acumulada do agente numa linha do log.

        O bloco de questionário não entra: ele vira dock na tela e balões de
        Pergunta/Você aqui, então gravá-lo cru mostraria as mesmas perguntas
        duas vezes. No lugar dele fica a mesma linha que o cockpit mostra.
        """
        text = "".join(self._text_buffer).strip()
        self._text_buffer.clear()
        if not text:
            return
        spoken, had_questionnaire = strip_questionnaire_block(text)
        if spoken:
            self._save_event(kind="Assistant", title=spoken[:160], detail=spoken)
        if had_questionnaire:
            self._save_event(
                kind="Info",
                title=QUESTIONNAIRE_NOTICE,
                detail=QUESTIONNAIRE_NOTICE,
            )

    def _save_event(self, *, kind: str, title: str, detail: str, tool_id: str = "") -> None:
        try:
            from pulse.store.runs import record_event

            record_event(
                self._bound_run_id,
                step_id=self._phase_id,
                acp_session_id=self._session_id or "",
                kind=kind,
                title=title,
                detail=detail,
                tool_id=tool_id,
            )
        except Exception:
            # Log é acessório: falha ao gravar não pode derrubar o step.
            pass
