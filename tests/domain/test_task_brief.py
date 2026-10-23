from __future__ import annotations

from pulse.domain.task_brief import TaskBrief


def test_the_prompt_joins_title_and_description_as_paragraphs():
    """Agents read the task as one text; the title leads it."""
    brief = TaskBrief(title="  Fix login  ", description="\nError 500 on upper-case e-mails\n")

    assert brief.title == "Fix login"
    assert brief.description == "Error 500 on upper-case e-mails"
    assert brief.prompt == "Fix login\n\nError 500 on upper-case e-mails"


def test_a_missing_part_leaves_no_blank_paragraph():
    assert TaskBrief(title="Fix login").prompt == "Fix login"
    assert TaskBrief(description="only details").prompt == "only details"


def test_a_brief_of_blanks_is_empty():
    assert TaskBrief(title="  ", description="\n").is_empty
    assert TaskBrief().prompt == ""
    assert not TaskBrief(title="x").is_empty
    assert not TaskBrief(description="x").is_empty
