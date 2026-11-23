"""Bounded Git-over-HTTP writes and permission enforcement using a real client."""

import base64, os, pathlib, subprocess, urllib.parse
from harness import b64
from reference.registry import add


def git(c, directory, args, actor="bob", success=True):
    env = os.environ.copy()
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_TERMINAL_PROMPT="0",
        GIT_CONFIG_GLOBAL=str(c.work / "pbp-git-write-empty-config"),
    )
    url = (
        c.git_base.replace(
            "://", f'://{actor}:{urllib.parse.quote(c.creds[actor],safe="")}@'
        )
        + "/alice/pbp-git-write.git"
    )
    cmd = [
        "git",
        "-c",
        "user.name=Bob Writer",
        "-c",
        "user.email=bob@example.test",
        *(["-C", str(directory)] if directory else []),
        *[url if x == "@url" else x for x in args],
    ]
    result = subprocess.run(cmd, env=env, capture_output=True, timeout=35)
    assert (result.returncode == 0) if success else (result.returncode != 0), (
        "Git transport permission/result differs: "
        + result.stderr.decode(errors="replace")[:500]
    )
    return result


def observe_branch(c, expected, previous=None):
    rp = "repos/alice/pbp-git-write"
    r, branch = c.request("GET", rp + "/branches/transport", "alice")
    assert r.status_code == 200
    if previous:
        assert branch["commit"]["id"] == previous, "denied push changed branch ref"
    r, obj = c.request(
        "GET", rp + "/contents/transport.txt", "alice", params={"ref": "transport"}
    )
    assert (
        r.status_code == 200 and base64.b64decode(obj["content"]) == expected.encode()
    ), "pushed file bytes differ"
    local = c.state["git-write-head"]
    assert (
        branch["commit"]["id"] == local
    ), "API branch differs from actual pushed commit"
    return {
        "head": c.norm.text(local, scope="alice/pbp-git-write"),
        "content": expected,
        "ref": "transport",
    }


def build(s):
    a = s.api
    rp = "repos/alice/pbp-git-write"
    a(
        "git-write-fixture",
        "private",
        "repository",
        "POST",
        "user/repos",
        "alice",
        body={"name": "pbp-git-write", "private": True, "auto_init": True},
        status=201,
    )
    for actor, permission in [("bob", "write"), ("carol", "read")]:
        a(
            "git-write-fixture",
            actor,
            "grant",
            "PUT",
            rp + "/collaborators/" + actor,
            "alice",
            body={"permission": permission},
            status=204,
        )

    def push(c):
        work = c.work / "pbp-git-write-client"
        work.mkdir()
        clone = work / "writer"
        git(c, None, ["clone", "--quiet", "@url", str(clone)])
        git(c, clone, ["checkout", "--quiet", "-b", "transport"])
        (clone / "transport.txt").write_text("pushed first version\n")
        git(c, clone, ["add", "transport.txt"])
        git(c, clone, ["commit", "--quiet", "-m", "Create through Git HTTP"])
        git(c, clone, ["push", "--quiet", "@url", "HEAD:refs/heads/transport"])
        c.state["git-write-head"] = (
            git(c, clone, ["rev-parse", "HEAD"]).stdout.decode().strip()
        )
        return observe_branch(c, "pushed first version\n")

    s.add("git-write", "writer", "create-branch", push, channel="git")
    a(
        "git-write",
        "isolated-main",
        "absent",
        "GET",
        rp + "/contents/transport.txt",
        "alice",
        params={"ref": "main"},
        status=404,
    )

    def update(c):
        clone = c.work / "pbp-git-write-client/writer"
        (clone / "transport.txt").write_text("pushed second version café\n")
        git(c, clone, ["add", "transport.txt"])
        git(c, clone, ["commit", "--quiet", "-m", "Update through Git HTTP"])
        git(c, clone, ["push", "--quiet", "@url", "HEAD:refs/heads/transport"])
        c.state["git-write-head"] = (
            git(c, clone, ["rev-parse", "HEAD"]).stdout.decode().strip()
        )
        return observe_branch(c, "pushed second version café\n")

    s.add("git-write", "writer", "update-branch", update, channel="git")

    def reader(c):
        clone = c.work / "pbp-git-write-client/reader"
        git(
            c,
            None,
            ["clone", "--quiet", "--branch", "transport", "@url", str(clone)],
            "carol",
        )
        (clone / "transport.txt").write_text("unauthorized replacement\n")
        git(c, clone, ["add", "transport.txt"], "carol")
        git(c, clone, ["commit", "--quiet", "-m", "Forbidden reader write"], "carol")
        previous = c.state["git-write-head"]
        git(
            c,
            clone,
            ["push", "--quiet", "@url", "HEAD:refs/heads/transport"],
            "carol",
            False,
        )
        return {
            "write_denied": True,
            **observe_branch(c, "pushed second version café\n", previous),
        }

    s.add("git-write", "reader", "denied-push", reader, channel="git")

    def fresh(c):
        clone = c.work / "pbp-git-write-client/fresh"
        git(
            c,
            None,
            ["clone", "--quiet", "--branch", "transport", "@url", str(clone)],
            "carol",
        )
        assert (
            clone / "transport.txt"
        ).read_bytes() == "pushed second version café\n".encode()
        assert (
            git(c, clone, ["rev-parse", "HEAD"], "carol").stdout.decode().strip()
            == c.state["git-write-head"]
        )
        git(c, clone, ["fsck", "--full", "--no-reflogs"], "carol")
        log = git(c, clone, ["log", "-2", "--format=%s"], "carol").stdout.decode()
        assert log == "Update through Git HTTP\nCreate through Git HTTP\n"
        return {
            "fresh_clone_content": "pushed second version café\n",
            "commit_messages": log,
            "git_objects_valid": True,
        }

    s.add("git-write", "reader", "fresh-clone", fresh, channel="git")
    a(
        "git-write",
        "private",
        "anonymous-denied",
        "GET",
        rp + "/contents/transport.txt",
        None,
        params={"ref": "transport"},
        status=404,
    )

    def visible(c, ui):
        p, status = ui.goto(
            "/alice/pbp-git-write/src/branch/transport/transport.txt", "carol"
        )
        assert status == 200
        ui.require(p, "pushed second version café")
        return {"content_visible": "pushed second version café", "reader": True}

    add(s, "git-write", "reader", "browser-content", visible)
