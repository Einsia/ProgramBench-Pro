from harness import Ref, pathref, b64


def build(s):
    a = s.api
    for visibility in ("public", "limited", "private"):
        org = "pbp-org-" + visibility
        op = "orgs/" + org
        a(
            "organizations",
            visibility,
            "create",
            "POST",
            "orgs",
            "alice",
            body={
                "username": org,
                "full_name": "Organization " + visibility,
                "description": "Team collaboration " + visibility,
                "visibility": visibility,
                "location": "Local",
                "website": "https://example.test/org",
            },
            save=org,
            status=201,
        )
        for actor in (None, "alice", "bob"):
            sc = visibility + "-" + (actor or "anonymous")
            for ep in ("", "/members", "/public_members", "/teams", "/repos"):
                a(
                    "organization-access",
                    sc,
                    ep.strip("/") or "profile",
                    "GET",
                    op + ep,
                    actor,
                )
        a(
            "organizations",
            visibility,
            "edit",
            "PATCH",
            op,
            "alice",
            body={
                "description": "Updated " + visibility,
                "full_name": "Edited " + visibility,
            },
            status=200,
        )
        a("organizations", visibility, "read-edited", "GET", op, "alice", status=200)
        a(
            "organizations",
            visibility,
            "outsider-edit",
            "PATCH",
            op,
            "bob",
            body={"description": "not owner"},
        )
        a(
            "organizations",
            visibility,
            "create-repo",
            "POST",
            op + "/repos",
            "alice",
            body={
                "name": "project",
                "private": visibility == "private",
                "auto_init": True,
            },
            status=201,
        )
        a(
            "organizations",
            visibility,
            "repo-list",
            "GET",
            op + "/repos",
            "alice",
            status=200,
        )
        a(
            "organizations",
            visibility,
            "member-check",
            "GET",
            op + "/members/alice",
            "alice",
            status=204,
        )
        a(
            "organizations",
            visibility,
            "publicize",
            "PUT",
            op + "/public_members/alice",
            "alice",
            status=204,
        )
        a(
            "organizations",
            visibility,
            "public-members",
            "GET",
            op + "/public_members",
            "alice",
            status=200,
        )
        a(
            "organizations",
            visibility,
            "conceal",
            "DELETE",
            op + "/public_members/alice",
            "alice",
            status=204,
        )
        a(
            "organizations",
            visibility,
            "concealed-members",
            "GET",
            op + "/public_members",
            "alice",
            status=200,
        )
    org = "pbp-org-public"
    op = "orgs/" + org
    for sc, body in [
        ("empty", {"username": ""}),
        ("duplicate", {"username": org}),
        ("user-collision", {"username": "alice"}),
        ("invalid", {"username": "bad org"}),
        (
            "invalid-visibility",
            {"username": "pbp-org-invalid", "visibility": "invalid"},
        ),
    ]:
        a("organization-validation", sc, "create", "POST", "orgs", "bob", body=body)
    # Permission/unit combinations have different read/write behavior in the same organization.
    teams = [
        ("reader-code", "read", ["repo.code"]),
        ("reader-issues", "read", ["repo.issues"]),
        ("writer-code", "write", ["repo.code"]),
        ("writer-issues", "write", ["repo.issues"]),
        (
            "writer-all",
            "write",
            ["repo.code", "repo.issues", "repo.pulls", "repo.releases", "repo.wiki"],
        ),
        ("administrator", "admin", ["repo.code", "repo.issues", "repo.pulls"]),
        ("all-repositories", "read", ["repo.code", "repo.issues"]),
        ("repo-creator", "write", ["repo.code", "repo.issues"]),
    ]
    # Unit permissions only show on a private repository: anyone may read a public one.
    a(
        "team-unit-fixture",
        "private-repo",
        "create",
        "POST",
        op + "/repos",
        "alice",
        body={"name": "team-private", "private": True, "auto_init": True},
        status=201,
    )
    for sc, permission, units in teams:
        key = "team-" + sc
        a(
            "teams",
            sc,
            "create",
            "POST",
            op + "/teams",
            "alice",
            body={
                "name": sc,
                "description": "Team " + sc,
                "permission": permission,
                "units": units,
                "includes_all_repositories": sc == "all-repositories",
                "can_create_org_repo": sc == "repo-creator",
            },
            save=key,
            status=201,
        )
        ep = pathref("teams/{id}", id=Ref(key, "id"))
        a("teams", sc, "read", "GET", ep, "alice", status=200)
        a(
            "teams",
            sc,
            "add-member",
            "PUT",
            lambda c, e=ep: e(c) + "/members/bob",
            "alice",
            status=204,
        )
        a(
            "teams",
            sc,
            "member-list",
            "GET",
            lambda c, e=ep: e(c) + "/members",
            "alice",
            status=200,
        )
        a(
            "teams",
            sc,
            "add-repo",
            "PUT",
            lambda c, e=ep: e(c) + "/repos/pbp-org-public/project",
            "alice",
        )
        a(
            "teams",
            sc,
            "repo-list",
            "GET",
            lambda c, e=ep: e(c) + "/repos",
            "bob",
            status=200,
        )
        a("teams", sc, "self-teams", "GET", "user/teams", "bob", status=200)
        a(
            "teams",
            sc,
            "org-permissions",
            "GET",
            "users/bob/orgs/pbp-org-public/permissions",
            "bob",
        )
        a(
            "team-unit-fixture",
            sc,
            "add-private-repo",
            "PUT",
            lambda c, e=ep: e(c) + "/repos/pbp-org-public/team-private",
            "alice",
        )
        for step, method, suffix, body in [
            ("read-code", "GET", "/contents", None),
            ("read-issues", "GET", "/issues", None),
            ("read-releases", "GET", "/releases", None),
            (
                "write-code",
                "POST",
                "/contents/" + sc + ".txt",
                {"content": b64("team " + sc), "message": "Team write"},
            ),
            ("write-issue", "POST", "/issues", {"title": "Team issue " + sc}),
            ("edit-settings", "PATCH", "", {"description": "Team settings " + sc}),
        ]:
            a(
                "team-unit-access",
                sc,
                step,
                method,
                "repos/pbp-org-public/team-private" + suffix,
                "bob",
                body=body,
            )
        a(
            "teams",
            sc,
            "edit",
            "PATCH",
            ep,
            "alice",
            body={"description": "Revised " + sc},
            status=200,
        )
        a(
            "teams",
            sc,
            "remove-member",
            "DELETE",
            lambda c, e=ep: e(c) + "/members/bob",
            "alice",
            status=204,
        )
        a(
            "teams",
            sc,
            "member-gone",
            "GET",
            lambda c, e=ep: e(c) + "/members/bob",
            "alice",
            status=404,
        )
        a(
            "teams",
            sc,
            "remove-repo",
            "DELETE",
            lambda c, e=ep: e(c) + "/repos/pbp-org-public/project",
            "alice",
        )
        a("teams", sc, "delete", "DELETE", ep, "alice", status=204)
        a("teams", sc, "gone", "GET", ep, "alice", status=404)
    for name in ("", "Owners", "reader-code"):
        a(
            "team-validation",
            name or "empty",
            "create",
            "POST",
            op + "/teams",
            "alice",
            body={"name": name, "permission": "read", "units": ["repo.code"]},
        )
    for actor in (None, "alice", "bob"):
        a(
            "organization-directory",
            actor or "anonymous",
            "search",
            "GET",
            "orgs",
            actor,
            params={"limit": 2, "page": 1},
        )
    for ep in ("user/orgs", "users/alice/orgs"):
        a("organization-membership", ep.replace("/", "-"), "list", "GET", ep, "alice")
    for sc in ("public", "private"):
        name = "pbp-disposable-org-" + sc
        a(
            "organization-delete",
            sc,
            "create",
            "POST",
            "orgs",
            "bob",
            body={"username": name, "visibility": sc},
            status=201,
        )
        a("organization-delete", sc, "outsider", "DELETE", "orgs/" + name, "carol")
        a(
            "organization-delete",
            sc,
            "owner",
            "DELETE",
            "orgs/" + name,
            "bob",
            status=204,
        )
        a("organization-delete", sc, "gone", "GET", "orgs/" + name, "bob", status=404)
