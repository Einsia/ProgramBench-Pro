from harness import Ref, pathref


def build(s):
    a = s.api
    rp = "repos/alice/pbp-issues"
    a(
        "issue-fixture",
        "public",
        "repository",
        "POST",
        "user/repos",
        "alice",
        body={"name": "pbp-issues", "auto_init": True},
        status=201,
    )
    a(
        "issue-fixture",
        "public",
        "writer",
        "PUT",
        rp + "/collaborators/bob",
        "alice",
        body={"permission": "write"},
        status=204,
    )
    labels = [
        ("bug", "ee0701", "Defects"),
        ("enhancement", "84b6eb", "Feature work"),
        ("needs review", "fbca04", "Review queue"),
        ("Unicode-标签", "5319e7", "多语言"),
        ("empty-description", "ffffff", ""),
        ("upper-color", "ABCDEF", "case normalization"),
        ("hash-color", "#abcdef", "prefix handling"),
        ("short-color", "abc", "short color"),
        ("bad-color", "zzzzzz", "invalid color"),
    ]
    for sc, color, desc in labels:
        key = "label-" + sc
        a(
            "labels",
            sc,
            "create",
            "POST",
            rp + "/labels",
            "alice",
            body={"name": sc, "color": color, "description": desc},
            save=key,
        )
        if sc not in ("short-color", "bad-color"):
            ep = pathref(rp + "/labels/{id}", id=Ref(key, "id"))
            a("labels", sc, "read", "GET", ep, "alice", status=200)
            a(
                "labels",
                sc,
                "edit",
                "PATCH",
                ep,
                "alice",
                body={"description": desc + " edited"},
                status=200,
            )
            a("labels", sc, "after-edit", "GET", ep, "bob", status=200)
            a(
                "labels",
                sc,
                "outsider-edit",
                "PATCH",
                ep,
                "carol",
                body={"name": "unauthorized"},
            )
    for sc, body in [
        ("empty-name", {"name": "", "color": "aabbcc"}),
        ("duplicate", {"name": "bug", "color": "aabbcc"}),
        ("case-duplicate", {"name": "BUG", "color": "aabbcc"}),
        ("missing-color", {"name": "no-color"}),
    ]:
        a("label-validation", sc, "create", "POST", rp + "/labels", "alice", body=body)
    for sc, body in [
        ("open", {}),
        ("closed", {"state": "closed"}),
        ("future", {"due_on": "2030-06-15T00:00:00Z"}),
        ("past", {"due_on": "2020-01-01T00:00:00Z"}),
        ("unicode", {"description": "工程计划 Ω"}),
        ("invalid-state", {"state": "nonsense"}),
    ]:
        key = "milestone-" + sc
        a(
            "milestones",
            sc,
            "create",
            "POST",
            rp + "/milestones",
            "alice",
            body={"title": "Milestone " + sc, **body},
            save=key,
        )
        ep = pathref(rp + "/milestones/{id}", id=Ref(key, "id"))
        a("milestones", sc, "read", "GET", ep, "alice")
        a(
            "milestones",
            sc,
            "edit",
            "PATCH",
            ep,
            "alice",
            body={"description": "Edited milestone " + sc},
        )
        a("milestones", sc, "public-read", "GET", ep, None)
    for state in ("open", "closed", "all", "invalid"):
        # The API consumes state/name/pagination, not the web sort parameter.
        a(
            "milestone-filter",
            state,
            "list",
            "GET",
            rp + "/milestones",
            "alice",
            params={"state": state, "limit": 3},
        )
    scenarios = [
        ("plain", {"title": "Plain issue", "body": "plain body"}),
        (
            "markdown",
            {
                "title": "Markdown issue",
                "body": "## Heading\n\n**bold** `code`\n- [ ] todo\n- [x] done",
            },
        ),
        ("unicode", {"title": "你好 café Ω 😀", "body": "Unicode 正文"}),
        (
            "html",
            {
                "title": "<script>not executable</script>",
                "body": "<script>alert(1)</script>\n<img src=x onerror=alert(1)>",
            },
        ),
        ("empty-body", {"title": "Empty body", "body": ""}),
        ("multiline", {"title": "Multi-line body", "body": "first\n\nthird\r\nfourth"}),
        ("closed-create", {"title": "Initially closed", "closed": True}),
        ("assigned", {"title": "Assigned Bob", "assignees": ["bob"]}),
        ("multi-assigned", {"title": "Two assignees", "assignees": ["alice", "bob"]}),
        ("labeled", {"title": "Labeled bug", "labels": [Ref("label-bug", "id")]}),
        (
            "multi-label",
            {
                "title": "Two labels",
                "labels": [Ref("label-bug", "id"), Ref("label-enhancement", "id")],
            },
        ),
        (
            "milestone",
            {"title": "Milestone issue", "milestone": Ref("milestone-open", "id")},
        ),
        (
            "closed-milestone",
            {"title": "Closed milestone", "milestone": Ref("milestone-closed", "id")},
        ),
        ("future", {"title": "Future due", "due_date": "2030-06-15T00:00:00Z"}),
        ("past", {"title": "Past due", "due_date": "2020-02-29T00:00:00Z"}),
        ("branch-ref", {"title": "Branch reference", "ref": "main"}),
        ("mention", {"title": "Mention issue", "body": "@bob please review #1"}),
        ("whitespace", {"title": "  Trim spaces  ", "body": "  body spaces  "}),
    ]
    for sc, body in scenarios:
        key = "issue-" + sc
        ep = pathref(rp + "/issues/{n}", n=Ref(key, "number"))
        # Gitea issue response uses number; all subsequent references use returned numbering.
        a(
            "issue-create",
            sc,
            "create",
            "POST",
            rp + "/issues",
            "alice",
            body=body,
            save=key,
            status=201,
        )
        a("issue-create", sc, "read", "GET", ep, "bob", status=200)
        a("issue-create", sc, "public", "GET", ep, None, status=200)
        a(
            "issue-edit",
            sc,
            "body",
            "PATCH",
            ep,
            "alice",
            body={"body": body.get("body", "") + "\nEdited content " + sc},
            status=201,
        )
        a(
            "issue-edit",
            sc,
            "title",
            "PATCH",
            ep,
            "alice",
            body={"title": "Updated " + body["title"].strip()},
            status=201,
        )
        a("issue-edit", sc, "after-edit", "GET", ep, "alice", status=200)
        cp = lambda c, e=ep: e(c) + "/comments"
        a(
            "comments",
            sc,
            "create",
            "POST",
            cp,
            "bob",
            body={"body": "Comment " + sc + " **formatted**"},
            save="comment-" + sc,
            status=201,
        )
        a("comments", sc, "list", "GET", cp, "alice", status=200)
        ce = pathref(rp + "/issues/comments/{id}", id=Ref("comment-" + sc, "id"))
        a("comments", sc, "read", "GET", ce, "carol", status=200)
        a(
            "comments",
            sc,
            "outsider-edit",
            "PATCH",
            ce,
            "carol",
            body={"body": "attempted takeover"},
        )
        a(
            "comments",
            sc,
            "author-edit",
            "PATCH",
            ce,
            "bob",
            body={"body": "Edited comment " + sc},
            status=200,
        )
        a("comments", sc, "edited-read", "GET", ce, "alice", status=200)
        a(
            "issue-state",
            sc,
            "close",
            "PATCH",
            ep,
            "bob",
            body={"state": "closed"},
            status=201,
        )
        a("issue-state", sc, "closed-read", "GET", ep, "alice", status=200)
        if sc not in ("closed-create", "closed-milestone", "past"):
            a(
                "issue-state",
                sc,
                "reopen",
                "PATCH",
                ep,
                "alice",
                body={"state": "open"},
                status=201,
            )
            a("issue-state", sc, "reopened-read", "GET", ep, "alice", status=200)
    for sc, body in [
        ("empty-title", {"title": ""}),
        ("missing-title", {"body": "body only"}),
        (
            "invalid-assignee",
            {"title": "Invalid assignee", "assignees": ["pbp-absent-user"]},
        ),
        ("outsider-assignee", {"title": "Outsider assignee", "assignees": ["carol"]}),
        ("missing-label", {"title": "Missing label", "labels": [99999999]}),
        ("missing-milestone", {"title": "Missing milestone", "milestone": 99999999}),
        ("bad-date", {"title": "Bad due date", "due_date": "not-a-date"}),
    ]:
        a("issue-validation", sc, "create", "POST", rp + "/issues", "alice", body=body)
    for state in ("open", "closed", "all"):
        # API ListIssues fixes created-desc order; browser sort coverage is in
        # browser_views. Do not count ignored query variants as distinct cases.
        a(
            "issue-filter",
            state,
            "list",
            "GET",
            rp + "/issues",
            "alice",
            params={"state": state},
            status=200,
        )
        for typ in ("issues", "pulls", "all"):
            a(
                "issue-type-filter",
                state + "-" + typ,
                "list",
                "GET",
                rp + "/issues",
                "alice",
                params={"state": state, "type": typ},
                status=200,
            )
        for mode, params in [
            ("bug", {"labels": "bug"}),
            ("enhancement", {"labels": "enhancement"}),
            ("both-labels", {"labels": "bug,enhancement"}),
            ("missing-label", {"labels": "absent"}),
            ("assigned-bob", {"assigned_by": "bob"}),
            ("assigned-alice", {"assigned_by": "alice"}),
            ("created-alice", {"created_by": "alice"}),
            ("created-bob", {"created_by": "bob"}),
            ("mentioned-bob", {"mentioned_by": "bob"}),
            (
                "milestone",
                {"milestones": lambda c: str(c.state["milestone-open"]["id"])},
            ),
            ("q-unicode", {"q": "café"}),
            ("q-missing", {"q": "no-match-zz"}),
        ]:
            a(
                "issue-query",
                state + "-" + mode,
                "list",
                "GET",
                rp + "/issues",
                "alice",
                params={"state": state, **params},
                status=200,
            )
    for page, limit in [
        (1, 1),
        (2, 1),
        (1, 4),
        (2, 4),
        (3, 4),
        (5, 4),
        (100, 3),
        (0, 3),
        (-1, 3),
        (1, 0),
        (1, 50),
    ]:
        a(
            "issue-pagination",
            f"p{page}-l{limit}",
            "list",
            "GET",
            rp + "/issues",
            "alice",
            params={"state": "all", "page": page, "limit": limit},
            status=200,
        )
    for actor in (None, "alice", "bob", "carol"):
        for mode, params in [
            ("all", {}),
            ("open", {"state": "open"}),
            ("closed", {"state": "closed"}),
            ("text", {"q": "Markdown"}),
            ("assigned", {"assigned": True}),
            ("created", {"created": True}),
            ("mentioned", {"mentioned": True}),
            ("review-requested", {"review_requested": True}),
        ]:
            a(
                "issue-global-search",
                (actor or "anonymous") + "-" + mode,
                "search",
                "GET",
                "repos/issues/search",
                actor,
                params={"type": "issues", **params},
            )
    for target in ("plain", "labeled", "multi-label", "closed-create"):
        ep = pathref(rp + "/issues/{n}/labels", n=Ref("issue-" + target, "number"))
        for step, method, body in [
            ("read", "GET", None),
            ("add", "POST", {"labels": [Ref("label-enhancement", "id")]}),
            ("after-add", "GET", None),
            (
                "replace",
                "PUT",
                {"labels": [Ref("label-bug", "id"), Ref("label-needs review", "id")]},
            ),
            ("after-replace", "GET", None),
            ("clear", "DELETE", None),
            ("after-clear", "GET", None),
        ]:
            a("issue-labels", target, step, method, ep, "alice", body=body)
    # Eight supported reactions, issue and comment targets, two users, duplicate and removal.
    for target in ("issue", "comment"):
        if target == "issue":
            ep = pathref(rp + "/issues/{n}/reactions", n=Ref("issue-plain", "number"))
        else:
            ep = pathref(
                rp + "/issues/comments/{id}/reactions", id=Ref("comment-plain", "id")
            )
        for reaction in (
            "+1",
            "-1",
            "laugh",
            "hooray",
            "confused",
            "heart",
            "rocket",
            "eyes",
        ):
            sc = target + "-" + reaction.replace("+", "plus").replace("-", "minus")
            for step, method, user, body in [
                ("add", "POST", "bob", {"content": reaction}),
                ("repeat", "POST", "bob", {"content": reaction}),
                ("second-user", "POST", "carol", {"content": reaction}),
                ("list", "GET", "alice", None),
                ("remove", "DELETE", "bob", {"content": reaction}),
                ("after-remove", "GET", "alice", None),
            ]:
                a("reactions", sc, step, method, ep, user, body=body)
        a(
            "reactions",
            target + "-invalid",
            "add",
            "POST",
            ep,
            "bob",
            body={"content": "not-a-reaction"},
        )
    for target in ("plain", "closed-create", "assigned"):
        ep = pathref(rp + "/issues/{n}", n=Ref("issue-" + target, "number"))
        for user in ("alice", "bob", "carol"):
            sc = target + "-" + user
            a(
                "issue-subscription",
                sc,
                "subscribe",
                "PUT",
                lambda c, e=ep, u=user: e(c) + "/subscriptions/" + u,
                user,
            )
            a(
                "issue-subscription",
                sc,
                "check",
                "GET",
                lambda c, e=ep: e(c) + "/subscriptions/check",
                user,
            )
            a(
                "issue-subscription",
                sc,
                "list",
                "GET",
                lambda c, e=ep: e(c) + "/subscriptions",
                user,
            )
            a(
                "issue-subscription",
                sc,
                "unsubscribe",
                "DELETE",
                lambda c, e=ep, u=user: e(c) + "/subscriptions/" + u,
                user,
            )
    for target in ("plain", "future", "past"):
        ep = pathref(rp + "/issues/{n}/deadline", n=Ref("issue-" + target, "number"))
        a(
            "deadlines",
            target,
            "change",
            "POST",
            ep,
            "alice",
            body={"due_date": "2031-01-02T00:00:00Z"},
        )
        a(
            "deadlines",
            target,
            "clear",
            "PATCH",
            pathref(rp + "/issues/{n}", n=Ref("issue-" + target, "number")),
            "alice",
            body={"unset_due_date": True},
        )
    for target in ("plain", "markdown", "unicode", "html"):
        ep = pathref(rp + "/issues/{n}/pin", n=Ref("issue-" + target, "number"))
        a("issue-pin", target, "pin", "POST", ep, "alice")
        a("issue-pin", target, "list", "GET", rp + "/issues/pinned", "alice")
        a("issue-pin", target, "unpin", "DELETE", ep, "alice")
    for target in ("plain", "markdown", "unicode"):
        ep = pathref(
            rp + "/issues/{n}/dependencies", n=Ref("issue-" + target, "number")
        )
        body = {
            "owner": "alice",
            "repo": "pbp-issues",
            "index": Ref("issue-assigned", "number"),
        }
        a("issue-dependencies", target, "add", "POST", ep, "alice", body=body)
        a("issue-dependencies", target, "list", "GET", ep, "alice")
        a("issue-dependencies", target, "remove", "DELETE", ep, "alice", body=body)
        a("issue-dependencies", target, "empty", "GET", ep, "alice")
    for target in ("plain", "html", "unicode", "closed-create"):
        ep = pathref(rp + "/issues/comments/{id}", id=Ref("comment-" + target, "id"))
        a("comment-delete", target, "outsider", "DELETE", ep, "carol")
        a("comment-delete", target, "author", "DELETE", ep, "bob", status=204)
        a("comment-delete", target, "gone", "GET", ep, "alice", status=404)
