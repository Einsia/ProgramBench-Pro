"""Official review decisions, approval thresholds and real browser merging."""

import base64, re, time, urllib.parse
from harness import Ref, b64, blob_sha, pathref, subset
from reference.registry import add


def review_in_browser(c, ui, endpoint, actor, event, body, key):
    route = "/" + endpoint.removeprefix("repos/")
    p, _ = ui.goto(route + "/files", actor)
    names = (
        ("Approve", "Approve Review")
        if event == "APPROVED"
        else ("Request changes", "Request Changes", "Submit Changes Request")
    )
    try:
        ui.button(p, *names)
        opened = True
    except AssertionError:
        opened = False
    if not opened:
        for label in ("Review comment", "Review body", "Comment", "Content"):
            pattern = ui.label_pattern(label)
            fields = (
                p.get_by_label(pattern).all()
                + p.get_by_placeholder(pattern).all()
                + p.get_by_role("textbox", name=pattern).all()
            )
            if any(el.is_visible() for el in fields):
                opened = True
                break
    if not opened:
        opener = next(ui.actions(
            p, re.compile(r"^(?:Review(?: changes)?|Submit review)(?:\s+\d+)?$", re.I)
        ), None)
        assert opener is not None, "accessible review action missing"
        opener.click()
        ui.event("click", names=["Review"])
    ui.fill(
        p,
        "content",
        body,
        labels=["Review comment", "Review body", "Comment", "Content"],
        placeholder="Review comment",
    )
    try:
        ui.button(p, *names)
        direct = True
    except AssertionError:
        direct = False
    if direct:
        ui.submit(p, *names)
    else:
        ui.choice(
            p,
            "event",
            event,
            labels=["Review Type", "Review decision", "Review"],
            option_labels=(
                ["Approve", "Approved"]
                if event == "APPROVED"
                else ["Request changes", "Changes requested"]
            ),
        )
        ui.submit(p, "Submit Review", "Submit review", "Submit", "Save Review")
    reviews = ui.corroborate(
        endpoint + "/reviews",
        actor,
        predicate=lambda xs: any(
            x["user"]["login"] == actor and x["state"] == event and x["body"] == body
            for x in xs
        ),
    )
    matches = [
        x
        for x in reviews
        if x["user"]["login"] == actor and x["state"] == event and x["body"] == body
    ]
    assert len(matches) == 1, "review save is missing or duplicated"
    review = matches[0]
    c.state[key] = review
    p, _ = ui.goto(route, actor)
    ui.require(p, body)
    return {
        "review": c.norm.clean(
            review, scope=c.norm.repository_scope(c.base + "/api/v1/" + endpoint)
        ),
        "persisted_visible": True,
    }


def merge_action(ui, page):
    """Prefer an enabled semantic form submit over a method/menu opener."""
    choices = []
    for rank, name in enumerate(("Create merge commit", "Merge Pull Request", "Merge")):
        for role in ("button", "link"):
            for el in page.get_by_role(
                role, name=ui.action_pattern(name)
            ).all():
                if el.is_visible() and el.is_enabled():
                    submit = el.evaluate(
                        '(e)=>Boolean(e.form) && (e.tagName==="BUTTON" || e.tagName==="INPUT") && e.type==="submit"'
                    )
                    choices.append((0 if submit else 1, rank, el, submit))
    assert choices, "visible merge-commit action missing"
    return sorted(choices, key=lambda x: x[:2])[0][2:]


def merge_in_browser(c, ui, endpoint, actor, contents, timeout=10, filename='review.txt'):
    before = c.pull_ready(endpoint, True)
    route = "/" + endpoint.removeprefix("repos/")
    p, _ = ui.goto(route, actor)
    for label in ("Merge method", "Merge strategy", "Merge type"):
        options = p.get_by_role(
            "combobox", name=re.compile("^" + re.escape(label) + r"(?:\s|$)", re.I)
        ).all()
        control = next((el for el in options if el.is_visible()), None)
        if control is not None:
            if control.evaluate("(e)=>e.tagName") == "SELECT":
                labels = [
                    el.inner_text().strip() for el in control.locator("option").all()
                ]
                selected = next(
                    (
                        x
                        for x in labels
                        if re.fullmatch(r"(?:Create )?merge(?: commit)?", x, re.I)
                    ),
                    None,
                )
                assert selected, "merge commit method missing from visible choices"
                control.select_option(label=selected)
            else:
                ui.choice(
                    p,
                    "merge_method",
                    "merge",
                    labels=[label],
                    option_labels=["Create merge commit", "Merge commit", "Merge"],
                )
            break
    visible_actions = [
        el.element_handle()
        for role in ("button", "link")
        for el in p.get_by_role(role).all()
        if el.is_visible()
    ]
    initial_forms = {
        form.aria_snapshot() for form in p.locator("form").all() if form.is_visible()
    }
    mutations = []
    confirmed = False
    navigated = [False]

    def navigation(frame):
        if frame == p.main_frame:
            navigated[0] = True

    def newly_visible(el):
        return navigated[0] or not el.evaluate(
            "(e,old)=>old.includes(e)", visible_actions
        )

    def requested(req):
        if req.method in ("POST", "PUT", "PATCH", "DELETE"):
            mutations.append(req.method)

    p.on("request", requested)
    p.on("framenavigated", navigation)
    action, submitted = merge_action(ui, p)
    action.click()
    ui.event("click", names=["merge commit action"])
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        r, obj = c.request("GET", endpoint, actor)
        assert r.status_code == 200, "merge target disappeared"
        if obj.get("merged"):
            break
        if not confirmed:
            try:
                confirm = ui.button(p, "Confirm Merge", "Confirm merge", "Confirm")
            except AssertionError:
                confirm = None
            if confirm is not None and newly_visible(confirm):
                confirm.click()
                ui.event("click", names=["Confirm Merge"])
                confirmed = True
            else:
                # A method opener may reveal a confirmation form. It is not
                # permission to retry an already-submitted mutation.
                for form in p.locator("form").all():
                    if not form.is_visible():
                        continue
                    try:
                        button, is_submit = merge_action(ui, form)
                    except AssertionError:
                        continue
                    # A POST can legitimately open a second confirmation page.
                    # After a submission, require newly exposed editing controls
                    # (or an explicit Confirm action above), never the same form.
                    editing = any(
                        el.is_visible() for el in form.get_by_role("textbox").all()
                    )
                    new_form = form.aria_snapshot() not in initial_forms
                    if (
                        is_submit
                        and newly_visible(button)
                        and (
                            (not submitted and not mutations) or (editing and new_form)
                        )
                    ):
                        button.click()
                        ui.event("click", names=["new merge confirmation"])
                        confirmed = True
                        break
        p.wait_for_timeout(100)
    p.remove_listener("request", requested)
    p.remove_listener("framenavigated", navigation)
    obj = ui.corroborate(endpoint, actor, want={"merged": True, "state": "closed"})
    assert obj["merged_by"]["login"] == actor, "merge author differs from browser actor"
    rp = endpoint.split("/pulls/", 1)[0]
    r, file = c.request("GET", rp + "/contents/" + filename, actor)
    assert (
        r.status_code == 200 and base64.b64decode(file["content"]) == contents.encode()
    ), "browser merge did not apply the proposed file bytes"
    r, commit = c.request("GET", rp + "/git/commits/" + obj["merge_commit_sha"], actor)
    assert r.status_code == 200 and [x["sha"] for x in commit["parents"]] == [
        before["base"]["sha"],
        before["head"]["sha"],
    ], "browser used the wrong merge method or parent graph"
    # API completion can precede the application's fetch-triggered navigation.
    # Await the resulting visible state before starting an independent refresh.
    from playwright.sync_api import expect

    expect(p.locator("body")).to_contain_text(
        re.compile(r"\bMerged\b"), use_inner_text=True, timeout=10000
    )
    p.wait_for_load_state("domcontentloaded")
    p.reload(wait_until="domcontentloaded")
    ui.require(p, "Merged")
    return {
        "pull": c.norm.clean(
            obj, scope=c.norm.repository_scope(c.base + "/api/v1/" + endpoint)
        ),
        "main_content": contents,
        "persisted_visible": True,
    }


def unchanged_after_denial(c, r, p, endpoint, rp, head):
    rr, pull = c.request("GET", endpoint, "bob")
    assert rr.status_code == 200
    subset(pull, {"state": "open", "merged": False})
    assert pull["head"]["sha"] == head, "denied merge modified proposed head"
    rr, file = c.request("GET", rp + "/contents/review.txt", "bob")
    assert (
        rr.status_code == 200
        and base64.b64decode(file["content"]) == b"before review\n"
    ), "denied merge changed main contents"


def build(s):
    a = s.api
    for sc, required in [("rejected-until-resolved", 1), ("two-approvals", 2)]:
        name = "pbp-review-gate-" + sc
        rp = "repos/alice/" + name
        key = "review-gate-" + sc
        for step, method, path, actor, body, status, save in [
            (
                "repository",
                "POST",
                "user/repos",
                "alice",
                {"name": name, "auto_init": True},
                201,
                None,
            ),
            (
                "writer",
                "PUT",
                rp + "/collaborators/bob",
                "alice",
                {"permission": "write"},
                204,
                None,
            ),
            (
                "reviewer",
                "PUT",
                rp + "/collaborators/carol",
                "alice",
                {"permission": "write"},
                204,
                None,
            ),
            (
                "base-file",
                "POST",
                rp + "/contents/review.txt",
                "alice",
                {"content": b64("before review\n"), "message": "Review base"},
                201,
                key + "-base",
            ),
            (
                "branch",
                "POST",
                rp + "/branches",
                "bob",
                {"new_branch_name": "feature", "old_branch_name": "main"},
                201,
                None,
            ),
            (
                "proposal",
                "PUT",
                rp + "/contents/review.txt",
                "bob",
                {
                    "branch": "feature",
                    "sha": blob_sha("before review\n"),
                    "content": b64("approved " + sc + "\n"),
                    "message": "Review proposal " + sc,
                },
                200,
                None,
            ),
        ]:
            a(
                "review-gate-fixture",
                sc,
                step,
                method,
                path,
                actor,
                body=body,
                status=status,
                save=save,
            )
        a(
            "review-gates",
            sc,
            "protect-main",
            "POST",
            rp + "/branch_protections",
            "alice",
            body={
                "branch_name": "main",
                "rule_name": "main",
                "enable_push": False,
                "required_approvals": required,
                "block_on_rejected_reviews": True,
            },
            status=201,
            want={"required_approvals": required, "block_on_rejected_reviews": True},
        )
        a(
            "review-gates",
            sc,
            "create-pull",
            "POST",
            rp + "/pulls",
            "bob",
            body={
                "head": "feature",
                "base": "main",
                "title": "Review gate " + sc,
                "body": "Proposal requires meaningful review decisions",
            },
            status=201,
            settle_pull=True,
            save=key,
        )
        ep = pathref(rp + "/pulls/{n}", n=Ref(key, "number"))

        def blocked(step):
            a(
                "review-gates",
                sc,
                step,
                "POST",
                lambda c, e=ep: e(c) + "/merge",
                "alice",
                body={"Do": "merge"},
                status=405,
                before=lambda c, e=ep: c.pull_ready(e(c), True),
                check=lambda c, r, p, e=ep, rp=rp, k=key: unchanged_after_denial(
                    c, r, p, e(c), rp, c.state[k]["head"]["sha"]
                ),
            )

        blocked("missing-approval-denied")
        a(
            "review-gates",
            sc,
            "self-approval-denied",
            "POST",
            lambda c, e=ep: e(c) + "/reviews",
            "bob",
            body={"event": "APPROVED", "body": "Self approval must not count"},
            status=422,
        )
        if required == 1:
            add(
                s,
                "review-gates",
                sc,
                "request-changes-browser",
                lambda c, ui, e=ep, k=key: review_in_browser(
                    c,
                    ui,
                    e(c),
                    "carol",
                    "REQUEST_CHANGES",
                    "Please address the requested changes",
                    k + "-rejected",
                ),
            )
            a(
                "review-gates",
                sc,
                "read-rejection",
                "GET",
                pathref(
                    rp + "/pulls/{n}/reviews/{id}",
                    n=Ref(key, "number"),
                    id=Ref(key + "-rejected", "id"),
                ),
                "bob",
                status=200,
                want={
                    "state": "REQUEST_CHANGES",
                    "body": "Please address the requested changes",
                },
            )
            a(
                "review-gates",
                sc,
                "independent-approval",
                "POST",
                lambda c, e=ep: e(c) + "/reviews",
                "alice",
                body={"event": "APPROVED", "body": "Independent maintainer approval"},
                status=200,
                want={"state": "APPROVED"},
                save=key + "-approved-alice",
            )
            blocked("rejection-still-denies")
            add(
                s,
                "review-gates",
                sc,
                "resolve-with-approval-browser",
                lambda c, ui, e=ep, k=key: review_in_browser(
                    c,
                    ui,
                    e(c),
                    "carol",
                    "APPROVED",
                    "Requested changes are addressed",
                    k + "-approved-carol",
                ),
            )
        else:
            a(
                "review-gates",
                sc,
                "first-approval",
                "POST",
                lambda c, e=ep: e(c) + "/reviews",
                "carol",
                body={"event": "APPROVED", "body": "First of two required approvals"},
                status=200,
                want={"state": "APPROVED"},
                save=key + "-approved-carol",
            )
            blocked("one-of-two-denied")
            add(
                s,
                "review-gates",
                sc,
                "second-approval-browser",
                lambda c, ui, e=ep, k=key: review_in_browser(
                    c,
                    ui,
                    e(c),
                    "alice",
                    "APPROVED",
                    "Second independent approval",
                    k + "-approved-alice",
                ),
            )
        a(
            "review-gates",
            sc,
            "review-list",
            "GET",
            lambda c, e=ep: e(c) + "/reviews",
            "bob",
            status=200,
        )
        for reviewer in ("alice", "carol"):
            a(
                "review-gates",
                sc,
                "read-approved-" + reviewer,
                "GET",
                pathref(
                    rp + "/pulls/{n}/reviews/{id}",
                    n=Ref(key, "number"),
                    id=Ref(key + "-approved-" + reviewer, "id"),
                ),
                "bob",
                status=200,
                want={"state": "APPROVED"},
            )
        add(
            s,
            "review-gates",
            sc,
            "merge-browser",
            lambda c, ui, e=ep, sc=sc: merge_in_browser(
                c, ui, e(c), "bob", "approved " + sc + "\n"
            ),
        )
        a(
            "review-gates",
            sc,
            "merged-state",
            "GET",
            ep,
            "alice",
            status=200,
            want={"merged": True, "state": "closed"},
        )
        a(
            "review-gates",
            sc,
            "main-content",
            "GET",
            rp + "/contents/review.txt",
            "alice",
            status=200,
            want={"content": b64("approved " + sc + "\n")},
        )
        a(
            "review-gates",
            sc,
            "reviews-after-merge",
            "GET",
            lambda c, e=ep: e(c) + "/reviews",
            "bob",
            status=200,
        )
