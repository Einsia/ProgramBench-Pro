"""Local deployment capabilities: Git LFS, generic/npm packages, OCI registry, package UI."""

import base64, hashlib, json, re, time, urllib.parse
from email.message import Message
from harness import Headers, Ref, b64, pathref, resolve, subset, lfs_batch_payload, unordered
from reference.registry import add, view
from reference.browser_observation import denied_page

LFS_HEADERS = {
    "Accept": "application/vnd.git-lfs+json",
    "Content-Type": "application/vnd.git-lfs+json",
}


def media_type(value, json_response=False):
    """MIME syntax is not payload identity; retain nondefault parameters."""
    main = value.split(";", 1)[0].strip().lower()
    assert re.fullmatch(
        r"[!#$%&'*+.^_`|~0-9a-z-]+/[!#$%&'*+.^_`|~0-9a-z-]+", main
    ), "invalid protocol Content-Type"
    message = Message()
    message["Content-Type"] = value
    parameters = []
    for key, val in message.get_params()[1:]:
        key = key.lower()
        if key == "charset":
            val = val.lower()
            if val == "utf8":
                val = "utf-8"
            if (
                json_response
                and (main == "application/json" or main.endswith("+json"))
                and val == "utf-8"
            ):
                continue
        parameters.append([key, val])
    return {"type": main, "parameters": sorted(parameters)}


def registry_upload_location(c, location):
    """Use the advertised local upload URL, including its opaque state query."""
    path = c.local_resource_path(location)
    parsed = urllib.parse.urlsplit(path)
    assert (
        parsed.path.startswith("/v2/") and parsed.path[len("/v2/") :]
    ), "upload Location is outside the exposed local registry"
    return path


def registry_finish_url(location, digest):
    """Appending the digest must preserve the exact server-supplied query."""
    parsed = urllib.parse.urlsplit(location)
    assert not any(
        key == "digest" for key, _ in urllib.parse.parse_qsl(parsed.query)
    ), "upload Location already contains a final digest"
    query = parsed.query + ("&" if parsed.query else "") + "digest=" + urllib.parse.quote(
        digest, safe=":"
    )
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))


def protocol_observation(
    c,
    r,
    payload,
    method,
    json_response=False,
    representation_type=None,
    range_spec=None,
    upload_offset=None,
    blob_content=None,
    upload_repository=None,
):
    """Only explicitly JSON protocol messages use semantic JSON comparison.

    Downloads (including JSON files and OCI content-addressed manifests) remain
    byte-exact. An empty successful non-HEAD response has no representation for
    Content-Type to describe; digest, upload ID, location and range stay strict.
    """
    observation = {"status": r.status_code}
    if json_response:
        assert isinstance(payload, (dict, list)), "protocol response is not JSON"
        observation["json"] = c.norm.clean(payload)
    else:
        observation["bytes_base64"] = base64.b64encode(r.content).decode()
    for key in (
        "Content-Type",
        "Docker-Content-Digest",
        "Docker-Upload-Uuid",
        "Location",
        "Range",
        "Content-Range",
    ):
        if key == "Content-Type" and blob_content is not None:
            # Registry blobs are opaque content-addressed bytes. The pinned
            # server sniffs plain text/gzip; the protocol's octet-stream is
            # equally valid. This exception never applies to manifests.
            if method == "HEAD" and key not in r.headers:
                observation[key] = media_type("application/octet-stream")
                continue
            parsed = media_type(r.headers.get(key, ""))
            allowed = {"application/octet-stream": []}
            if blob_content.startswith(b"\x1f\x8b\x08"):
                allowed.update({"application/x-gzip": [], "application/gzip": []})
            try:
                text = blob_content.decode("utf-8")
                if all(ch in "\n\r\t" or ord(ch) >= 32 for ch in text):
                    allowed["text/plain"] = [[], [["charset", "utf-8"]]]
                    if text.isascii():
                        allowed["text/plain"].append([["charset", "us-ascii"]])
            except UnicodeDecodeError:
                pass
            assert parsed["type"] in allowed, "invalid OCI blob representation type"
            options = allowed[parsed["type"]]
            valid = (
                parsed["parameters"] in options
                if parsed["type"] == "text/plain"
                else parsed["parameters"] == options
            )
            assert valid, "invalid OCI blob representation parameters"
            observation[key] = media_type("application/octet-stream")
            continue
        if key == "Content-Type" and method == "HEAD" and representation_type:
            if key in r.headers:
                assert media_type(r.headers[key]) == media_type(
                    representation_type
                ), "HEAD has incorrect representation type"
            observation[key] = media_type(representation_type)
            continue
        if (
            key == "Content-Type"
            and not r.content
            and 200 <= r.status_code < 300
            and method != "HEAD"
        ):
            continue
        if key in r.headers:
            if key == "Content-Type":
                observation[key] = media_type(r.headers[key], json_response)
            else:
                observation[key] = (
                    c.norm.identity("registry-upload", r.headers[key])
                    if key == "Docker-Upload-Uuid"
                    else c.norm.text(r.headers[key], uri=key == "Location")
                )
    if method == "HEAD" and "Content-Length" in r.headers:
        observation["Content-Length"] = int(r.headers["Content-Length"])
    if blob_content is not None:
        assert (
            method in ("GET", "HEAD") and r.status_code == 200
        ), "invalid OCI blob download status"
        assert re.fullmatch(
            r"/v2/.+/blobs/sha256:[0-9a-f]{64}", urllib.parse.urlsplit(r.url).path
        ), "OCI blob equivalence used outside a blob endpoint"
        digest = "sha256:" + hashlib.sha256(blob_content).hexdigest()
        assert (
            r.headers.get("Docker-Content-Digest") == digest
        ), "OCI blob digest differs"
        assert urllib.parse.urlsplit(r.url).path.endswith(
            "/" + digest
        ), "OCI blob URL identifies another digest"
        if method == "GET":
            assert r.content == blob_content, "OCI blob bytes differ"
        if method == "HEAD":
            assert (
                "Content-Length" in r.headers
            ), "OCI blob HEAD is missing required Content-Length"
        if "Content-Length" in r.headers:
            assert int(r.headers["Content-Length"]) == len(
                blob_content
            ), "OCI blob length differs"
        observation["Content-Length"] = len(blob_content)
    if range_spec is not None:
        start, end, total = range_spec
        # Pinned Gitea 1.22.6 emits total-start here. Accept only that proved
        # legacy value or the RFC full length, with strict interval and bytes.
        value = r.headers.get("Content-Range", "")
        assert value in (
            f"bytes {start}-{end}/{total}",
            f"bytes {start}-{end}/{total-start}",
        ), "partial response has incorrect Content-Range"
        assert len(r.content) == end - start + 1, "partial response length is incorrect"
        observation["Content-Range"] = f"bytes {start}-{end}/{total}"
    if upload_offset is not None:
        request_path = urllib.parse.urlsplit(r.url).path
        if upload_repository is None and re.fullmatch(
            r"/v2/.+/blobs/uploads(?:/[^/]+)?", request_path
        ):
            upload_repository = request_path.split("/blobs/uploads", 1)[0]
        assert method in ("POST", "PATCH", "GET") and re.fullmatch(
            r"/v2/.+", upload_repository or ""
        ), "upload progress exception lacks its original repository scope"
        repository = upload_repository
        canonical_range = f"0-{max(0,upload_offset-1)}"
        # The pinned product's GET progress has an off-by-one end. PATCH
        # responses and standard registries must identify the received interval.
        allowed = {canonical_range}
        if method == "GET":
            allowed.add(f"0-{upload_offset}")
        assert r.headers.get("Range") in allowed, "upload progress reports incorrect received bytes"
        observation["Range"] = canonical_range
        location = registry_upload_location(
            c, r.headers.get("Location", r.url) if method == "GET" else r.headers.get("Location")
        )
        if method != "GET":
            # Prove opaque query state is usable before removing it from the
            # observation. Never invent a fallback upload URL or credential.
            active, _ = c.request(
                "GET", location, None,
                headers={
                    key: value for key, value in r.request.headers.items()
                    if key.lower() not in ("content-length", "content-range", "transfer-encoding", "content-type")
                },
            )
            assert active.status_code == 204, "advertised upload Location is unusable"
            assert active.headers.get("Range") in (
                canonical_range, f"0-{upload_offset}"
            ), "advertised upload Location has incorrect received bytes"
            if "Docker-Upload-Uuid" in r.headers:
                assert active.headers.get("Docker-Upload-Uuid") == r.headers["Docker-Upload-Uuid"], "upload Location identifies another upload UUID"
            if "Location" in active.headers:
                location = registry_upload_location(c, active.headers["Location"])
                r.headers["Location"] = active.headers["Location"]
        r.headers.setdefault("Location", location)
        upload_id = r.headers.get("Docker-Upload-Uuid")
        canonical_location = (
            repository + "/blobs/uploads/" + upload_id
            if upload_id
            else urllib.parse.urlsplit(location).path
        )
        observation["Location"] = c.norm.text(canonical_location, uri=True)
    return observation


def binary(
    s,
    family,
    scenario,
    step,
    method,
    path,
    actor="alice",
    data=None,
    headers=None,
    status=200,
    expected=None,
    save=None,
    json_response=False,
    representation_type=None,
    range_spec=None,
    upload_offset=None,
    blob_content=None,
    upload_repository=None,
):
    def action(c):
        ep = resolve(path, c)
        r, p = c.request(
            method, ep, actor, headers=resolve(headers, c), data=resolve(data, c)
        )
        assert r.status_code == status, f"{method} {ep}: {r.status_code} {str(p)[:400]}"
        if expected is not None:
            assert r.content == expected, "binary content differs"
        if r.status_code >= 400:
            if save:
                c.state[save] = {"body": p, "headers": Headers(r.headers), "bytes": r.content}
            return c.observe(r, p)
        observation = protocol_observation(
            c,
            r,
            p,
            method,
            json_response,
            representation_type,
            range_spec,
            upload_offset,
            blob_content,
            upload_repository,
        )
        if save:
            c.state[save] = {"body": p, "headers": Headers(r.headers), "bytes": r.content}
        if (
            method == "PUT"
            and re.fullmatch(r"/v2/.+/manifests/[^/]+", urllib.parse.urlsplit(ep).path)
            and status == 201
        ):
            sent = resolve(data, c)
            digest = "sha256:" + hashlib.sha256(sent).hexdigest()
            assert (
                r.headers.get("Docker-Content-Digest") == digest
            ), "published manifest digest differs from its bytes"
            loc = urllib.parse.urlsplit(c.local_resource_path(r.headers.get("Location", "")))
            root = urllib.parse.urlsplit(ep).path.rsplit("/", 1)[0] + "/"
            assert (
                loc.path.startswith(root)
                and loc.path[len(root) :]
                and "/" not in loc.path[len(root) :]
                and not loc.query
            ), "manifest Location identifies another repository"
            rr, _ = c.request("GET", loc.path, actor, headers=resolve(headers, c))
            assert (
                rr.status_code == 200
                and rr.content == sent
                and rr.headers.get("Docker-Content-Digest") == digest
            ), "manifest Location does not retrieve the published bytes"
            observation["Location"] = root + digest
        return observation

    s.add(family, scenario, step, action)


def checked_lfs_actions(c, r, p, lp, data, operation=None):
    """Validate actual Basic Transfer actions before canonicalizing their URLs.

    The batch operation's returned plan is exercised against its real object;
    later explicit upload/verify/download CASEs retain their endpoint, response,
    permission and idempotent-write checks. No action receives fallback caller
    credentials: only its advertised headers are sent to a local-origin URL.
    """
    if (
        r.status_code != 200
        or not isinstance(p, dict)
        or p.get("transfer", "basic") != "basic"
    ):
        return
    normalized = lfs_batch_payload(p)
    oid = hashlib.sha256(data).hexdigest()
    size = len(data)
    rows = normalized["objects"]
    assert (
        len(rows) == 1
        and rows[0]["oid"] == oid
        and type(rows[0]["size"]) is int
        and rows[0]["size"] == size
    ), "LFS batch identifies the wrong object or size"
    original = p["objects"][0]
    obj = {**rows[0]}
    assert obj.get("actions") is None or isinstance(
        obj["actions"], dict
    ), "LFS actions must be a map"
    actions = obj.get("actions") or {}
    if operation is None:
        operation = json.loads(r.request.body)["operation"]
    assert operation in ("upload", "download"), "invalid LFS transfer operation"
    if obj.get("error"):
        assert not actions, "LFS object has both actions and an error"
        return  # An error is still compared as an error, never proof of presence.
    assert isinstance(actions, dict), "LFS actions must be a map"
    assert set(actions) <= (
        {"upload", "verify"} if operation == "upload" else {"download"}
    ), "LFS action is inappropriate for the requested operation"
    if operation == "download":
        assert "download" in actions, "successful LFS download lacks a usable action"
    actor = getattr(r, "pbp_actor", "alice")

    def use(name, body=None, raw=None):
        action = original["actions"][name]
        path = c.local_resource_path(action["href"])
        headers = dict(action.get("header") or {})
        defaults = {
            "upload": {"Content-Type": "application/octet-stream"},
            "verify": LFS_HEADERS,
        }.get(name, {})
        for k, v in defaults.items():
            if k.lower() not in {key.lower() for key in headers}:
                headers[k] = v
        rr, result = c.request(
            {"upload": "PUT", "download": "GET", "verify": "POST"}[name],
            path,
            None,
            body=body,
            data=raw,
            headers=headers,
        )
        assert rr.status_code == 200, "LFS " + name + " action is unusable"
        if name == "download":
            assert (
                rr.content == data and hashlib.sha256(rr.content).hexdigest() == oid
            ), "LFS action returned another object"
        if "Content-Length" in rr.headers:
            assert int(rr.headers["Content-Length"]) == len(
                rr.content
            ), "LFS action response length is incorrect"
        return rr, result

    if "upload" in actions:
        use("upload", raw=data)
        rr, _ = c.request("GET", lp + "/objects/" + oid, actor)
        assert (
            rr.status_code == 200 and rr.content == data
        ), "LFS advertised upload did not save the exact object in its repository"
    if "verify" in actions:
        use("verify", body={"oid": oid, "size": size})
        rr, _ = c.request("GET", lp + "/objects/" + oid, actor)
        assert (
            rr.status_code == 200 and rr.content == data
        ), "LFS verify refers to a missing or different object"
        # A successful no-op endpoint is not a verification operation. A valid
        # but absent object must be rejected by this same advertised callback.
        wrong = {"oid": "0" * 64, "size": size}
        rr, _ = c.request("GET", lp + "/objects/" + wrong["oid"], actor)
        assert (
            rr.status_code == 404
        ), "LFS negative verification fixture unexpectedly exists"
        action = original["actions"]["verify"]
        headers = {**LFS_HEADERS, **(action.get("header") or {})}
        rr, _ = c.request(
            "POST",
            c.local_resource_path(action["href"]),
            None,
            body=wrong,
            headers=headers,
        )
        assert rr.status_code == 404, "LFS verify callback accepts a missing object"
    if "download" in actions:
        use("download")
    # Both a truthful skip and a completed upload must expose the exact object
    # in this repository. A global content store is not a public requirement.
    if operation == "upload":
        rr, _ = c.request("GET", lp + "/objects/" + oid, actor)
        assert (
            rr.status_code == 200
            and rr.content == data
            and hashlib.sha256(rr.content).hexdigest() == oid
        ), "LFS upload plan falsely claims the repository object is present"
        if "Content-Length" in rr.headers:
            assert (
                int(rr.headers["Content-Length"]) == size
            ), "LFS stored object size differs"
        # The optional upload/verify plan is an instruction already executed,
        # not product state. Preserve unknown extension metadata instead of a
        # general ignore-extra-fields rule. Opaque auth is only waived after use.
        extensions = {
            name: {
                k: v
                for k, v in action.items()
                if k not in ("href", "header", "expires_at", "expires_in")
            }
            for name, action in actions.items()
        }
        for name, action in actions.items():
            extra_headers = {
                k: v
                for k, v in action.get("header", {}).items()
                if k not in ("authorization", "accept", "content-type")
            }
            if extra_headers:
                extensions[name]["header_extensions"] = extra_headers
        extensions = {name: value for name, value in extensions.items() if value}
        saved = {k: v for k, v in obj.items() if k not in ("actions", "authenticated")}
        saved["verified_upload"] = {
            "repository": lp,
            "oid": oid,
            "size": size,
            "sha256": hashlib.sha256(rr.content).hexdigest(),
        }
        if extensions:
            saved["action_extensions"] = extensions
        r.pbp_verified_lfs = {**normalized, "objects": [saved]}
        return
    checked = {}
    for name, action in actions.items():
        # Unknown extensions remain exact instead of acquiring fabricated
        # functional evidence. Non-credential headers and nondefault metadata survive.
        if name in ("upload", "download", "verify"):
            # Only a successfully executed action receives this marker. Opaque
            # server-issued credential value/scheme/presence are not identity;
            # actual usability and object scope above are. Unverified batch
            # payloads keep their original Authorization comparison.
            headers = {
                **(action.get("header") or {}),
                "authorization": "@verified-local-object-access",
            }
            checked[name] = {
                **action,
                "header": headers,
                "href": {
                    "application": "@origin",
                    "repository": lp,
                    "method": {"upload": "PUT", "download": "GET", "verify": "POST"}[
                        name
                    ],
                    "oid": oid,
                    "size": size,
                },
            }
        else:
            checked[name] = action
    r.pbp_verified_lfs = {**normalized, "objects": [{**obj, "actions": checked}]}


def lfs_visible_identity(text, oid, objects):
    """A displayed hash prefix must uniquely identify the expected inventory object."""
    return any(
        oid.startswith(token)
        and sum(other.startswith(token) for other in objects) == 1
        for token in re.findall(r"\b[0-9a-f]{10,64}\b", text)
    )


def lfs_browser_objects(c, ui, path, actor, objects):
    """Visible LFS inventory plus real detail/download navigation, not URL grammar.

    The fixed reference renders small text directly (without a raw link) and
    offers a raw link for opaque binary files. Text previews are checked in the
    browser, then exact repository bytes corroborate invisible final newlines.
    A successful API read alone never satisfies a visible object destination.
    """
    page, status = ui.goto(path, actor)
    if status >= 400 or urllib.parse.urlsplit(page.url).path == "/user/login":
        visible = ui.text(page)
        assert all(
            oid[:10] not in visible for oid in objects
        ), "denied LFS page exposes object identity"
        for el in page.get_by_role("link").all():
            if el.is_visible():
                assert all(
                    oid not in (el.get_attribute("href") or "") for oid in objects
                ), "denied LFS page exposes object link"
        return {"status": status, **denied_page(c, ui, page, path, status, actor)}
    assert status == 200 and ui.text(page).strip(), "LFS object list unavailable"

    def inventory():
        # Semantic rows/listitems are useful grouping, not a required layout.
        # The fallback finds an ordinary containing block with OID and size.
        observed = page.evaluate_handle(
            r"""()=>{
          const links=[...document.querySelectorAll('a,button,[role="link"]')];
          const visible=e=>!!(e.getClientRects().length)&&getComputedStyle(e).visibility!=='hidden';
          const tokens=s=>(s||'').match(/\b[0-9a-f]{10,64}\b/g)||[];
          const rows=new Map();let next=0;const found=[];
          links.forEach(a=>{
            if(!visible(a))return;
            const label=[a.innerText,a.title,a.getAttribute('aria-label')].filter(Boolean).join(' ');
            let row=a.closest('tr,[role="row"],li,[role="listitem"],article');
            if(!row){row=a.parentElement;while(row&&row!==document.body){
              if(/\b\d+(?:\.\d+)?\s*(?:bytes?|[KMGT]?i?B)\b/i.test(row.innerText)&&tokens(row.innerText+' '+label).length)break;
              row=row.parentElement;
            }}
            if(!row||row===document.body)return;
            const ids=tokens(label);const named=ids.length>0;
            if(!named&&!/^(?:download|view|open)(?:\s+(?:object|file|raw))?$/i.test(label.trim()))return;
            const rowids=tokens(row.innerText);const all=[...new Set(named?ids:rowids)];
            if(!all.length)return;
            if(!rows.has(row))rows.set(row,next++);
            found.push({control:a,row:rows.get(row),ids:all,named,text:row.innerText,href:a.href||null});
          });return found;
        }"""
        )
        items = []
        try:
            for entry in observed.get_properties().values():
                item = entry.evaluate(
                    "(x)=>({row:x.row,ids:x.ids,named:x.named,text:x.text,href:x.href})"
                )
                item["control"] = entry.get_property("control").as_element()
                items.append(item)
                entry.dispose()
        finally:
            observed.dispose()
        return items

    def visible_objects():
        # Each row group and ElementHandle belongs only to this document. No
        # old ordinal or locator survives a reload; the visible OID selects it.
        items = inventory()
        groups = {}
        try:
            for item in items:
                matches = {
                    oid
                    for oid in objects
                    if any(oid.startswith(x) for x in item["ids"])
                }
                assert (
                    len(matches) == 1
                ), "visible LFS row identifies an unknown or ambiguous object"
                oid = next(iter(matches))
                assert all(
                    oid.startswith(x) for x in item["ids"]
                ), "visible LFS row has conflicting identity"
                sizes = re.findall(
                    r"\b(\d+(?:\.\d+)?)\s*(bytes?|[KMGT]?i?B)\b", item["text"], re.I
                )
                multipliers = {
                    "b": 1,
                    "byte": 1,
                    "bytes": 1,
                    "kb": 1000,
                    "kib": 1024,
                    "mb": 1000000,
                    "mib": 1048576,
                }
                assert any(
                    unit.lower() in multipliers
                    and float(value) * multipliers[unit.lower()] == len(objects[oid])
                    for value, unit in sizes
                ), "visible LFS object size differs"
                key = (item["row"], oid)
                if key not in groups or item["named"]:
                    groups[key] = item
            ids = [oid for _, oid in groups]
            assert len(ids) == len(objects) and set(ids) == set(
                objects
            ), "visible LFS inventory has missing, extra or duplicate objects"
            chosen = {oid: item for (_, oid), item in groups.items()}
            for item in items:
                if not any(item is kept for kept in chosen.values()):
                    item["control"].dispose()
            return chosen
        except Exception:
            for item in items:
                item["control"].dispose()
            raise

    def release(items):
        for item in items.values():
            item.pop("control").dispose()

    initial = visible_objects()
    release(initial)
    del initial

    def follow(el, detail=None):
        href = el.evaluate("(e)=>e.href||null")
        if href:
            c.local_resource_path(href)
        before = ui.text(page) if detail else None
        docs = []
        downloads = []
        foreign = []

        def response(r):
            if r.request.is_navigation_request() and r.frame == page.main_frame:
                docs.append(r)

        def download_event(download):
            downloads.append(download)

        def boundary(route):
            try:
                c.local_resource_path(route.request.url)
            except AssertionError:
                foreign.append(route.request.url)
                route.abort()
                return
            route.continue_()

        page.on("response", response)
        page.on("download", download_event)
        page.route("**/*", boundary)
        try:
            el.click(no_wait_after=True)
            deadline = time.monotonic() + 8
            same_document = False
            while not downloads and not docs and time.monotonic() < deadline:
                if detail:
                    oid, data = detail
                    visible = ui.text(page)
                    # Client-side routing need not load a new document or even
                    # change its URL. Require a real visible detail transition;
                    # pushState alone (including for an empty object) is a no-op.
                    if visible != before and lfs_visible_identity(visible, oid, objects):
                        links = [
                            x
                            for role in ("link", "button")
                            for x in page.get_by_role(
                                role,
                                name=re.compile(
                                    r"^(?:View Raw|Raw|Download(?: (?:File|Object))?)$",
                                    re.I,
                                ),
                            ).all()
                            if x.is_visible()
                        ]
                        previews = [
                            x for x in page.locator("pre,code").all() if x.is_visible()
                        ]
                        if links or previews:
                            same_document = True
                            break
                page.wait_for_timeout(25)
            assert not foreign, "LFS browser destination leaves application"
            if downloads:
                download = downloads[-1]
                c.local_resource_path(download.url)
                assert download.failure() is None, "LFS browser download failed"
                with open(download.path(), "rb") as f:
                    raw = f.read()
                return raw, False
            if same_document:
                c.local_resource_path(page.url)
                return b"", True
            assert docs, "LFS object control did not navigate or download"
            page.wait_for_load_state("domcontentloaded")
            c.local_resource_path(page.url)
            final = docs[-1]
            assert final.status == 200, "LFS browser destination is missing or denied"
            return (
                final.body(),
                "text/html" in final.headers.get("content-type", "").lower(),
            )
        finally:
            page.remove_listener("response", response)
            page.remove_listener("download", download_event)
            page.unroute("**/*", boundary)

    for oid, data in objects.items():
        page, current_status = ui.goto(path, actor)
        assert current_status == 200, "LFS object list unavailable after navigation"
        current = visible_objects()
        item = current[oid]
        try:
            control = item["control"]
            assert control.is_visible(), "visible LFS object control disappeared"
            raw, html = follow(control, (oid, data))
        finally:
            release(current)
        if html:
            assert lfs_visible_identity(ui.text(page), oid, objects), "LFS detail page identifies another object"
            links = [
                x
                for role in ("link", "button")
                for x in page.get_by_role(
                    role,
                    name=re.compile(
                        r"^(?:View Raw|Raw|Download(?: (?:File|Object))?)$", re.I
                    ),
                ).all()
                if x.is_visible()
            ]
            if links:
                raw, is_html = follow(links[0])
                assert not is_html, "LFS download control returned another HTML page"
            else:
                # Reference has no raw control on small text/empty previews.
                text = data.decode("utf-8")
                assert all(
                    ch in "\r\n\t" or ord(ch) >= 32 for ch in text
                ), "binary LFS detail lacks usable download"
                if text:
                    wanted = text.replace("\r\n", "\n").rstrip("\n")
                    previews = [
                        x.inner_text().replace("\r\n", "\n").rstrip("\n")
                        for x in page.locator("pre,code").all()
                        if x.is_visible()
                    ]
                    if previews:
                        assert (
                            wanted in previews
                        ), "visible LFS preview has wrong content"
                    else:
                        assert wanted in ui.text(
                            page
                        ), "LFS detail lacks visible object content"
                else:
                    assert all(
                        not x.inner_text().strip()
                        for x in page.locator("pre,code").all()
                        if x.is_visible()
                    ), "empty LFS object displays nonempty content"
                lp = path.rsplit("/settings/lfs", 1)[0] + ".git/info/lfs"
                rr, _ = c.request("GET", lp + "/objects/" + oid, actor)
                assert (
                    rr.status_code == 200
                ), "visible LFS detail has no repository object"
                raw = rr.content
        assert (
            raw == data
            and len(raw) == len(data)
            and hashlib.sha256(raw).hexdigest() == oid
        ), "LFS visible link returned wrong object bytes"
        ui.event(
            "lfs-object-navigation",
            oid=oid,
            size=len(data),
            sha256=hashlib.sha256(raw).hexdigest(),
            href=item["href"],
        )
    ui.goto(path, actor)
    return {
        "status": status,
        "objects": unordered(
            [
                {
                    "oid": oid,
                    "size": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
                for oid, data in objects.items()
            ]
        ),
    }


# The npm tarballs of the publish cases: a tar (mtime 0) of package/package.json, the sorted-key JSON of
# {"name": name, "version": version, "main": "index.js"}, and package/index.js, "module.exports = 42;\n", gzipped at
# level 9 with mtime 0 as CPython 3.12 wrote them for the frozen record (zlib's header with OS byte 3, where Python
# 3.10 and 3.13+ write 255). Frozen bytes: the oracle holds these tarballs and their digests.
NPM_TARBALLS = {
    ("pbp-npm", "1.0.0"): (
        "H4sIAAAAAAACA+3TQQrCMBCF4aw9Rchaa1prBcXDRBukatPQqgji3U2rIrhxo4L4f5sJj8AshufNcmNWduivM1o3lRNvpoMs"
        "TbsZPE+tJ6PHu83jOEsyIbX4gn2zM3VYL/7TSZWmcGoqVeFyewz3V32pnCltm/mFHzhfttHB1k1RdT/jSEdanQV+3633w/v1"
        "P7HjZf+T8XP/Q0b/v6Gs8v3WRvboq3rXyLlMk1mPWgAAAAAAAAAAAAAAAPyMCzu7g6MAKAAA"
    ),
    ("pbp-npm", "2.0.0-beta.1"): (
        "H4sIAAAAAAACA+3TzYrCMBSG4ay9ipC1pkmpDszgxUQNUp2moa0iiPdurD8LN25UEN9nc8JH4CwOX3TztVv6LJ6nXrV1EE9m"
        "kklR9DO5n8aa/Pbuc2sn9kdII95g03auSevFd9qrypVB/UpVhoXfpfuroVTBVf6UxVkchVidoq1v2rLuf+baaDOa+c5pqw4C"
        "H+zS++x6/VfseNR/k4/v+58y+v8OVb3Y/Hvtd7FuulZOZZH/DagFAAAAAAAAAAAAAADAxzgCLr1IywAoAAA="
    ),
    ("@pbp/tools", "1.2.3"): (
        "H4sIAAAAAAACA+3TSwrCMBSF4YxdRchY+raCIriVqEGqtgltFUHcu2lVBCdOVBD/b3LDIXAHl+P0cqvXJnTXGWwaW4k3i7w8"
        "y/rpPc8oGuePd5fHcZ7GQkbiC/ZNq2u/Xvynkyp1UamJVEW1Mkd/fzWUqtKl6bK5W7iwtXbXpwdTN4XtP8dBEqTqLPDjbr0P"
        "79f/xI6X/U9Gz/33Gf3/htKu9jsTmKOzddvImcyS6YBaAAAAAAAAAAAAAAAA/IwLCs5EdwAoAAA="
    ),
    ("Invalid Name", "1.0.0"): (
        "H4sIAAAAAAACA+3TsQrCMBSF4cw+RcgsNZHWQfEBXHyHYINUbVraKoL47qZVQbq4qFD8v+Umh0CGyyntZm+3blLeZ7SrCy8+"
        "TAezOO5m0J/avJy73JiZSYTU4geOdWOr8L34TxeV28yruVSZT9057F+NpfI2d2228id7yFK5bu8hP7mqzoruuYl0pNVVYNAe"
        "vZ88t/+NP971X0+Tfv9DRv9/IS/S48FF7lwWVVPLpYynixG1AAAAAAAAAAAAAAAAGIwb2E202gAoAAA="
    ),
    ("pbp-bad", "not-semver"): (
        "H4sIAAAAAAACA+3TvQrCMBSG4cxeRcjsT1uqg+LFRBukapPQtCKI926sCtLFRQXxfZYTPgJnOHxer3d6Yyb+Nsfb4Kx4sySa"
        "5Xk3o/5M0qd3l6fpLJ0KmYgvaEOj67he/KeTqnRp1Vyq0hbmGO+vhlJZXZlr5ld+tNLFNTqYOpSu+2ldMwqmiok6C/y0e+8n"
        "j+t/Yser/ifZtN//mNH/b6hc0e7N2By9q5sglzLPFgNqAQAAAAAAAAAAAAAA8DMuOJDbigAoAAA="
    ),
}
# gzip.compress(b"local OCI layer\n", mtime=0) as CPython 3.12 wrote it (see above): the oracle holds the layer, and
# the image manifest digest that the episode manifest names is derived from it.
OCI_LAYER = base64.b64decode("H4sIAAAAAAACA8vJT07MUfB39lTISaxMLeICAM2SIeMQAAAA")


def tgz(name, version):
    return base64.b64decode(NPM_TARBALLS[(name, version)])


def npm_payload(name, version):
    raw = tgz(name, version)
    filename = name.rsplit("/", 1)[-1] + "-" + version + ".tgz"
    return (
        {
            "_id": name,
            "name": name,
            "description": "Local npm package",
            "dist-tags": {"latest": version},
            "versions": {
                version: {
                    "name": name,
                    "version": version,
                    "description": "Local npm package",
                    "author": {"name": "Alice Example"},
                    "license": "MIT",
                    "keywords": ["local", "test"],
                    "dependencies": {"example-dependency": "^1.0.0"},
                    "dist": {
                        "shasum": hashlib.sha1(raw).hexdigest(),
                        "integrity": "sha512-"
                        + base64.b64encode(hashlib.sha512(raw).digest()).decode(),
                        "tarball": f"https://example.test/{filename}",
                    },
                }
            },
            "_attachments": {
                filename: {
                    "content_type": "application/octet-stream",
                    "data": base64.b64encode(raw).decode(),
                    "length": len(raw),
                }
            },
            "readme": "# Local package\n\nOffline package contents.",
        },
        raw,
        filename,
    )


def build(s):
    a = s.api
    # Six LFS object scenarios exercise authorization, binary integrity and deduplication.
    for private in (False, True):
        vis = "private" if private else "public"
        name = "pbp-lfs-" + vis
        rp = "repos/alice/" + name
        lp = "/alice/" + name + ".git/info/lfs"
        a(
            "lfs-fixture",
            vis,
            "repo",
            "POST",
            "user/repos",
            "alice",
            body={"name": name, "private": private, "auto_init": True},
            status=201,
        )
        a(
            "lfs-fixture",
            vis,
            "writer",
            "PUT",
            rp + "/collaborators/bob",
            "alice",
            body={"permission": "write"},
            status=204,
        )
        for kind, data in [
            ("empty", b""),
            ("text", "LFS object café\n".encode()),
            ("binary", bytes(range(256)) * 3),
        ]:
            sc = vis + "-" + kind
            oid = hashlib.sha256(data).hexdigest()
            obj = {"oid": oid, "size": len(data)}
            a(
                "lfs-objects",
                sc,
                "batch-missing",
                "POST",
                lp + "/objects/batch",
                "alice",
                body={
                    "operation": "download",
                    "transfers": ["basic"],
                    "objects": [obj],
                },
                headers=LFS_HEADERS,
                status=200,
            )
            check = lambda c, r, p, lp=lp, data=data: checked_lfs_actions(
                c, r, p, lp, data
            )
            a(
                "lfs-objects",
                sc,
                "batch-upload",
                "POST",
                lp + "/objects/batch",
                "alice",
                body={"operation": "upload", "transfers": ["basic"], "objects": [obj]},
                headers=LFS_HEADERS,
                status=200,
                save="lfs-batch-" + sc,
                check=check,
            )
            binary(
                s,
                "lfs-objects",
                sc,
                "upload",
                "PUT",
                lp + "/objects/" + oid + "/" + str(len(data)),
                "alice",
                data=data,
                headers={"Content-Type": "application/octet-stream"},
                status=200,
                json_response=True,
            )
            a(
                "lfs-objects",
                sc,
                "verify",
                "POST",
                lp + "/verify",
                "alice",
                body=obj,
                headers=LFS_HEADERS,
                status=200,
            )
            a(
                "lfs-objects",
                sc,
                "batch-existing",
                "POST",
                lp + "/objects/batch",
                "alice",
                body={"operation": "upload", "objects": [obj]},
                headers=LFS_HEADERS,
                status=200,
                check=check,
            )
            binary(
                s,
                "lfs-objects",
                sc,
                "download",
                "GET",
                lp + "/objects/" + oid,
                "bob",
                expected=data,
            )
            binary(
                s,
                "lfs-objects",
                sc,
                "download-public-policy",
                "GET",
                lp + "/objects/" + oid,
                None,
                status=401 if private else 200,
                expected=None if private else data,
            )
            a(
                "lfs-objects",
                sc,
                "outsider-policy",
                "POST",
                lp + "/objects/batch",
                "carol",
                body={"operation": "download", "objects": [obj]},
                headers=LFS_HEADERS,
                check=check,
            )
            if kind == "binary":
                binary(
                    s,
                    "lfs-objects",
                    sc,
                    "partial-download",
                    "GET",
                    lp + "/objects/" + oid,
                    "alice",
                    headers={"Range": "bytes=3-15"},
                    status=206,
                    expected=data[3:16],
                    range_spec=(3, 15, len(data)),
                )
                a(
                    "lfs-pointer",
                    vis,
                    "commit",
                    "POST",
                    rp + "/contents/large.bin",
                    "alice",
                    body={
                        "content": b64(
                            "version https://git-lfs.github.com/spec/v1\noid sha256:"
                            + oid
                            + "\nsize "
                            + str(len(data))
                            + "\n"
                        ),
                        "message": "Add LFS pointer",
                    },
                    status=201,
                )
        for actor in ("alice", "bob", "carol", None):
            data = b"permission transfer\n"
            a(
                "lfs-permission",
                vis + "-" + (actor or "anonymous"),
                "upload-batch",
                "POST",
                lp + "/objects/batch",
                actor,
                body={
                    "operation": "upload",
                    "objects": [
                        {"oid": hashlib.sha256(data).hexdigest(), "size": len(data)}
                    ],
                },
                headers=LFS_HEADERS,
                check=lambda c, r, p, lp=lp, data=data: checked_lfs_actions(
                    c, r, p, lp, data
                ),
            )
        for kind, path in [
            ("plain", "design.psd"),
            ("nested", "assets/image.png"),
            ("space", "art files/scene.blend"),
            ("unicode", "设计.bin"),
        ]:
            sc = vis + "-" + kind
            key = "lfs-lock-" + sc
            a(
                "lfs-locks",
                sc,
                "lock",
                "POST",
                lp + "/locks",
                "alice",
                body={"path": path},
                headers=LFS_HEADERS,
                status=201,
                save=key,
            )
            a(
                "lfs-locks",
                sc,
                "duplicate",
                "POST",
                lp + "/locks",
                "bob",
                body={"path": path},
                headers=LFS_HEADERS,
                status=409,
            )
            a(
                "lfs-locks",
                sc,
                "list",
                "GET",
                lp + "/locks",
                "bob",
                params={"path": path},
                headers=LFS_HEADERS,
                status=200,
            )
            a(
                "lfs-locks",
                sc,
                "verify-ownership",
                "POST",
                lp + "/locks/verify",
                "bob",
                body={},
                headers=LFS_HEADERS,
                status=200,
            )
            # Cross-owner non-forced unlock is excluded: pinned upstream returns 500.
            # Duplicate-lock rejection, verify ownership and owner unlock remain tested.
            if kind != "plain":
                a(
                    "lfs-locks",
                    sc,
                    "owner-unlock",
                    "POST",
                    pathref(lp + "/locks/{id}/unlock", id=Ref(key, "lock", "id")),
                    "alice",
                    body={},
                    headers=LFS_HEADERS,
                    status=200,
                )
                a(
                    "lfs-locks",
                    sc,
                    "gone",
                    "GET",
                    lp + "/locks",
                    "alice",
                    params={"path": path},
                    headers=LFS_HEADERS,
                    status=200,
                )
        for actor in ("alice", "bob", "carol", None):
            inventory = {
                hashlib.sha256(data).hexdigest(): data
                for data in (
                    b"",
                    "LFS object café\n".encode(),
                    bytes(range(256)) * 3,
                    b"permission transfer\n",
                )
            }
            add(
                s,
                "lfs-pages",
                vis + "-" + (actor or "anonymous"),
                "objects",
                lambda c, ui, path="/alice/" + name + "/settings/lfs", actor=actor, objects=inventory: lfs_browser_objects(
                    c, ui, path, actor, objects
                ),
            )
    lp = "/alice/pbp-lfs-public.git/info/lfs"
    for sc, body in [
        ("bad-operation", {"operation": "erase", "objects": []}),
        (
            "bad-oid",
            {"operation": "upload", "objects": [{"oid": "not-a-sha", "size": 1}]},
        ),
        (
            "negative-size",
            {"operation": "upload", "objects": [{"oid": "a" * 64, "size": -1}]},
        ),
        ("empty-list", {"operation": "download", "objects": []}),
    ]:
        a(
            "lfs-validation",
            sc,
            "batch",
            "POST",
            lp + "/objects/batch",
            "alice",
            body=body,
            headers=LFS_HEADERS,
        )
    a(
        "lfs-validation",
        "wrong-media",
        "batch",
        "POST",
        lp + "/objects/batch",
        "alice",
        body={"operation": "download", "objects": []},
        headers={"Accept": "text/plain"},
        status=415,
    )
    # Generic packages: multiple file types and version semantics under public user ownership.
    for version in ("1.0.0", "2.0.0-rc.1"):
        for kind, filename, data in [
            ("text", "notes.txt", b"package notes\n"),
            ("binary", "payload.bin", bytes(range(64))),
            ("spaces", "file with spaces.txt", "包文件 café".encode()),
        ]:
            sc = version + "-" + kind
            path = (
                "/api/packages/alice/generic/pbp-generic/"
                + version
                + "/"
                + urllib.parse.quote(filename, safe="")
            )
            binary(
                s, "package-generic", sc, "upload", "PUT", path, data=data, status=201
            )
            binary(
                s, "package-generic", sc, "download", "GET", path, None, expected=data
            )
            binary(
                s,
                "package-generic",
                sc,
                "duplicate",
                "PUT",
                path,
                data=data,
                status=409,
            )
        ep = "packages/alice/generic/pbp-generic/" + version
        for actor in ("alice", "bob", None):
            a(
                "package-metadata",
                version + "-" + (actor or "anonymous"),
                "version",
                "GET",
                ep,
                actor,
                status=200 if actor else 401,
            )
            a(
                "package-metadata",
                version + "-" + (actor or "anonymous"),
                "files",
                "GET",
                ep + "/files",
                actor,
                status=200 if actor else 401,
            )
        a("package-permission", version, "outsider-delete", "DELETE", ep, "bob")
    for actor in (None, "invalid", "bob"):
        a(
            "package-permission",
            actor or "anonymous",
            "outsider-upload",
            "PUT",
            "/api/packages/alice/generic/pbp-forbidden/1.0.0/file.txt",
            actor,
            data=b"not authorized",
        )
    for sc, owner, name, version, file in [
        ("bad-name", "alice", "bad name", "1.0.0", "file.txt"),
        ("bad-version", "alice", "pbp-bad", " version ", "file.txt"),
        ("bad-file", "alice", "pbp-bad", "1.0.0", " file.txt"),
        ("missing-owner", "pbp-missing", "pbp-bad", "1.0.0", "file.txt"),
    ]:
        path = (
            "/api/packages/"
            + owner
            + "/generic/"
            + urllib.parse.quote(name, safe="")
            + "/"
            + urllib.parse.quote(version, safe="")
            + "/"
            + urllib.parse.quote(file, safe="")
        )
        a("package-validation", sc, "upload", "PUT", path, "alice", data=b"invalid")
    # Standard npm publish bodies include real deterministic tarballs and integrity checks.
    for sc, name, version in [
        ("unscoped", "pbp-npm", "1.0.0"),
        ("prerelease", "pbp-npm", "2.0.0-beta.1"),
        ("scoped", "@pbp/tools", "1.2.3"),
    ]:
        payload, raw, filename = npm_payload(name, version)
        path = "/api/packages/alice/npm/" + name
        a("package-npm", sc, "publish", "PUT", path, "alice", body=payload, status=201)
        a(
            "package-npm",
            sc,
            "metadata",
            "GET",
            path,
            None,
            status=200,
            save="npm-" + sc,
            hint="npm",
        )
        binary(
            s,
            "package-npm",
            sc,
            "download",
            "GET",
            path + "/-/" + version + "/" + filename,
            None,
            expected=raw,
        )
        a(
            "package-npm",
            sc,
            "duplicate",
            "PUT",
            path,
            "alice",
            body=payload,
            status=409,
        )
        tags = "/api/packages/alice/npm/-/package/" + name + "/dist-tags"
        a("package-npm", sc, "tags", "GET", tags, "alice", status=200)
        a(
            "package-npm",
            sc,
            "tag-next",
            "PUT",
            tags + "/next",
            "alice",
            body=version,
            status=200,
        )
        a("package-npm", sc, "tag-list", "GET", tags, None, status=200)
        a(
            "package-npm",
            sc,
            "remove-tag",
            "DELETE",
            tags + "/next",
            "alice",
            status=200,
        )
    for text in ("pbp", "tools", "no-match-zz"):
        a(
            "package-npm-search",
            text,
            "query",
            "GET",
            "/api/packages/alice/npm/-/v1/search",
            None,
            params={"text": text, "size": 10},
            status=200,
            hint="npm-search",
        )
    for sc, body in [
        ("empty", {}),
        ("bad-name", npm_payload("Invalid Name", "1.0.0")[0]),
        ("bad-version", npm_payload("pbp-bad", "not-semver")[0]),
    ]:
        a(
            "package-npm-validation",
            sc,
            "publish",
            "PUT",
            "/api/packages/alice/npm/pbp-invalid",
            "alice",
            body=body,
        )
    # OCI registry: bearer authentication, chunked upload, immutable digests and manifests.
    a("package-container", "registry", "anonymous-probe", "GET", "/v2/", None)
    for actor in ("alice", "bob", None):

        def authenticate(c, actor=actor):
            r, p = c.request("GET", "/v2/token", actor)
            assert r.status_code == 200
            assert isinstance(p.get("token"), str) and p["token"], "registry token is missing"
            probe, _ = c.request(
                "GET", "/v2/", None, headers={"Authorization": "Bearer " + p["token"]}
            )
            assert probe.status_code == 200, "issued registry token is unusable"
            denied, _ = c.request(
                "GET", "/v2/", None, headers={"Authorization": "Bearer pbp-invalid-registry-token"}
            )
            assert denied.status_code == 401, "registry accepts an unissued bearer token"
            c.state["registry-token-" + (actor or "anonymous")] = p["token"]
            return {"status": 200, "usable_token": True}

        s.add("package-container-auth", actor or "anonymous", "token", authenticate)
    bearer = lambda c: {"Authorization": "Bearer " + c.state["registry-token-alice"]}
    repo = "/v2/alice/pbp-image"
    config = json.dumps(
        {
            "architecture": "amd64",
            "os": "linux",
            "rootfs": {"type": "layers", "diff_ids": []},
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    layer = OCI_LAYER
    for sc, data in [("config", config), ("layer", layer)]:
        digest = "sha256:" + hashlib.sha256(data).hexdigest()
        key = "oci-" + sc
        binary(
            s,
            "package-container-blob",
            sc,
            "begin",
            "POST",
            repo + "/blobs/uploads",
            None,
            headers=bearer,
            status=202,
            save=key,
            upload_offset=0,
            upload_repository=repo,
        )
        upload = lambda c, k=key: registry_upload_location(
            c, c.state[k]["headers"]["Location"]
        )
        split = max(1, len(data) // 2)
        binary(
            s,
            "package-container-blob",
            sc,
            "chunk",
            "PATCH",
            upload,
            None,
            data=data[:split],
            headers=lambda c, offset=split: {
                **bearer(c), "Content-Type": "application/octet-stream", "Content-Range": f"0-{offset-1}"
            },
            status=202,
            save=key,
            upload_offset=split,
            upload_repository=repo,
        )
        binary(
            s,
            "package-container-blob",
            sc,
            "progress",
            "GET",
            upload,
            None,
            headers=bearer,
            status=204,
            save=key,
            upload_offset=split,
            upload_repository=repo,
        )
        binary(
            s,
            "package-container-blob",
            sc,
            "finish",
            "PUT",
            lambda c, u=upload, d=digest: registry_finish_url(u(c), d),
            None,
            data=data[split:],
            headers=lambda c, start=split, end=len(data)-1: {
                **bearer(c), "Content-Type": "application/octet-stream", "Content-Range": f"{start}-{end}"
            },
            status=201,
        )
        binary(
            s,
            "package-container-blob",
            sc,
            "head",
            "HEAD",
            repo + "/blobs/" + digest,
            None,
            headers=bearer,
            status=200,
            representation_type="application/octet-stream",
            blob_content=data,
        )
        binary(
            s,
            "package-container-blob",
            sc,
            "download",
            "GET",
            repo + "/blobs/" + digest,
            None,
            headers=bearer,
            expected=data,
            blob_content=data,
        )
    manifest = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "config": {
            "mediaType": "application/vnd.oci.image.config.v1+json",
            "digest": "sha256:" + hashlib.sha256(config).hexdigest(),
            "size": len(config),
        },
        "layers": [
            {
                "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
                "digest": "sha256:" + hashlib.sha256(layer).hexdigest(),
                "size": len(layer),
            }
        ],
    }
    raw = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    binary(
        s,
        "package-container-manifest",
        "latest",
        "publish",
        "PUT",
        repo + "/manifests/latest",
        None,
        data=raw,
        headers=lambda c: {
            **bearer(c),
            "Content-Type": "application/vnd.oci.image.manifest.v1+json",
        },
        status=201,
    )
    for actor in ("alice", "bob", None):
        token = lambda c, x=actor: {
            "Authorization": "Bearer "
            + c.state["registry-token-" + (x or "anonymous")],
            "Accept": "application/vnd.oci.image.manifest.v1+json",
        }
        binary(
            s,
            "package-container-manifest",
            actor or "anonymous",
            "by-tag",
            "GET",
            repo + "/manifests/latest",
            None,
            headers=token,
            expected=raw,
        )
        binary(
            s,
            "package-container-manifest",
            actor or "anonymous",
            "by-digest",
            "GET",
            repo + "/manifests/" + digest,
            None,
            headers=token,
            expected=raw,
        )
        a(
            "package-container-manifest",
            actor or "anonymous",
            "tags",
            "GET",
            repo + "/tags/list",
            None,
            headers=token,
            status=200,
        )
    a(
        "package-container",
        "registry",
        "catalog",
        "GET",
        "/v2/_catalog",
        None,
        headers=bearer,
        status=200,
    )
    a(
        "package-container-manifest",
        "bob",
        "delete-denied",
        "DELETE",
        repo + "/manifests/" + digest,
        None,
        headers=lambda c: {"Authorization": "Bearer " + c.state["registry-token-bob"]},
    )
    # UI must expose package metadata/version selection and a real deletion episode.
    for actor in ("alice", "bob", None):
        for typ, name, version in [
            ("generic", "pbp-generic", "1.0.0"),
            ("npm", "pbp-npm", "1.0.0"),
            ("container", "pbp-image", "latest"),
        ]:
            root = "/alice/-/packages/" + typ + "/" + name + "/" + version
            view(
                s,
                "package-pages",
                typ + "-" + (actor or "anonymous"),
                "detail",
                root,
                actor,
                required=(name,),
                link_pattern=r"^/alice/-/packages/" + typ + "/" + name + r"/",
                ordered=False,
            )
            view(
                s,
                "package-pages",
                typ + "-" + (actor or "anonymous"),
                "settings",
                root + "/settings",
                actor,
            )
        for typ in ("generic", "npm", "container"):
            view(
                s,
                "package-directory",
                (actor or "anonymous") + "-" + typ,
                "filter",
                "/alice/-/packages?" + urllib.parse.urlencode({"type": typ}),
                actor,
                link_pattern=r"^/alice/-/packages/(?:generic|npm|container)/[^/]+/[^/]+$",
                ordered=False,
            )

    def delete_package(c, ui):
        endpoint = "packages/alice/generic/pbp-generic/2.0.0-rc.1"
        preserved = ui.corroborate("packages/alice/generic/pbp-generic/1.0.0/files")
        p, _ = ui.goto("/alice/-/packages/generic/pbp-generic/2.0.0-rc.1/settings")
        # Prefer the semantic version action. Upstream labels that action
        # "Delete Package" on a version-specific settings page.
        ui.delete(
            p, endpoint, "Delete Version", "Delete version", "Delete Package", "Delete package"
        )
        assert (
            ui.corroborate("packages/alice/generic/pbp-generic/1.0.0/files")
            == preserved
        ), "version deletion removed or changed another version"
        p.reload(wait_until="domcontentloaded")
        r, obj = c.request("GET", endpoint)
        assert r.status_code == 404
        return {
            "deleted_version": "2.0.0-rc.1",
            "api_status": 404,
            "other_version_preserved": True,
        }

    add(s, "package-delete", "generic-prerelease", "confirm", delete_package)
    a(
        "package-delete",
        "generic-file",
        "delete",
        "DELETE",
        "/api/packages/alice/generic/pbp-generic/1.0.0/file%20with%20spaces.txt",
        "alice",
        status=204,
    )
    a(
        "package-delete",
        "generic-file",
        "remaining",
        "GET",
        "packages/alice/generic/pbp-generic/1.0.0/files",
        "alice",
        status=200,
    )
    a(
        "package-delete",
        "npm-prerelease",
        "delete",
        "DELETE",
        "packages/alice/npm/pbp-npm/2.0.0-beta.1",
        "alice",
        status=204,
    )
    a(
        "package-delete",
        "npm-prerelease",
        "gone",
        "GET",
        "packages/alice/npm/pbp-npm/2.0.0-beta.1",
        "alice",
        status=404,
    )
    for typ in ("generic", "npm", "container"):
        a(
            "package-directory",
            typ,
            "list",
            "GET",
            "packages/alice",
            "alice",
            params={"type": typ},
            status=200,
            hint="package-list",
        )
