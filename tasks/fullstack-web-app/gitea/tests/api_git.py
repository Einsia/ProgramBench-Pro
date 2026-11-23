import base64, hashlib, os, pathlib, subprocess, urllib.parse
from harness import Ref, pathref, b64

# Each file scenario tests a distinct path/content semantic, not just a different name.
FILES = [
    ("ascii", "src/plain.txt", "hello\n"),
    ("nested", "src/deep/nested/config.json", '{"enabled":true,"value":42}\n'),
    ("unicode-path", "docs/你好.md", "# Unicode path\n"),
    ("unicode-content", "docs/unicode.txt", "café Ω العربية 😀\n"),
    ("spaces", "docs/file with spaces.txt", "space path\n"),
    ("plus", "docs/a+b.txt", "plus sign\n"),
    ("percent", "docs/100%.txt", "percent sign\n"),
    ("hash", "docs/a#b.txt", "fragment character\n"),
    (
        "dotfile",
        ".editorconfig",
        "root = true\n[*]\nindent_style = space\nindent_size = 2\n",
    ),
    ("empty", "src/empty.txt", ""),
    ("no-newline", "src/no-newline.txt", "last line"),
    ("crlf", "src/windows.txt", "first\r\nsecond\r\n"),
    ("markdown", "docs/README.md", "# Docs\n\n**bold** [link](https://example.test)\n"),
    ("html", "web/index.html", "<h1>Content</h1><script>text only</script>\n"),
    ("code", "src/main.py", "def answer():\n    return 42\n"),
    (
        "large-lines",
        "src/lines.txt",
        "\n".join(f"line {i:03d}: value {i*i}" for i in range(80)) + "\n",
    ),
]


def build(s):
    a = s.api
    rp = "repos/alice/pbp-git"
    a(
        "git-fixture",
        "main",
        "create",
        "POST",
        "user/repos",
        "alice",
        body={"name": "pbp-git", "auto_init": True, "description": "Git semantics"},
        status=201,
    )
    for sc, path, text in FILES:
        ep = rp + "/contents/" + urllib.parse.quote(path, safe="/")
        key = "file-" + sc
        a(
            "files",
            sc,
            "create",
            "POST",
            ep,
            "alice",
            body={"content": b64(text), "message": "Create " + sc},
            save=key,
            status=201,
        )
        a(
            "files",
            sc,
            "read",
            "GET",
            ep,
            "alice",
            save=key + "-get",
            status=200,
            want={
                "path": path,
                "content": b64(text),
                "encoding": "base64",
                "size": len(text.encode()),
            },
        )
        a(
            "files",
            sc,
            "raw",
            "GET",
            rp + "/raw/" + urllib.parse.quote(path, safe="/"),
            None,
            status=200,
            hint="raw-bytes",
            check=lambda c, r, p, t=text: (
                (_ for _ in ()).throw(AssertionError("raw content mismatch"))
                if r.content != t.encode()
                else None
            ),
        )
        a(
            "files",
            sc,
            "blob",
            "GET",
            pathref(rp + "/git/blobs/{sha}", sha=Ref(key + "-get", "sha")),
            "alice",
            status=200,
            want={
                "content": b64(text),
                "encoding": "base64",
                "size": len(text.encode()),
            },
        )
        changed = text + "\nchanged " + sc + "\n"
        a(
            "files",
            sc,
            "update",
            "PUT",
            ep,
            "alice",
            body={
                "content": b64(changed),
                "sha": Ref(key + "-get", "sha"),
                "message": "Update " + sc,
            },
            save=key + "-updated",
            status=200,
        )
        a(
            "files",
            sc,
            "updated-read",
            "GET",
            ep,
            "alice",
            save=key + "-current",
            status=200,
            want={"content": b64(changed), "size": len(changed.encode())},
        )
        a(
            "files",
            sc,
            "stale-update",
            "PUT",
            ep,
            "alice",
            body={
                "content": b64("stale write"),
                "sha": Ref(key + "-get", "sha"),
                "message": "stale",
            },
        )
        a(
            "files",
            sc,
            "duplicate-create",
            "POST",
            ep,
            "alice",
            body={"content": b64("duplicate"), "message": "duplicate"},
        )
        a(
            "files",
            sc,
            "history",
            "GET",
            rp + "/commits",
            "alice",
            params={"path": path, "limit": 3},
            status=200,
        )
    for sc, body in [
        ("missing-content", {}),
        ("bad-base64", {"content": "!not-base64!"}),
        ("missing-sha", {"content": b64("replacement")}),
        (
            "bad-sha",
            {
                "content": b64("replacement"),
                "sha": "0000000000000000000000000000000000000000",
            },
        ),
        ("missing-branch", {"content": b64("replacement"), "branch": "does-not-exist"}),
    ]:
        a(
            "files-validation",
            sc,
            "update",
            "PUT",
            rp + "/contents/src/plain.txt",
            "alice",
            body=body,
        )
    for sc, path in [
        ("absolute", "/outside.txt"),
        ("gitdir", ".git/config"),
        ("empty", ""),
    ]:
        a(
            "files-path-validation",
            sc,
            "create",
            "POST",
            rp + "/contents/" + urllib.parse.quote(path, safe="/"),
            "alice",
            body={"content": b64("unsafe path"), "message": "path validation"},
        )
    for path in (
        "",
        "src",
        "src/deep",
        "src/deep/nested",
        "docs",
        "missing",
        "src/plain.txt/child",
    ):
        a(
            "directory-listing",
            path.replace("/", "-") or "root",
            "read",
            "GET",
            rp + "/contents" + ("/" + path if path else ""),
            "alice",
        )
    a(
        "git-objects",
        "head",
        "branch",
        "GET",
        rp + "/branches/main",
        "alice",
        save="git-head",
        status=200,
    )
    a(
        "git-objects",
        "head",
        "commit",
        "GET",
        pathref(rp + "/git/commits/{sha}", sha=Ref("git-head", "commit", "id")),
        "alice",
        save="git-commit",
        status=200,
    )
    a(
        "git-objects",
        "head",
        "tree",
        "GET",
        pathref(
            rp + "/git/trees/{sha}", sha=Ref("git-commit", "commit", "tree", "sha")
        ),
        "alice",
        save="git-tree",
        status=200,
    )
    for recursive in (False, True):
        for page in (1, 2, 9):
            a(
                "git-tree",
                "recursive-" + str(recursive) + "-page-" + str(page),
                "query",
                "GET",
                pathref(
                    rp + "/git/trees/{sha}",
                    sha=Ref("git-commit", "commit", "tree", "sha"),
                ),
                "alice",
                params={"recursive": recursive, "per_page": 5, "page": page},
                status=200,
            )
    for endpoint in (
        "git/refs",
        "git/refs/heads",
        "git/refs/heads/main",
        "git/refs/heads/absent",
        "commits",
        "languages",
        "editorconfig/src/main.py",
    ):
        a(
            "git-objects",
            endpoint.replace("/", "-"),
            "read",
            "GET",
            rp + "/" + endpoint,
            "alice",
        )
    for page, limit in [
        (1, 1),
        (2, 1),
        (1, 5),
        (2, 5),
        (100, 5),
        (0, 3),
        (-1, 3),
        (1, 0),
        (1, 50),
    ]:
        a(
            "commit-pagination",
            f"p{page}-l{limit}",
            "list",
            "GET",
            rp + "/commits",
            "alice",
            params={"page": page, "limit": limit},
            status=200,
        )
    # Branch names include hierarchical refs and syntactic rejection boundaries.
    branches = [
        ("feature", "feature"),
        ("hierarchy", "feature/nested"),
        ("unicode", "开发"),
        ("dot", "release.1"),
        ("dash", "fix-hyphen"),
        ("space", "bad branch"),
        ("dotdot", "a..b"),
        ("lock", "name.lock"),
        ("trailing-slash", "trailing/"),
        ("head", "HEAD"),
    ]
    for sc, name in branches:
        a(
            "branches",
            sc,
            "create",
            "POST",
            rp + "/branches",
            "alice",
            body={"new_branch_name": name, "old_branch_name": "main"},
            save="branch-" + sc,
        )
        a(
            "branches",
            sc,
            "read",
            "GET",
            rp + "/branches/" + urllib.parse.quote(name, safe=""),
            "alice",
        )
        a(
            "branches",
            sc,
            "duplicate",
            "POST",
            rp + "/branches",
            "alice",
            body={"new_branch_name": name, "old_branch_name": "main"},
        )
        if sc in ("feature", "hierarchy", "unicode", "dot", "dash"):
            ep = rp + "/contents/branch-" + sc + ".txt"
            a(
                "branches",
                sc,
                "isolated-write",
                "POST",
                ep,
                "alice",
                body={
                    "branch": name,
                    "content": b64("on " + name),
                    "message": "Branch-only file",
                },
                status=201,
            )
            a(
                "branches",
                sc,
                "file-on-branch",
                "GET",
                ep,
                "alice",
                params={"ref": name},
                status=200,
            )
            a(
                "branches",
                sc,
                "absent-on-main",
                "GET",
                ep,
                "alice",
                params={"ref": "main"},
                status=404,
            )
            a(
                "branches",
                sc,
                "compare",
                "GET",
                rp + "/compare/main..." + urllib.parse.quote(name, safe=""),
                "alice",
                status=200,
            )
            a(
                "branches",
                sc,
                "delete",
                "DELETE",
                rp + "/branches/" + urllib.parse.quote(name, safe=""),
                "alice",
                status=204,
            )
            a(
                "branches",
                sc,
                "gone",
                "GET",
                rp + "/branches/" + urllib.parse.quote(name, safe=""),
                "alice",
                status=404,
            )
    a("branches", "default", "cannot-delete", "DELETE", rp + "/branches/main", "alice")
    a(
        "branches",
        "missing-source",
        "create",
        "POST",
        rp + "/branches",
        "alice",
        body={"new_branch_name": "pbp-no-source", "old_branch_name": "missing"},
    )
    tags = [
        ("simple", "v1.0.0", ""),
        ("annotated", "v2.0.0", "Release notes\nsecond line"),
        ("hierarchy", "release/stable", "stable branch"),
        ("unicode", "版本-一", "Unicode tag"),
        ("space", "bad tag", "invalid"),
        ("dotdot", "a..b", "invalid"),
    ]
    for sc, name, msg in tags:
        if sc in ("space", "dotdot"):
            a(
                "tag-invalid-read",
                sc,
                "missing",
                "GET",
                rp + "/tags/" + urllib.parse.quote(name, safe=""),
                "alice",
                status=404,
            )
            continue
        a(
            "tags",
            sc,
            "create",
            "POST",
            rp + "/tags",
            "alice",
            body={"tag_name": name, "target": "main", "message": msg},
            save="tag-" + sc,
        )
        a(
            "tags",
            sc,
            "read",
            "GET",
            rp + "/tags/" + urllib.parse.quote(name, safe=""),
            "alice",
        )
        a(
            "tags",
            sc,
            "duplicate",
            "POST",
            rp + "/tags",
            "alice",
            body={"tag_name": name, "target": "main"},
        )
        if sc not in ("space", "dotdot"):
            a(
                "tags",
                sc,
                "contents",
                "GET",
                rp + "/contents/src/plain.txt",
                "alice",
                params={"ref": name},
                status=200,
            )
            a(
                "tags",
                sc,
                "delete",
                "DELETE",
                rp + "/tags/" + urllib.parse.quote(name, safe=""),
                "alice",
                status=204,
            )
            a(
                "tags",
                sc,
                "gone",
                "GET",
                rp + "/tags/" + urllib.parse.quote(name, safe=""),
                "alice",
                status=404,
            )

    # Git HTTP actually invokes git, so implementing JSON alone cannot pass these cases.
    def gitcase(sc, args, actor="alice", check=None):
        def action(c):
            work = c.work / "pbp-git-client"
            work.mkdir(exist_ok=True)
            env = os.environ.copy()
            env.update(
                GIT_CONFIG_NOSYSTEM="1",
                GIT_TERMINAL_PROMPT="0",
                GIT_CONFIG_GLOBAL=str(work / "empty-config"),
            )
            url = (
                c.git_base.replace(
                    "://", f'://{actor}:{urllib.parse.quote(c.creds[actor],safe="")}@'
                )
                + "/alice/pbp-git.git"
            )
            argv = [
                "git",
                *[
                    (
                        url
                        if x == "@url"
                        else str(work / "clone") if x == "@clone" else x
                    )
                    for x in args
                ],
            ]
            r = subprocess.run(argv, env=env, capture_output=True, timeout=35)
            assert (
                r.returncode == 0
            ), f'git {args[0]} failed: {r.stderr.decode(errors="replace")[:500]}'
            if check:
                check(c, work, r)
            return {
                "success": True,
                "output": c.norm.text(
                    r.stdout.decode(errors="replace"), scope="alice/pbp-git"
                ),
            }

        s.add("git-http", sc, "transport", action, channel="git")

    gitcase("advertise", ["ls-remote", "--heads", "@url"])

    def clone_contents(c, work, result):
        for scenario, path, original in FILES:
            expected = (original + "\nchanged " + scenario + "\n").encode()
            assert (
                work / "clone" / path
            ).read_bytes() == expected, "clone file bytes differ: " + path

    gitcase(
        "clone",
        ["clone", "--quiet", "@url", "@clone"],
        check=clone_contents,
    )
    gitcase("log", ["-C", "@clone", "log", "-3", "--format=%s"])
    gitcase("tracked-paths", ["-C", "@clone", "ls-files"])
    # Deletions have their own post-state and stale-SHA boundary.
    for sc, path, text in FILES[:8]:
        ep = rp + "/contents/" + urllib.parse.quote(path, safe="/")
        a(
            "file-delete",
            sc,
            "stale",
            "DELETE",
            ep,
            "alice",
            body={"sha": Ref("file-" + sc + "-get", "sha"), "message": "stale delete"},
        )
        a(
            "file-delete",
            sc,
            "delete",
            "DELETE",
            ep,
            "alice",
            body={
                "sha": Ref("file-" + sc + "-current", "sha"),
                "message": "Remove " + sc,
            },
            status=200,
        )
        a("file-delete", sc, "gone", "GET", ep, "alice", status=404)
