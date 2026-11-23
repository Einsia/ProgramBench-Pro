import urllib.parse
from harness import Ref, pathref, b64


def build(s):
    a = s.api
    rp = "repos/alice/pbp-publish"
    a(
        "publishing-fixture",
        "public",
        "repository",
        "POST",
        "user/repos",
        "alice",
        body={"name": "pbp-publish", "auto_init": True},
        status=201,
    )
    a(
        "publishing-fixture",
        "public",
        "writer",
        "PUT",
        rp + "/collaborators/bob",
        "alice",
        body={"permission": "write"},
        status=204,
    )
    scenarios = [
        ("stable", False, False),
        ("prerelease", False, True),
        ("draft", True, False),
        ("draft-prerelease", True, True),
    ]
    for sc, draft, pre in scenarios:
        key = "release-" + sc
        tag = "v-" + sc
        a(
            "releases",
            sc,
            "create",
            "POST",
            rp + "/releases",
            "alice",
            body={
                "tag_name": tag,
                "target_commitish": "main",
                "name": "Release " + sc,
                "body": "Notes **" + sc + "**\n\n- item",
                "draft": draft,
                "prerelease": pre,
            },
            save=key,
            status=201,
        )
        ep = pathref(rp + "/releases/{id}", id=Ref(key, "id"))
        for actor in ("alice", "bob", "carol", None):
            a(
                "release-visibility",
                sc + "-" + (actor or "anonymous"),
                "read",
                "GET",
                ep,
                actor,
            )
            a(
                "release-visibility",
                sc + "-" + (actor or "anonymous"),
                "by-tag",
                "GET",
                rp + "/releases/tags/" + tag,
                actor,
            )
        a(
            "releases",
            sc,
            "edit",
            "PATCH",
            ep,
            "bob",
            body={"name": "Edited release " + sc, "body": "Updated notes " + sc},
            status=200,
        )
        a("releases", sc, "after-edit", "GET", ep, "alice", status=200)
        a(
            "releases",
            sc,
            "outsider-edit",
            "PATCH",
            ep,
            "carol",
            body={"name": "forbidden"},
        )
        a(
            "releases",
            sc,
            "duplicate-tag",
            "POST",
            rp + "/releases",
            "alice",
            body={"tag_name": tag, "name": "duplicate"},
        )
    for actor in ("alice", "bob", "carol", None):
        for sc, params in [
            ("all", {}),
            ("draft", {"draft": True}),
            ("published", {"draft": False}),
            ("prerelease", {"pre-release": True}),
            ("stable", {"pre-release": False}),
            ("first-page", {"page": 1, "limit": 2}),
            ("second-page", {"page": 2, "limit": 2}),
            ("empty-page", {"page": 99, "limit": 2}),
        ]:
            a(
                "release-query",
                (actor or "anonymous") + "-" + sc,
                "list",
                "GET",
                rp + "/releases",
                actor,
                params=params,
            )
        a(
            "release-latest",
            actor or "anonymous",
            "read",
            "GET",
            rp + "/releases/latest",
            actor,
        )
    for sc, body in [
        ("no-tag", {"name": "No tag"}),
        ("missing-target", {"tag_name": "v-absent", "target_commitish": "missing"}),
    ]:
        a(
            "release-validation",
            sc,
            "create",
            "POST",
            rp + "/releases",
            "alice",
            body=body,
        )
    for sc, filename, content, mime in [
        ("text", "notes.txt", b"attachment text\n", "text/plain"),
        ("binary", "blob.bin", bytes(range(256)), "application/octet-stream"),
        ("unicode", "release-cafe.txt", "café 工具".encode(), "text/plain"),
    ]:

        def upload(c, sc=sc, filename=filename, content=content, mime=mime):
            rid = c.state["release-stable"]["id"]
            r, p = c.request(
                "POST",
                f"{rp}/releases/{rid}/assets",
                "alice",
                params={"name": filename},
                files={"attachment": (filename, content, mime)},
            )
            assert r.status_code == 201, (r.status_code, p)
            c.state["asset-" + sc] = p
            return c.observe(r, p, "asset")

        s.add("release-assets", sc, "upload", upload)
        ep = pathref(
            rp + "/releases/{rid}/assets/{id}",
            rid=Ref("release-stable", "id"),
            id=Ref("asset-" + sc, "id"),
        )
        a("release-assets", sc, "metadata", "GET", ep, "alice", status=200)

        def download(c, sc=sc, content=content):
            url = c.state["asset-" + sc]["browser_download_url"]
            path = c.local_resource_path(url)
            r = c.get_raw(path)
            assert r.status_code == 200
            assert r.content == content, "asset bytes mismatch"
            return {
                "status": 200,
                "content_base64": __import__("base64").b64encode(r.content).decode(),
            }

        s.add("release-assets", sc, "download", download)
        a(
            "release-assets",
            sc,
            "rename",
            "PATCH",
            ep,
            "alice",
            body={"name": "renamed-" + filename},
            status=201,
        )
        a(
            "release-assets",
            sc,
            "list",
            "GET",
            pathref(rp + "/releases/{id}/assets", id=Ref("release-stable", "id")),
            "alice",
            status=200,
        )
        a("release-assets", sc, "delete", "DELETE", ep, "alice", status=204)
        a("release-assets", sc, "gone", "GET", ep, "alice", status=404)
    for sc in ("draft", "draft-prerelease"):
        ep = pathref(rp + "/releases/{id}", id=Ref("release-" + sc, "id"))
        a(
            "release-publish",
            sc,
            "publish",
            "PATCH",
            ep,
            "alice",
            body={"draft": False},
            status=200,
        )
        a("release-publish", sc, "public-read", "GET", ep, None, status=200)
    a(
        "release-delete",
        "prerelease",
        "delete",
        "DELETE",
        pathref(rp + "/releases/{id}", id=Ref("release-prerelease", "id")),
        "alice",
        status=204,
    )
    a(
        "release-delete",
        "prerelease",
        "tag-survives",
        "GET",
        rp + "/tags/v-prerelease",
        "alice",
        status=200,
    )
    # v1.22.6 API hardcodes master. Set it through the product's visible setting.
    from reference.registry import add

    def wiki_branch(c, ui):
        p, _ = ui.goto("/alice/pbp-publish/settings")
        field = ui.field(p, "default_wiki_branch", labels=["Default Wiki Branch Name"])
        field.fill("master")
        ui.save_field(p, field, "Update Settings")
        p.wait_for_load_state("domcontentloaded")
        p.reload()
        assert ui.field(p, "default_wiki_branch").input_value() == "master"
        return {"default_wiki_branch": "master", "persisted": True}

    add(s, "wiki-settings", "api-compatible-branch", "save", wiki_branch)
    # Built-in wiki is a Git-backed product, including Unicode, spaces and revision history.
    pages = [
        ("home", "Home", "# Welcome\n\nWiki home."),
        ("spaces", "Getting Started", "# Setup\n\n1. Install\n2. Run"),
        ("unicode", "使用说明", "# 文档\n\n你好 café"),
        (
            "markdown",
            "Formatting",
            "**bold** _italic_ `code`\n\n| A | B |\n|---|---|\n| 1 | 2 |",
        ),
        ("html", "Sanitized", "<script>alert(1)</script>\nSafe text"),
        ("links", "Links", "[Home](Home) [External](https://example.test)"),
        ("sidebar", "_Sidebar", "[Home](Home)\n[Guide](Getting-Started)"),
        ("footer", "_Footer", "Project footer"),
    ]
    for sc, title, content in pages:
        ep = rp + "/wiki/page/" + urllib.parse.quote(title.replace(" ", "-"), safe="")
        a(
            "wiki",
            sc,
            "create",
            "POST",
            rp + "/wiki/new",
            "alice",
            body={
                "title": title,
                "content_base64": b64(content),
                "message": "Create wiki " + sc,
            },
            save="wiki-" + sc,
            status=201,
        )
        a("wiki", sc, "read", "GET", ep, "alice", status=200)
        a("wiki", sc, "public", "GET", ep, None, status=200)
        a(
            "wiki",
            sc,
            "duplicate",
            "POST",
            rp + "/wiki/new",
            "alice",
            body={"title": title, "content_base64": b64("duplicate")},
        )
        a(
            "wiki",
            sc,
            "outsider-edit",
            "PATCH",
            ep,
            "carol",
            body={"content_base64": b64("forbidden")},
        )
        a(
            "wiki",
            sc,
            "writer-edit",
            "PATCH",
            ep,
            "bob",
            body={
                "title": title,
                "content_base64": b64(content + "\n\nRevised " + sc),
                "message": "Revise wiki " + sc,
            },
            status=200,
        )
        a("wiki", sc, "after-edit", "GET", ep, "alice", status=200)
        a(
            "wiki",
            sc,
            "revisions",
            "GET",
            rp
            + "/wiki/revisions/"
            + urllib.parse.quote(title.replace(" ", "-"), safe=""),
            "alice",
            status=200,
        )
    for page, limit in [(1, 2), (2, 2), (3, 2), (99, 2)]:
        a(
            "wiki-pagination",
            f"p{page}-l{limit}",
            "pages",
            "GET",
            rp + "/wiki/pages",
            "alice",
            params={"page": page, "limit": limit},
            status=200,
        )
    for sc, title, _ in pages[-4:]:
        ep = rp + "/wiki/page/" + urllib.parse.quote(title.replace(" ", "-"), safe="")
        a("wiki-delete", sc, "delete", "DELETE", ep, "alice", status=204)
        a("wiki-delete", sc, "gone", "GET", ep, "alice", status=404)
