from harness import Ref, pathref, b64


def build(s):
    a = s.api
    for private in (False, True):
        vis = "private" if private else "public"
        for grant in ("none", "read", "write", "admin"):
            sc = vis + "-" + grant
            repo = "pbp-access-" + sc
            rp = "repos/bob/" + repo
            a(
                "access-fixture",
                sc,
                "create",
                "POST",
                "user/repos",
                "bob",
                body={"name": repo, "private": private, "auto_init": True},
                save=repo,
                status=201,
            )
            a(
                "access-fixture",
                sc,
                "issue",
                "POST",
                rp + "/issues",
                "bob",
                body={"title": "Permission target " + sc, "body": "original body"},
                save=sc + "-issue",
                status=201,
            )
            a(
                "access-fixture",
                sc,
                "comment",
                "POST",
                pathref(rp + "/issues/{n}/comments", n=Ref(sc + "-issue", "number")),
                "bob",
                body={"body": "owner comment"},
                save=sc + "-comment",
                status=201,
            )
            if grant != "none":
                a(
                    "access-fixture",
                    sc,
                    "grant",
                    "PUT",
                    rp + "/collaborators/carol",
                    "bob",
                    body={"permission": grant},
                    status=204,
                )
                a(
                    "access-fixture",
                    sc,
                    "permission",
                    "GET",
                    rp + "/collaborators/carol/permission",
                    "bob",
                )
            roles = (
                [("collaborator-" + grant, "carol")]
                if grant != "none"
                else [
                    ("anonymous", None),
                    ("outsider", "carol"),
                    ("owner", "bob"),
                    ("siteadmin", "alice"),
                ]
            )
            for role, actor in roles:
                rs = vis + "-" + role
                for ep in (
                    "",
                    "/branches",
                    "/branches/main",
                    "/commits",
                    "/contents",
                    "/contents/README.md",
                    "/raw/README.md",
                    "/issues",
                    "/issues/1",
                    "/issues/1/comments",
                    "/labels",
                    "/milestones",
                    "/releases",
                    "/wiki/pages",
                    "/tags",
                    "/collaborators",
                    "/collaborators/carol/permission",
                    "/assignees",
                    "/reviewers",
                    "/branch_protections",
                    "/subscription",
                    "/subscribers",
                    "/stargazers",
                    "/teams",
                ):
                    endpoint = (
                        pathref(
                            rp + ep.replace("/issues/1", "/issues/{n}"),
                            n=Ref(sc + "-issue", "number"),
                        )
                        if "/issues/1" in ep
                        else rp + ep
                    )
                    a(
                        "permission-read",
                        rs,
                        ep.strip("/").replace("/", "-") or "repository",
                        "GET",
                        endpoint,
                        actor,
                        hint="branch-list" if ep == "/branches" else "object",
                    )
                # Mutating authorization is not inferred from read access.
                mutations = [
                    (
                        "issue-title",
                        "PATCH",
                        "/issues/1",
                        {"title": "Edited by " + role},
                    ),
                    (
                        "comment-create",
                        "POST",
                        "/issues/1/comments",
                        {"body": "Comment from " + role},
                    ),
                    (
                        "comment-edit",
                        "PATCH",
                        pathref("/issues/comments/{id}", id=Ref(sc + "-comment", "id")),
                        {"body": "Changed by " + role},
                    ),
                    (
                        "label-create",
                        "POST",
                        "/labels",
                        {"name": "label-" + role, "color": "aabbcc"},
                    ),
                    (
                        "milestone-create",
                        "POST",
                        "/milestones",
                        {"title": "milestone-" + role},
                    ),
                    (
                        "branch-create",
                        "POST",
                        "/branches",
                        {
                            "new_branch_name": "branch-" + role,
                            "old_branch_name": "main",
                        },
                    ),
                    (
                        "file-create",
                        "POST",
                        "/contents/" + role + ".txt",
                        {
                            "content": b64("content by " + role),
                            "message": "Add permission file",
                        },
                    ),
                    ("settings", "PATCH", "", {"description": "settings by " + role}),
                    ("issue-close", "PATCH", "/issues/1", {"state": "closed"}),
                    ("issue-reopen", "PATCH", "/issues/1", {"state": "open"}),
                ]
                for step, method, ep, body in mutations:
                    endpoint = (lambda c, e=ep: rp + e(c)) if callable(ep) else rp + ep
                    # Capture rp by value when composing the dynamic comment path.
                    if callable(ep):
                        endpoint = lambda c, e=ep, r=rp: r + e(c)
                    if isinstance(ep, str) and "/issues/1" in ep:
                        endpoint = pathref(
                            rp + ep.replace("/issues/1", "/issues/{n}"),
                            n=Ref(sc + "-issue", "number"),
                        )
                    a("permission-write", rs, step, method, endpoint, actor, body=body)
                a(
                    "permission-write",
                    rs,
                    "owner-observes-issue",
                    "GET",
                    pathref(rp + "/issues/{n}", n=Ref(sc + "-issue", "number")),
                    "bob",
                )
                a("permission-write", rs, "owner-observes-repo", "GET", rp, "bob")
            if grant != "none":
                a(
                    "permission-revoke",
                    sc,
                    "remove",
                    "DELETE",
                    rp + "/collaborators/carol",
                    "bob",
                    status=204,
                )
                a("permission-revoke", sc, "read-after", "GET", rp, "carol")
                a(
                    "permission-revoke",
                    sc,
                    "write-after",
                    "PATCH",
                    pathref(rp + "/issues/{n}", n=Ref(sc + "-issue", "number")),
                    "carol",
                    body={"title": "revoked attempt"},
                )
                a(
                    "permission-revoke",
                    sc,
                    "membership-after",
                    "GET",
                    rp + "/collaborators/carol",
                    "bob",
                    status=404,
                )
    # The validation target exists in this episode, so the checks reach collaborator validation.
    a(
        "permission-validation-fixture",
        "target",
        "repository",
        "POST",
        "user/repos",
        "alice",
        body={"name": "pbp-repo-public", "auto_init": True},
        status=201,
    )
    for permission in ("invalid", "", "owner"):
        a(
            "permission-validation",
            permission or "empty",
            "add",
            "PUT",
            "repos/alice/pbp-repo-public/collaborators/bob",
            "alice",
            body={"permission": permission},
        )
    for user in ("pbp-no-user", "alice"):
        a(
            "permission-validation",
            user,
            "add",
            "PUT",
            f"repos/alice/pbp-repo-public/collaborators/{user}",
            "alice",
            body={"permission": "write"},
        )
