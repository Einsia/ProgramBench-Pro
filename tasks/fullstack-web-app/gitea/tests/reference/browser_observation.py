"""Reference-only visible denial checks."""
import base64
import re
import urllib.parse


def denied_page(c, ui, page, path, status, actor):
    """Benign denial wording is free, while private contents must remain hidden.

    A requested name/path can be echoed by a generic error page. Inspect known
    private metadata/content, not words such as "Not Found" or the request URL.
    Privileged read checks are observer-only and never given to the browser.
    """
    body = ui.text(page)
    secrets = []
    parts = urllib.parse.urlsplit(path).path.split("/")
    if len(parts) >= 3 and parts[1] not in ("org", "user", "explore", "repo"):
        owner, name = parts[1:3]
        r, repo = c.request("GET", "repos/" + owner + "/" + name, "alice")
        if r.status_code == 200 and repo.get("private"):
            if repo.get("description"):
                secrets.append(repo["description"])
            suffix = "/".join(parts[3:])
            if re.match(r"issues/\d+$", suffix):
                rr, item = c.request(
                    "GET", "repos/" + owner + "/" + name + "/" + suffix, "alice"
                )
                if rr.status_code == 200:
                    secrets.extend(
                        x for x in (item.get("title"), item.get("body")) if x
                    )
            if suffix.startswith("src/branch/"):
                chunks = suffix.split("/", 3)
                if len(chunks) == 4:
                    rr, item = c.request(
                        "GET",
                        "repos/" + owner + "/" + name + "/contents/" + chunks[3],
                        "alice",
                        params={"ref": chunks[2]},
                    )
                    if rr.status_code == 200 and item.get("content"):
                        contents = base64.b64decode(item["content"]).decode(
                            errors="replace"
                        )
                        secrets.extend(
                            x
                            for x in contents.splitlines()
                            if len(x) > 12 and name not in x
                        )
            # Generic navigation and a self-link on an error page are harmless;
            # actual private file/download/commit links expose repository data.
            assert not ui.links(
                page,
                r"^/" + re.escape(owner + "/" + name) + r"/(?:src|raw|commit)/",
                normalize=False,
            ), "private resource links exposed by denied page"
    organization = (
        parts[2]
        if len(parts) > 2 and parts[1] == "org"
        else (parts[1] if len(parts) > 1 else "")
    )
    if organization.startswith("pbp-org-") or organization.startswith("pbp-ui-org-"):
        r, org = c.request("GET", "orgs/" + organization, "alice")
        if r.status_code == 200 and org.get("visibility") == "private":
            secrets.extend(
                x
                for x in (org.get("description"), org.get("full_name"))
                if x and x != organization
            )
    for secret in secrets:
        assert secret not in body, "private resource contents exposed by denied page"
    login = urllib.parse.urlsplit(page.url).path == "/user/login"
    if login:
        ui.field(page, "user_name")
        ui.field(page, "password")
        ui.button(page, "Sign In", "Log In", "Login")
    return {"access": "login" if login else "denied", "private_content_exposed": False}

