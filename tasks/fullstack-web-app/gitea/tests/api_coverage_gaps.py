"""High-value authorization and transport enforcement episodes.

These cases exercise behavior that DTO-only permission/configuration tests cannot
prove: scoped tokens against real resources, private organization team units and
revocation, anonymous Git transport isolation, branch protection enforcement, and
repository feature switches.
"""

import base64
import os
import pathlib
import subprocess
import urllib.parse

from harness import Ref, b64, pathref


def git_url(c, owner, repo, actor=None):
    auth = ""
    if actor:
        auth = f'{actor}:{urllib.parse.quote(c.creds[actor], safe="")}@'
    return c.git_base.replace("://", "://" + auth) + f"/{owner}/{repo}.git"


def git_run(c, owner, repo, actor, args, directory=None):
    env = os.environ.copy()
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_TERMINAL_PROMPT="0",
        GIT_CONFIG_GLOBAL=str(c.work / "gap-git-empty-config"),
    )
    argv = [
        "git",
        *(["-C", str(directory)] if directory else []),
        *[
            git_url(c, owner, repo, actor) if x == "@url" else x
            for x in args
        ],
    ]
    return subprocess.run(argv, env=env, capture_output=True, timeout=35)


def build(s):
    a = s.api

    # Scoped token fixture: the token owner has write access to one private repo,
    # while a read-only token must not mutate it.
    private = "repos/alice/pbp-gap-token-private"
    public = "repos/alice/pbp-gap-token-public"
    a(
        "token-gap-fixture",
        "private-repo",
        "create",
        "POST",
        "user/repos",
        "alice",
        body={"name": "pbp-gap-token-private", "private": True, "auto_init": True},
        status=201,
    )
    a(
        "token-gap-fixture",
        "public-repo",
        "create",
        "POST",
        "user/repos",
        "alice",
        body={"name": "pbp-gap-token-public", "auto_init": True},
        status=201,
    )
    for rp in (private, public):
        a(
            "token-gap-fixture",
            rp.rsplit("/", 1)[1],
            "file",
            "POST",
            rp + "/contents/token-gap.txt",
            "alice",
            body={"content": b64("token fixture\n"), "message": "Token fixture"},
            status=201,
        )
    a(
        "token-gap-fixture",
        "private-permission",
        "grant",
        "PUT",
        private + "/collaborators/bob",
        "alice",
        body={"permission": "write"},
        status=204,
    )
    for name, scopes in (
        ("read", ["read:repository"]),
        ("write", ["write:repository"]),
    ):
        a(
            "token-gap-fixture",
            "token-" + name,
            "create",
            "POST",
            "users/bob/tokens",
            "bob",
            body={"name": "pbp-gap-token-" + name, "scopes": scopes},
            save="gap-token-" + name,
            status=201,
            hint="token",
        )
    a(
        "token-gap",
        "read-public",
        "repository",
        "GET",
        public,
        "token:gap-token-read",
        status=200,
    )
    a(
        "token-gap",
        "read-public",
        "file",
        "GET",
        public + "/contents/token-gap.txt",
        "token:gap-token-read",
        status=200,
    )
    def denied_write_before(c):
        rr, _ = c.request("GET", private + "/contents/read-token.txt", "alice")
        assert rr.status_code == 404, "denied write fixture path already exists"
        rr, branch = c.request("GET", private + "/branches/main", "alice")
        assert rr.status_code == 200, "trusted branch snapshot unavailable"
        c.state["gap-denied-write-head"] = branch["commit"]["id"]

    def denied_write_unchanged(c, _response, _payload):
        rr, _ = c.request("GET", private + "/contents/read-token.txt", "alice")
        assert rr.status_code == 404, "rejected token write still created its file"
        rr, branch = c.request("GET", private + "/branches/main", "alice")
        assert rr.status_code == 200 and branch["commit"]["id"] == c.state["gap-denied-write-head"], (
            "rejected token write changed the repository branch"
        )

    a(
        "token-gap",
        "read-private",
        "repository",
        "GET",
        private,
        "token:gap-token-read",
        status=200,
    )
    a(
        "token-gap",
        "read-private",
        "write-denied",
        "POST",
        private + "/contents/read-token.txt",
        "token:gap-token-read",
        body={"content": b64("must be denied"), "message": "Read token write"},
        status=[403, 404],
        before=denied_write_before,
        check=denied_write_unchanged,
    )
    a(
        "token-gap",
        "write-private",
        "write-allowed",
        "POST",
        private + "/contents/write-token.txt",
        "token:gap-token-write",
        body={"content": b64("write token\n"), "message": "Write token write"},
        status=201,
    )
    a(
        "token-gap",
        "write-private",
        "read-after-write",
        "GET",
        private + "/contents/write-token.txt",
        "token:gap-token-write",
        status=200,
    )
    a(
        "token-gap",
        "read-revocation",
        "revoke",
        "DELETE",
        pathref("users/bob/tokens/{id}", id=Ref("gap-token-read", "id")),
        "bob",
        status=204,
    )
    a(
        "token-gap",
        "read-revocation",
        "denied-after-revoke",
        "GET",
        public,
        "token:gap-token-read",
        status=401,
    )

    # Public/private smart-HTTP behavior is independent of the JSON API.
    a(
        "git-gap-fixture",
        "public-repo",
        "create",
        "POST",
        "user/repos",
        "alice",
        body={"name": "pbp-gap-git-public", "auto_init": True},
        status=201,
    )
    a(
        "git-gap-fixture",
        "public-file",
        "create",
        "POST",
        "repos/alice/pbp-gap-git-public/contents/visible.txt",
        "alice",
        body={"content": b64("anonymous Git read\n"), "message": "Public Git fixture"},
        status=201,
    )
    a(
        "git-gap-fixture",
        "private-repo",
        "create",
        "POST",
        "user/repos",
        "alice",
        body={"name": "pbp-gap-git-private", "private": True, "auto_init": True},
        status=201,
    )

    def anonymous_clone(c):
        work = c.work / "gap-anonymous-git"
        work.mkdir()
        result = git_run(
            c,
            "alice",
            "pbp-gap-git-public",
            None,
            ["clone", "--quiet", "@url", str(work / "public")],
        )
        assert result.returncode == 0, result.stderr.decode(errors="replace")[:500]
        assert (work / "public/visible.txt").read_bytes() == b"anonymous Git read\n"
        return {"anonymous_public_clone": True, "content": "anonymous Git read\n"}

    s.add("git-gap", "anonymous-public", "clone", anonymous_clone, channel="git")

    def anonymous_private(c):
        work = c.work / "gap-anonymous-git"
        result = git_run(
            c,
            "alice",
            "pbp-gap-git-private",
            None,
            ["ls-remote", "@url"],
        )
        assert result.returncode != 0, "anonymous private Git metadata was exposed"
        clone = git_run(
            c,
            "alice",
            "pbp-gap-git-private",
            None,
            ["clone", "--quiet", "@url", str(work / "private")],
        )
        assert clone.returncode != 0, "anonymous private Git clone was allowed"
        return {"anonymous_private_denied": True}

    s.add("git-gap", "anonymous-private", "denied", anonymous_private, channel="git")

    # Private organization team unit enforcement and revocation.
    org = "pbp-gap-org"
    repo = "pbp-gap-org-private"
    op = "orgs/" + org
    rp = "repos/" + org + "/" + repo
    a(
        "team-gap-fixture",
        "org",
        "create",
        "POST",
        "orgs",
        "alice",
        body={"username": org, "visibility": "private"},
        status=201,
    )
    a(
        "team-gap-fixture",
        "repo",
        "create",
        "POST",
        op + "/repos",
        "alice",
        body={"name": repo, "private": True, "auto_init": True},
        status=201,
    )
    a(
        "team-gap-fixture",
        "file",
        "create",
        "POST",
        rp + "/contents/team.txt",
        "alice",
        body={"content": b64("team private\n"), "message": "Team fixture"},
        status=201,
    )
    a(
        "team-gap-fixture",
        "team",
        "create",
        "POST",
        op + "/teams",
        "alice",
        body={"name": "private-code-reader", "permission": "read", "units": ["repo.code"]},
        save="gap-team",
        status=201,
    )
    team_ep = pathref("teams/{id}", id=Ref("gap-team", "id"))
    a("team-gap-fixture", "member", "add", "PUT", lambda c: team_ep(c) + "/members/bob", "alice", status=204)
    a("team-gap-fixture", "repo", "add", "PUT", lambda c: team_ep(c) + "/repos/" + org + "/" + repo, "alice", status=204)
    a("team-gap", "private-code", "read", "GET", rp + "/contents/team.txt", "bob", status=200)
    a(
        "team-gap",
        "private-code",
        "issue-denied",
        "POST",
        rp + "/issues",
        "bob",
        body={"title": "Unit must deny issues"},
        status=[403, 404],
    )
    a("team-gap", "private-code", "remove-repo", "DELETE", lambda c: team_ep(c) + "/repos/" + org + "/" + repo, "alice", status=204)
    a("team-gap", "private-code", "read-after-repo-revoke", "GET", rp + "/contents/team.txt", "bob", status=[403, 404])
    a("team-gap", "private-code", "add-repo-again", "PUT", lambda c: team_ep(c) + "/repos/" + org + "/" + repo, "alice", status=204)
    a("team-gap", "private-code", "remove-member", "DELETE", lambda c: team_ep(c) + "/members/bob", "alice", status=204)
    a("team-gap", "private-code", "read-after-member-revoke", "GET", rp + "/contents/team.txt", "bob", status=[403, 404])
