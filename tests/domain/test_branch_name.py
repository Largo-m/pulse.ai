from pulse.domain.branch_name import task_slug


def test_a_task_becomes_a_kebab_case_branch_name():
    assert task_slug("Corrigir o login!") == "corrigir-o-login"


def test_accents_drop_out_of_the_slug():
    assert task_slug("Ação rápida") == "acao-rapida"


def test_a_task_with_no_safe_character_has_no_slug():
    assert task_slug("???") == ""
