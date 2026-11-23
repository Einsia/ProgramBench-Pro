from harness import Ref, pathref, subset
from markup_observation import (
    observe_markup,
)  # Required helper; fail during suite loading if absent.


def build(s):
    a = s.api
    # Baseline: authentication views reveal different profile fields, and all collections are empty.
    for actor in (None, "invalid", "alice", "bob", "carol"):
        sc = actor or "anonymous"
        a(
            "auth",
            sc,
            "current",
            "GET",
            "user",
            actor,
            status=200 if actor in ("alice", "bob", "carol") else 401,
            save="me-" + sc,
        )
        for endpoint in (
            "user/repos",
            "user/orgs",
            "user/teams",
            "user/starred",
            "user/subscriptions",
            "user/emails",
            "user/settings",
        ):
            a(
                "auth",
                sc,
                endpoint.replace("/", "-"),
                "GET",
                endpoint,
                actor,
                status=200 if actor in ("alice", "bob", "carol") else 401,
            )
    for name in ("alice", "bob", "carol"):
        for actor in (None, name, "alice" if name != "alice" else "bob"):
            sc = name + "-as-" + (actor or "anonymous")
            a(
                "profiles",
                sc,
                "read",
                "GET",
                f"users/{name}",
                actor,
                save="user-" + name,
                status=200,
                want={"login": name, "full_name": name.title() + " Example"},
            )
        for endpoint in (
            "repos",
            "orgs",
            "followers",
            "following",
            "starred",
            "subscriptions",
        ):
            a(
                "profiles",
                name,
                endpoint,
                "GET",
                f"users/{name}/{endpoint}",
                None,
                status=200 if endpoint == "repos" else 401,
            )
    for q in ("alice", "ALICE", "bob", "Example", "missing-person", "a", ""):
        for lim in (1, 10):
            a(
                "user-search",
                q.lower() + "-" + str(lim) if q != "ALICE" else "uppercase-" + str(lim),
                "query",
                "GET",
                "users/search",
                None,
                params={"q": q, "limit": lim},
                status=200,
            )
    for user in ("alice", "bob", "carol"):
        other = {"alice": "bob", "bob": "carol", "carol": "alice"}[user]
        for target in (other, user, "pbp-absent-user"):
            sc = user + "-to-" + target
            for step, method in [
                ("before", "GET"),
                ("follow", "PUT"),
                ("after", "GET"),
                ("repeat", "PUT"),
            ]:
                a("follows", sc, step, method, f"user/following/{target}", user)
            a("follows", sc, "following-list", "GET", f"users/{user}/following", user)
            a("follows", sc, "follower-list", "GET", f"users/{target}/followers", user)
            a("follows", sc, "unfollow", "DELETE", f"user/following/{target}", user)
            a("follows", sc, "removed", "GET", f"user/following/{target}", user)
    settings = [
        ("full_name", "Bøb 工程師"),
        ("description", "Engineer **markdown** & <script>safe</script>"),
        ("location", "Paris / 東京"),
        ("website", "https://example.test/path?q=one&v=two"),
        ("language", "en-US"),
        ("theme", "gitea-light"),
        ("hide_email", False),
        ("hide_activity", True),
        ("diff_view_style", "split"),
        ("enable_repo_unit_hints", False),
    ]
    for field, value in settings:
        sc = field
        a(
            "settings",
            sc,
            "change",
            "PATCH",
            "user/settings",
            "bob",
            body={field: value},
        )
        a("settings", sc, "self", "GET", "user/settings", "bob")
        a("settings", sc, "public", "GET", "users/bob", None)
    for field, value in [
        ("full_name", "Bob Example"),
        ("description", ""),
        ("location", ""),
        ("website", ""),
        ("hide_email", True),
        ("hide_activity", False),
        ("diff_view_style", "unified"),
        ("enable_repo_unit_hints", True),
    ]:
        a(
            "settings",
            field,
            "reset",
            "PATCH",
            "user/settings",
            "bob",
            body={field: value},
        )
    for sc, emails in [
        ("secondary", ["bob+work@example.test"]),
        ("unicode", ["unicode@example.test"]),
        ("duplicate", ["bob+work@example.test"]),
        ("bad", ["not-an-email"]),
        ("occupied", ["alice@example.test"]),
        ("empty", []),
    ]:
        a("emails", sc, "add", "POST", "user/emails", "bob", body={"emails": emails})
        a("emails", sc, "list", "GET", "user/emails", "bob")
        if sc in ("secondary", "unicode"):
            a(
                "emails",
                sc,
                "remove",
                "DELETE",
                "user/emails",
                "bob",
                body={"emails": emails},
            )
            a("emails", sc, "after-remove", "GET", "user/emails", "bob")
    # Token permissions are independent of basic-auth permissions.
    scope_sets = [
        ("all", ["all"]),
        ("user-read", ["read:user"]),
        ("user-write", ["write:user"]),
        ("repo-read", ["read:repository"]),
        ("repo-write", ["write:repository"]),
        ("org-read", ["read:organization"]),
        ("issue-read", ["read:issue"]),
        ("issue-write", ["write:issue"]),
        ("notification", ["read:notification"]),
        ("public", ["public-only", "read:user", "read:repository"]),
    ]
    for sc, scopes in scope_sets:
        key = "token-" + sc
        a(
            "tokens",
            sc,
            "create",
            "POST",
            "users/bob/tokens",
            "bob",
            body={"name": "pbp-" + sc, "scopes": scopes},
            save=key,
            status=201,
            hint="token",
        )
        for ep in ("user", "user/repos", "user/orgs", "notifications", "user/settings"):
            a("tokens", sc, ep.replace("/", "-"), "GET", ep, "token:" + key)
        a(
            "tokens",
            sc,
            "revoke",
            "DELETE",
            pathref("users/bob/tokens/{id}", id=Ref(key, "id")),
            "bob",
        )
        a("tokens", sc, "revoked-denied", "GET", "user", "token:" + key, status=401)
    for sc, body in [
        ("bad-scope", {"name": "pbp-invalid", "scopes": ["invented:scope"]}),
        ("empty-name", {"name": "", "scopes": ["all"]}),
        ("empty-scope", {"name": "pbp-none", "scopes": []}),
    ]:
        a(
            "tokens-invalid",
            sc,
            "create",
            "POST",
            "users/bob/tokens",
            "bob",
            body=body,
            hint="token",
        )
    for actor in (None, "bob", "carol"):
        a(
            "tokens-cross-user",
            actor or "anonymous",
            "list-alice",
            "GET",
            "users/alice/tokens",
            actor,
        )
    for sc, body in [
        ("plain", {"text": "Hello **world** and `code`"}),
        ("heading", {"text": "# Heading\n\n- one\n- two"}),
        ("table", {"text": "| A | B |\n|---|---|\n| x | y |"}),
        ("xss", {"text": "<script>alert(1)</script>\n[bad](javascript:alert(1))"}),
        ("links", {"text": "[Example](https://example.test)"}),
        ("unicode", {"text": "你好 **café** 😀"}),
        ("empty", {"text": ""}),
        ("task-list", {"text": "- [x] done\n- [ ] todo"}),
    ]:
        a(
            "markdown",
            sc,
            "render",
            "POST",
            "markdown",
            "alice",
            body=body,
            hint="markdown",
        )
    for endpoint in (
        "gitignore/templates",
        "licenses",
        "label/templates",
        "settings/api",
        "settings/repository",
        "settings/ui",
        "settings/attachment",
    ):
        a(
            "discovery",
            endpoint.replace("/", "-"),
            "read",
            "GET",
            endpoint,
            None,
            status=200,
        )
    for kind, names in [
        ("gitignore", ["Python", "Node", "Go", "Rust", "Java", "not-real-template"]),
        ("licenses", ["MIT", "Apache-2.0", "BSD-3-Clause", "not-real-license"]),
        ("label", ["Default", "Advanced", "not-real-labels"]),
    ]:
        for name in names:
            ep = (
                f"{kind}/templates/{name}" if kind != "licenses" else f"licenses/{name}"
            )
            a("templates", kind + "-" + name, "read", "GET", ep, None)
