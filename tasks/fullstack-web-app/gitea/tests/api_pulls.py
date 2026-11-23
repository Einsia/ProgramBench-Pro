from harness import Ref, pathref, b64, blob_sha


def build(s):
    a = s.api
    episodes = [
        ("merge", "merge", False),
        ("squash", "squash", False),
        ("rebase", "rebase", False),
        ("rebase-merge", "rebase-merge", False),
        ("closed", "close", False),
        ("conflict", "merge", True),
    ]
    for sc, style, conflict in episodes:
        rp = "repos/alice/pbp-pr-" + sc
        key = "pr-" + sc
        a(
            "pull-fixture",
            sc,
            "repository",
            "POST",
            "user/repos",
            "alice",
            body={"name": "pbp-pr-" + sc, "auto_init": True},
            status=201,
        )
        a(
            "pull-fixture",
            sc,
            "writer",
            "PUT",
            rp + "/collaborators/bob",
            "alice",
            body={"permission": "write"},
            status=204,
        )
        a(
            "pull-fixture",
            sc,
            "base-file",
            "POST",
            rp + "/contents/feature.txt",
            "alice",
            body={"content": b64("base\n"), "message": "Base feature"},
            save=key + "-base-file",
            status=201,
        )
        a(
            "pull-fixture",
            sc,
            "branch",
            "POST",
            rp + "/branches",
            "bob",
            body={"new_branch_name": "feature", "old_branch_name": "main"},
            status=201,
        )
        a(
            "pull-fixture",
            sc,
            "feature-file",
            "PUT",
            rp + "/contents/feature.txt",
            "bob",
            body={
                "branch": "feature",
                "sha": blob_sha("base\n"),
                "content": b64("feature " + sc + "\n"),
                "message": "Implement feature " + sc,
            },
            status=200,
        )
        if conflict:
            a(
                "pull-fixture",
                sc,
                "conflict-file",
                "PUT",
                rp + "/contents/feature.txt",
                "alice",
                body={
                    "sha": blob_sha("base\n"),
                    "content": b64("conflicting main change\n"),
                    "message": "Conflicting main",
                },
                status=200,
            )
        a(
            "pulls",
            sc,
            "create",
            "POST",
            rp + "/pulls",
            "bob",
            body={
                "head": "feature",
                "base": "main",
                "title": "Propose " + sc,
                "body": "A **pull request** for " + sc,
            },
            save=key,
            status=201,
            settle_pull=not conflict,
        )
        ep = pathref(rp + "/pulls/{n}", n=Ref(key, "number"))
        a(
            "pulls",
            sc,
            "read",
            "GET",
            ep,
            "alice",
            status=200,
            eventually={"mergeable": not conflict},
        )
        a("pulls", sc, "by-branches", "GET", rp + "/pulls/main/feature", "alice")
        for suffix in ("/files", "/commits", "/reviews", "/merge"):
            a(
                "pulls",
                sc,
                suffix.strip("/"),
                "GET",
                lambda c, e=ep, z=suffix: e(c) + z,
                "alice",
            )
        a(
            "pulls",
            sc,
            "duplicate",
            "POST",
            rp + "/pulls",
            "bob",
            body={"head": "feature", "base": "main", "title": "Duplicate"},
        )
        a(
            "pulls",
            sc,
            "rename",
            "PATCH",
            ep,
            "bob",
            body={"title": "Updated proposal " + sc, "body": "Revised description"},
            status=201,
        )
        a(
            "pulls",
            sc,
            "outsider-edit",
            "PATCH",
            ep,
            "carol",
            body={"title": "Hijacked proposal"},
        )
        a(
            "pulls",
            sc,
            "issue-view",
            "GET",
            pathref(rp + "/issues/{n}", n=Ref(key, "number")),
            "alice",
            status=200,
        )
        review_ep = lambda c, e=ep: e(c) + "/reviews"
        a(
            "reviews",
            sc,
            "comment",
            "POST",
            review_ep,
            "alice",
            body={"event": "COMMENT", "body": "Review comment " + sc},
            save=key + "-review",
            status=200,
        )
        a(
            "reviews",
            sc,
            "read-comment",
            "GET",
            pathref(
                rp + "/pulls/{n}/reviews/{id}",
                n=Ref(key, "number"),
                id=Ref(key + "-review", "id"),
            ),
            "bob",
            status=200,
        )
        a(
            "reviews",
            sc,
            "author-pending-draft",
            "POST",
            review_ep,
            "bob",
            body={"event": "PENDING", "body": "Self approval"},
        )
        a(
            "reviews",
            sc,
            "request-review",
            "POST",
            lambda c, e=ep: e(c) + "/requested_reviewers",
            "bob",
            body={"reviewers": ["alice"]},
        )
        a(
            "reviews",
            sc,
            "pending-draft",
            "POST",
            review_ep,
            "alice",
            body={"event": "PENDING", "body": "Approved " + sc},
            save=key + "-approval",
            status=200,
        )
        a("reviews", sc, "list", "GET", review_ep, "alice", status=200)
        a(
            "pull-filter",
            sc,
            "open",
            "GET",
            rp + "/pulls",
            "alice",
            params={"state": "open"},
            status=200,
        )
        a(
            "pull-filter",
            sc,
            "closed-before",
            "GET",
            rp + "/pulls",
            "alice",
            params={"state": "closed"},
            status=200,
        )
        if style == "close":
            a(
                "pull-state",
                sc,
                "close",
                "PATCH",
                ep,
                "bob",
                body={"state": "closed"},
                status=201,
            )
            a("pull-state", sc, "closed-read", "GET", ep, "alice", status=200)
            a(
                "pull-state",
                sc,
                "reopen",
                "PATCH",
                ep,
                "bob",
                body={"state": "open"},
                status=201,
                settle_pull=True,
            )
            a(
                "pull-state",
                sc,
                "close-again",
                "PATCH",
                ep,
                "bob",
                body={"state": "closed"},
                status=201,
            )
        else:
            a(
                "pull-merge",
                sc,
                "outsider",
                "POST",
                lambda c, e=ep: e(c) + "/merge",
                "carol",
                body={"Do": style},
            )
            a(
                "pull-merge",
                sc,
                "merge",
                "POST",
                lambda c, e=ep: e(c) + "/merge",
                "alice",
                body={
                    "Do": style,
                    "merge_message_field": "Merge through API",
                    "delete_branch_after_merge": False,
                },
                status=None if conflict else 200,
                before=lambda c, e=ep, w=not conflict: c.pull_ready(e(c), w),
            )
            a("pull-merge", sc, "state", "GET", ep, "alice", status=200)
            a(
                "pull-merge",
                sc,
                "merged-check",
                "GET",
                lambda c, e=ep: e(c) + "/merge",
                "alice",
                status=404 if conflict else 204,
            )
            a(
                "pull-merge",
                sc,
                "base-content",
                "GET",
                rp + "/contents/feature.txt",
                "alice",
                status=200,
                want={
                    "content": b64(
                        "conflicting main change\n"
                        if conflict
                        else "feature " + sc + "\n"
                    )
                },
            )
            a(
                "pull-merge",
                sc,
                "repeat",
                "POST",
                lambda c, e=ep: e(c) + "/merge",
                "alice",
                body={"Do": style},
            )
        for state in ("open", "closed", "all"):
            a(
                "pull-filter",
                sc,
                state + "-after",
                "GET",
                rp + "/pulls",
                "alice",
                params={"state": state},
                status=200,
            )
    rp = "repos/alice/pbp-pr-closed"
    for sc, body in [
        ("missing-title", {"head": "feature", "base": "main"}),
        ("same-branch", {"head": "main", "base": "main", "title": "same"}),
        ("missing-head", {"head": "absent", "base": "main", "title": "missing"}),
        ("missing-base", {"head": "feature", "base": "absent", "title": "missing"}),
    ]:
        a("pull-validation", sc, "create", "POST", rp + "/pulls", "alice", body=body)
    for state in ("pending", "success", "error", "failure", "warning"):
        key = "status-" + state
        ep = pathref(rp + "/statuses/{sha}", sha=Ref("pr-closed", "head", "sha"))
        a(
            "commit-status",
            state,
            "create",
            "POST",
            ep,
            "bob",
            body={
                "state": state,
                "context": "checks/" + state,
                "description": "Result " + state,
                "target_url": "https://example.test/check/" + state,
            },
            save=key,
        )
        a(
            "commit-status",
            state,
            "list",
            "GET",
            ep,
            "alice",
            params={"sort": "leastindex"},
        )
        a(
            "commit-status",
            state,
            "combined",
            "GET",
            pathref(rp + "/commits/{sha}/status", sha=Ref("pr-closed", "head", "sha")),
            "alice",
        )
    for sc, body in [
        ("one-approval", {"required_approvals": 1}),
        ("block-rejected", {"block_on_rejected_reviews": True}),
        ("no-push", {"enable_push": False}),
        (
            "status-required",
            {"enable_status_check": True, "status_check_contexts": ["checks/test"]},
        ),
    ]:
        name = "protect-" + sc
        a(
            "branch-protection",
            sc,
            "create",
            "POST",
            rp + "/branch_protections",
            "alice",
            body={"branch_name": name, "rule_name": name, **body},
        )
        a(
            "branch-protection",
            sc,
            "read",
            "GET",
            rp + "/branch_protections/" + name,
            "alice",
        )
        a(
            "branch-protection",
            sc,
            "edit",
            "PATCH",
            rp + "/branch_protections/" + name,
            "alice",
            body={"required_approvals": 2},
        )
        a("branch-protection", sc, "list", "GET", rp + "/branch_protections", "alice")
        a(
            "branch-protection",
            sc,
            "delete",
            "DELETE",
            rp + "/branch_protections/" + name,
            "alice",
        )
