from pathlib import Path

from pulse.plan.spec_prompt import ROUTE_RELATIVE_PATH, build_classify_prompt, route_file
from pulse.plan.spec_route import load_route, parse_route_text


def test_parse_route_text_accepts_aliases_and_fences():
    assert parse_route_text("flow: quick\nreason: bug pontual\n") == ("quick", "bug pontual")
    assert parse_route_text("flow: full\nreason: nova feature\n") == ("full", "nova feature")
    assert parse_route_text("```yaml\nflow: fix-bug\nreason: token\n```") == ("quick", "token")
    assert parse_route_text("flow: new-issue\nreason: auth\n") == ("full", "auth")
    assert parse_route_text("flow: nope\n") is None
    assert parse_route_text("not yaml") is None


def test_load_route_reads_workspace_file(tmp_path: Path):
    path = route_file(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("flow: quick\nreason: <=3 files\n", encoding="utf-8")
    assert load_route(tmp_path) == ("quick", "<=3 files")
    assert ROUTE_RELATIVE_PATH in str(path)


def test_classify_prompt_asks_for_route_file(tmp_path: Path):
    prompt = build_classify_prompt(
        workspace=tmp_path,
        user_prompt="Corrigir botão",
        skill_dir=tmp_path,
    )
    assert "Corrigir botão" in prompt
    assert ".route.yaml" in prompt
    assert "flow: quick" in prompt
    assert "Não" in prompt
    assert "implemente" in prompt.lower()
