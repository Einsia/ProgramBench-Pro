from harness import Ref, pathref, b64, subset, canonical_uri


def renamed_repository(c, response, payload, key, target):
    location = c.local_resource_path(response.headers.get("Location"))
    assert canonical_uri(location) == canonical_uri("/api/v1/" + target), "rename redirect identifies another destination"
    r, repository = c.request("GET", location, "bob")
    assert r.status_code == 200 and repository["id"] == c.state[key]["id"], "rename redirect does not resolve to the original repository"
    assert repository["full_name"] == target.removeprefix("repos/"), "rename redirect resolves to another repository name"


def build(s):
    a = s.api
    # Input semantics: initialization, privacy, template, default branch, metadata.
    specs = [
        ("public", {}),
        ("private", {"private": True}),
        ("empty", {"auto_init": False}),
        ("template", {"template": True}),
        ("description", {"description": "Unicode café 工具 & <safe>"}),
        ("website", {"description": "Project with home page"}),
        ("branch", {"default_branch": "develop"}),
        ("license", {"license": "MIT"}),
        ("ignore", {"gitignores": "Python,Node"}),
        ("readme", {"readme": "Default"}),
    ]
    for sc, extra in specs:
        repo = "pbp-repo-" + sc
        path = f"repos/alice/{repo}"
        body = {"name": repo, "auto_init": True, "default_branch": "main", **extra}
        a(
            "repository-create",
            sc,
            "create",
            "POST",
            "user/repos",
            "alice",
            body=body,
            save=repo,
            status=201,
            want={"name": repo, "private": extra.get("private", False)},
        )
        for actor in ("alice", "bob", None):
            a(
                "repository-create",
                sc,
                "read-" + (actor or "anonymous"),
                "GET",
                path,
                actor,
            )
        for ep in (
            "branches",
            "contents",
            "languages",
            "labels",
            "milestones",
            "releases",
            "tags",
            "issue_templates",
            "issue_config",
            "assignees",
        ):
            a("repository-initial", sc, ep, "GET", path + "/" + ep, "alice")
    invalid = [
        ("empty", {"name": ""}),
        ("spaces", {"name": "bad name"}),
        ("slash", {"name": "bad/name"}),
        ("dot", {"name": "."}),
        ("dotdot", {"name": ".."}),
        ("reserved", {"name": "issues"}),
        ("duplicate", {"name": "pbp-repo-public"}),
        ("case-duplicate", {"name": "PBP-REPO-PUBLIC"}),
        (
            "invalid-branch",
            {"name": "pbp-badbranch", "auto_init": True, "default_branch": "a..b"},
        ),
    ]
    for sc, body in invalid:
        a(
            "repository-validation",
            sc,
            "create",
            "POST",
            "user/repos",
            "alice",
            body=body,
        )
    for actor in (None, "invalid"):
        a(
            "repository-validation",
            actor or "anonymous",
            "unauthorized",
            "POST",
            "user/repos",
            actor,
            body={"name": "pbp-unauthorized"},
        )
    # Settings are tested on a repository that is not shared by unrelated episodes.
    rp = "repos/alice/pbp-repo-description"
    edits = [
        ("description", {"description": "changed\nmultiple lines & unicode Ω"}),
        ("website", {"website": "https://example.test/project"}),
        ("private", {"private": True}),
        ("public", {"private": False}),
        ("issues-off", {"has_issues": False}),
        ("issues-on", {"has_issues": True}),
        ("wiki-off", {"has_wiki": False}),
        ("wiki-on", {"has_wiki": True}),
        ("pulls-off", {"has_pull_requests": False}),
        ("pulls-on", {"has_pull_requests": True}),
        ("projects-off", {"has_projects": False}),
        ("projects-on", {"has_projects": True}),
        ("merge-off", {"allow_merge_commits": False}),
        ("merge-on", {"allow_merge_commits": True}),
        ("squash-off", {"allow_squash_merge": False}),
        ("squash-on", {"allow_squash_merge": True}),
        ("rebase-off", {"allow_rebase": False}),
        ("rebase-on", {"allow_rebase": True}),
        ("delete-branch", {"default_delete_branch_after_merge": True}),
        ("ignore-whitespace", {"ignore_whitespace_conflicts": True}),
        ("template-on", {"template": True}),
        ("template-off", {"template": False}),
        ("archived", {"archived": True}),
        ("unarchived", {"archived": False}),
    ]
    for sc, body in edits:
        a("repository-settings", sc, "edit", "PATCH", rp, "alice", body=body)
        a("repository-settings", sc, "read", "GET", rp, "alice")
        a("repository-settings", sc, "outsider-view", "GET", rp, "bob")
    for sc, body in [
        ("duplicate-rename", {"name": "pbp-repo-public"}),
        ("empty-name", {"name": ""}),
        ("missing-branch", {"default_branch": "missing"}),
        ("invalid-website", {"website": "not a URL"}),
    ]:
        a("repository-settings-invalid", sc, "edit", "PATCH", rp, "alice", body=body)
    # Stars and subscriptions: independent actors, idempotence and visible counters.
    for user in ("alice", "bob", "carol"):
        for visibility in ("public", "private"):
            name = "pbp-repo-" + visibility
            sc = user + "-" + visibility
            a("stars", sc, "before", "GET", f"user/starred/alice/{name}", user)
            a("stars", sc, "star", "PUT", f"user/starred/alice/{name}", user)
            a("stars", sc, "repeat", "PUT", f"user/starred/alice/{name}", user)
            a("stars", sc, "list", "GET", "user/starred", user)
            a("stars", sc, "stargazers", "GET", f"repos/alice/{name}/stargazers", user)
            a("stars", sc, "unstar", "DELETE", f"user/starred/alice/{name}", user)
            a("stars", sc, "removed", "GET", f"user/starred/alice/{name}", user)
            a(
                "watches",
                sc,
                "watch",
                "PUT",
                f"repos/alice/{name}/subscription",
                user,
                body={"subscribed": True},
            )
            a("watches", sc, "get", "GET", f"repos/alice/{name}/subscription", user)
            a("watches", sc, "list", "GET", "user/subscriptions", user)
            a(
                "watches",
                sc,
                "subscribers",
                "GET",
                f"repos/alice/{name}/subscribers",
                user,
            )
            a(
                "watches",
                sc,
                "unwatch",
                "DELETE",
                f"repos/alice/{name}/subscription",
                user,
            )
    # Search query semantics, visibility and paging with multiple distinct records.
    for actor in (None, "alice", "bob"):
        for mode, params in [
            ("all", {}),
            ("query", {"q": "pbp-repo"}),
            ("description", {"q": "Unicode", "includeDesc": True}),
            ("private", {"is_private": True}),
            ("public", {"is_private": False}),
            ("template", {"template": True}),
            ("non-template", {"template": False}),
            ("owner", {"uid": Ref("user-alice", "id")}),
            ("starred", {"starredBy": Ref("user-bob", "id")}),
            ("missing", {"q": "no-match-zz"}),
        ]:
            a(
                "repository-search",
                (actor or "anonymous") + "-" + mode,
                "query",
                "GET",
                "repos/search",
                actor,
                params=params,
                status=200,
            )
    # Storage byte counts and global row-ID ordering are implementation dependent.
    for sort in ("alpha", "created", "updated"):
        for order in ("asc", "desc"):
            for page in (1, 2, 20):
                a(
                    "repository-search-order",
                    sort + "-" + order + "-" + str(page),
                    "query",
                    "GET",
                    "repos/search",
                    "alice",
                    params={
                        "q": "pbp-repo",
                        "sort": sort,
                        "order": order,
                        "limit": 3,
                        "page": page,
                    },
                    status=200,
                    temporal_page=(
                        sort + "_at" if sort in ("created", "updated") else None
                    ),
                )
    # Fork and template generation preserve content but alter ownership/relationships.
    for sc, ep, body in [
        (
            "fork-public",
            "repos/alice/pbp-repo-public/forks",
            {"name": "pbp-fork-public"},
        ),
        (
            "fork-private",
            "repos/alice/pbp-repo-private/forks",
            {"name": "pbp-fork-private"},
        ),
        (
            "generate",
            "repos/alice/pbp-repo-template/generate",
            {
                "owner": "bob",
                "name": "pbp-generated",
                "git_content": True,
                "topics": True,
                "labels": True,
                "private": True,
            },
        ),
    ]:
        a("repository-derived", sc, "create", "POST", ep, "bob", body=body)
        a("repository-derived", sc, "owner-repos", "GET", "users/bob/repos", "bob")
        a(
            "repository-derived",
            sc,
            "source-forks",
            "GET",
            "repos/alice/pbp-repo-public/forks",
            "alice",
        )
    # Missing resources and authorization are status cases, not scalar count padding.
    for actor in (None, "alice", "bob"):
        for suffix in (
            "",
            "/contents/missing.txt",
            "/branches/absent",
            "/tags/v-missing",
            "/issues/999999",
            "/issues/comments/999999",
            "/labels/999999",
            "/milestones/999999",
            "/releases/999999",
            "/wiki/page/Absent",
            "/pulls/999999",
        ):
            sc = (
                (actor or "anonymous")
                + "-"
                + (suffix.replace("/", "-") or "repository")
            )
            a(
                "missing-resource",
                sc,
                "read",
                "GET",
                "repos/alice/pbp-never-exists" + suffix,
                actor,
            )
    # Isolated delete and rename transitions.
    for sc, private in [("public", False), ("private", True)]:
        name = "pbp-lifecycle-" + sc
        rp = "repos/bob/" + name
        a(
            "repository-lifecycle",
            sc,
            "create",
            "POST",
            "user/repos",
            "bob",
            body={"name": name, "private": private, "auto_init": True},
            status=201,
            save="lifecycle-" + sc,
        )
        a(
            "repository-lifecycle",
            sc,
            "rename",
            "PATCH",
            rp,
            "bob",
            body={"name": name + "-renamed"},
            status=200,
        )
        a("repository-lifecycle", sc, "old-address", "GET", rp, "bob", status=307,
          check=lambda c, r, p, key="lifecycle-" + sc, target=rp + "-renamed":
              renamed_repository(c, r, p, key, target))
        rp += "-renamed"
        a("repository-lifecycle", sc, "new-address", "GET", rp, "bob", status=200)
        a("repository-lifecycle", sc, "outsider-delete", "DELETE", rp, "carol")
        a("repository-lifecycle", sc, "owner-delete", "DELETE", rp, "bob", status=204)
        a("repository-lifecycle", sc, "gone", "GET", rp, "bob", status=404)
