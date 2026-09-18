from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from pulse.plan.analyze_codebase_flow import run_analyze_codebase
from pulse.plan.new_issue_flow import run_new_issue
from pulse.plan.quick_flow import run_quick
from pulse.plan.setup_project_flow import run_setup_project
from pulse.plan.spec_types import get_spec_type


def run_plan(
    *,
    spec_type_id: str,
    user_prompt: str,
    workspace: Path | None = None,
    stream: Any | None = None,
    prompt_handler: Any | None = None,
    render_header: bool = True,
) -> int:
    kwargs: dict[str, Any] = {
        "user_prompt": user_prompt,
        "workspace": workspace,
        "stream": stream,
        "prompt_handler": prompt_handler,
        "render_header": render_header,
    }

    if spec_type_id == "setup-project":
        return run_setup_project(**kwargs)

    if spec_type_id == "analyze-codebase":
        return run_analyze_codebase(**kwargs)

    if spec_type_id == "fix-bug":
        return run_quick(**kwargs)

    if spec_type_id == "new-issue":
        return run_new_issue(**kwargs)

    spec_type = get_spec_type(spec_type_id)
    label = spec_type.label if spec_type else spec_type_id
    print(
        f"[pulse] Pipeline '{label}' ainda não implementado.\n"
        f"[pulse] Prompt: {user_prompt}",
        file=sys.stderr,
    )
    return 2
