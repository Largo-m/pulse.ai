from pulse.domain.branch_name import task_slug, worktree_folders


def test_a_task_becomes_a_kebab_case_branch_name():
    assert task_slug("Corrigir o login!") == "corrigir-o-login"


def test_accents_drop_out_of_the_slug():
    assert task_slug("Ação rápida") == "acao-rapida"


def test_a_task_with_no_safe_character_has_no_slug():
    assert task_slug("???") == ""


def test_a_branch_with_a_slash_becomes_a_single_folder():
    """A `/` would nest the worktree in a subfolder the cleanup never looks at."""
    folder, _fallback = worktree_folders("feat/fix-login", "run-aaaaaaaa")
    assert folder == "feat-fix-login"


def test_every_slash_of_the_branch_becomes_a_dash():
    folder, _fallback = worktree_folders("a/b/c", "run-aaaaaaaa")
    assert folder == "a-b-c"


def test_a_branch_without_a_slash_keeps_its_name_as_the_folder():
    folder, _fallback = worktree_folders("corrigir-o-login", "run-aaaaaaaa")
    assert folder == "corrigir-o-login"


def test_the_fallback_folder_adds_the_short_run_id():
    """`feat/x` and `feat-x` map to one folder; the run id keeps the second apart."""
    _folder, fallback = worktree_folders("feat/x", "0123456789abcdef")
    assert fallback == "feat-x-01234567"
