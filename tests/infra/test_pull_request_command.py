import pytest

from pulse.vcs.publish import forge_of, request_command


@pytest.mark.parametrize(
    ("url", "forge"),
    [
        ("git@github.com:acme/app.git", "github"),
        ("https://github.com/acme/app.git", "github"),
        ("https://gitlab.com/acme/app.git", "gitlab"),
        ("git@gitlab.example.com:acme/app.git", "gitlab"),
        ("https://git.internal.example/acme/app.git", ""),
    ],
)
def test_the_forge_comes_from_the_origin_url(url: str, forge: str):
    assert forge_of(url) == forge


def test_a_self_hosted_gitlab_matches_the_host_glab_already_uses():
    url = "https://git.internal.example/acme/app.git"
    assert forge_of(url, glab_host="git.internal.example") == "gitlab"


def test_github_and_gitlab_get_the_same_title_and_body():
    body = "#### Descrição:\ncorrigir o login\n"
    github = request_command(
        forge="github", branch="corrigir-o-login", base="main", title="corrigir-o-login", body=body
    )
    gitlab = request_command(
        forge="gitlab", branch="corrigir-o-login", base="main", title="corrigir-o-login", body=body
    )

    assert github[:3] == ["gh", "pr", "create"]
    assert "--body" in github
    assert body in github
    assert gitlab[:3] == ["glab", "mr", "create"]
    assert "--description" in gitlab
    assert body in gitlab
    assert "--force" not in github
    assert "--force" not in gitlab
