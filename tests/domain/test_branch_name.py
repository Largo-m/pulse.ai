from pulse.domain.branch_name import task_slug, worktree_folder


def test_a_task_becomes_a_kebab_case_branch_name():
    assert task_slug("Corrigir o login!") == "corrigir-o-login"


def test_accents_drop_out_of_the_slug():
    assert task_slug("Ação rápida") == "acao-rapida"


def test_a_task_with_no_safe_character_has_no_slug():
    assert task_slug("???") == ""


def test_a_branch_with_a_slash_becomes_a_single_folder():
    """A `/` would nest the worktree in a subfolder the cleanup never looks at."""
    assert worktree_folder("feat/fix-login") == "feat-fix-login"


def test_every_slash_of_the_branch_becomes_a_dash():
    assert worktree_folder("a/b/c") == "a-b-c"


def test_a_branch_without_a_slash_keeps_its_name_as_the_folder():
    assert worktree_folder("corrigir-o-login") == "corrigir-o-login"
