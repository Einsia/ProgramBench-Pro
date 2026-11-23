"""Program-check vocabulary and public access to one candidate through the black-box runtime.

One operation with all its assertions is one CASE. Every request reaches the
candidate through the runtime's api operation (the channel the model also has on
the reference); Git clients reach it through a local relay that forwards each
HTTP request through that same operation. Nothing here reads candidate files,
databases or processes.
"""

from __future__ import annotations
import base64, dataclasses, datetime, gzip, hashlib, html, json, math, pathlib, re, shutil, tempfile, threading, time, urllib.parse, zlib
from collections import Counter
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import requests

from evaluation.broker import BrokerError

CREDS = {
    "alice": "Alice-Local-2026!",
    "bob": "Bob-Local-2026!",
    "carol": "Carol-Local-2026!",
}
# The product origin as the runtime configures it (PORT 3000 on loopback, for the reference and every candidate).
ORIGIN = "http://127.0.0.1:3000"
# Headers the runtime's api operation forwards; Content-Type travels as content_type.
API_HEADERS = {"accept", "authorization", "if-match", "if-none-match", "if-modified-since", "if-unmodified-since",
               "range", "content-range", "x-lfs-content-length", "x-lfs-content-hash", "git-protocol"}
# Connection-level headers that the runtime's HTTP client sets itself.
TRANSPORT_HEADERS = {"content-length", "host", "connection", "user-agent", "accept-encoding", "transfer-encoding",
                     "expect", "pragma", "cache-control", "accept-language", "keep-alive", "te"}


class MissingDependency(AssertionError):
    pass


class State(dict):
    def __missing__(self, key):
        raise MissingDependency(f"missing successful prerequisite {key}")


@dataclasses.dataclass
class Case:
    id: str
    family: str
    scenario: str
    channel: str
    description: str
    action: object


class Ref:
    def __init__(self, key, *path):
        self.key, self.path = key, path

    def get(self, ctx):
        if self.key not in ctx.state:
            raise MissingDependency(f"missing result {self.key}")
        v = ctx.state[self.key]
        try:
            for part in self.path:
                v = v[part]
        except (KeyError, IndexError, TypeError) as e:
            raise MissingDependency(f"prerequisite {self.key} lacks {self.path}") from e
        return v


def resolve(x, ctx):
    if isinstance(x, Ref):
        return x.get(ctx)
    if callable(x):
        return x(ctx)
    if isinstance(x, dict):
        return {k: resolve(v, ctx) for k, v in x.items()}
    if isinstance(x, (tuple, list)):
        return [resolve(v, ctx) for v in x]
    return x


def b64(text):
    return base64.b64encode(text.encode()).decode()


def blob_sha(data):
    """Git blob identity of known file bytes (what a contents update must name as the file's current sha)."""
    data = data.encode() if isinstance(data, str) else data
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def subset(got, want):
    for k, v in want.items():
        assert k in got, f"missing {k}"
        assert got[k] == v, f"{k}: {got[k]!r} != {v!r}"


def pathref(template, **values):
    return lambda c: template.format(
        **{
            k: urllib.parse.quote(str(resolve(v, c)), safe="")
            for k, v in values.items()
        }
    )


def application_origin_matches(base, target):
    """Same protocol/port and this host, including explicit loopback aliases."""
    try:
        origin = urllib.parse.urlsplit(base)
        candidate = urllib.parse.urlsplit(target)
        aliases = {"127.0.0.1", "localhost", "0.0.0.0"}
        return (
            origin.scheme in ("http", "https")
            and candidate.scheme == origin.scheme
            and candidate.username is None
            and candidate.password is None
            and (candidate.port or (443 if candidate.scheme == "https" else 80))
            == (origin.port or (443 if origin.scheme == "https" else 80))
            and (candidate.hostname == origin.hostname or
                 candidate.hostname in aliases and origin.hostname in aliases)
        )
    except ValueError:
        return False


def canonical_uri(value):
    """Canonicalize octets within path segments and query components.

    Split before decoding. A percent-encoded slash remains inside its original
    segment, and a percent-encoded question mark cannot become a query delimiter.
    Ordinary text and source/file payloads are not interpreted as URIs.
    """
    if not (value.startswith("/") or re.match(r"^https?://", value)) or "\n" in value:
        return value
    parts = urllib.parse.urlsplit(value)
    path = "/".join(
        urllib.parse.quote_from_bytes(
            urllib.parse.unquote_to_bytes(segment), safe="!$&'()*+,;=:@-._~"
        )
        for segment in parts.path.split("/")
    )

    # Decode query components once, preserving order, repetition, delimiters and
    # the distinction between literal '+' (space) and '%2B' (plus). Do not let
    # encoded '&'/'=' become query structure or move '/' into the URI path.
    def component(text):
        return urllib.parse.quote_from_bytes(
            urllib.parse.unquote_to_bytes(text.replace("+", " ")), safe="-._~"
        )

    query = "&".join(
        "=".join(component(x) for x in pair.split("=", 1))
        for pair in parts.query.split("&")
    )
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, path, query, parts.fragment)
    )


def unordered(values):
    """Private observation marker: membership with multiplicity, never order."""
    return {"@unordered": list(values)}


def numeric_identity(value, nullable=False):
    if nullable and value is None:
        return value
    assert type(value) in (int, float), "numeric identity must be a JSON number"
    assert (
        -(2**63) <= value < 2**63 and math.isfinite(value) and int(value) == value
    ), "numeric identity must be an int64"
    return int(value)


def json_number(token):
    """Preserve integral int64 JSON values in subsequent API and browser paths.

    Parse the decimal token before binary floating-point rounding, including
    legal large int64 values. Strings/booleans are untouched, fractional numbers
    keep ordinary numeric semantics, and response bytes are never rewritten.
    """
    value = Decimal(token)
    if (
        value.is_finite()
        and -(2**63) <= value < 2**63
        and value == value.to_integral_value()
    ):
        return int(value)
    return float(token)


def git_blob_content(payload):
    """Content-addressed blob IDs are derived bytes, not generated row IDs.

    Called only for Git contents/blob API observations. Commit IDs can vary with
    generated commit metadata; their existing graph normalization is unchanged.
    """
    if isinstance(payload, list):
        for item in payload:
            git_blob_content(item)
    elif isinstance(payload, dict):
        if payload.get("encoding") == "base64" and {"sha", "size", "content"} <= payload.keys():
            assert isinstance(payload["content"], str), "Git blob content must be base64 text"
            content = base64.b64decode("".join(payload["content"].split()), validate=True)
            assert numeric_identity(payload["size"]) == len(content), "Git blob size differs from its decoded bytes"
            expected = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
            assert payload["sha"] == expected, "Git blob identity is not the hash of its actual content"
        for item in payload.values():
            if isinstance(item, (dict, list)):
                git_blob_content(item)


def lfs_batch_payload(payload):
    """Protocol defaults and benign diagnostics, retaining all object actions."""
    payload = {"transfer": "basic", **payload}
    objects = []
    # The pinned Go server serializes the empty response slice as null. This
    # represents no objects; a nonempty requested/result collection stays exact.
    entries = [] if payload["objects"] is None else payload["objects"]
    assert isinstance(
        entries, list
    ), "LFS objects must be an array or the legacy empty null"
    for obj in entries:
        obj = dict(obj)
        if "authenticated" in obj:
            assert (
                type(obj["authenticated"]) is bool
            ), "LFS authenticated must be boolean"
            if not obj.get("actions"):
                obj.pop("authenticated")
        if isinstance(obj.get("error"), dict):
            error = obj["error"]
            assert (
                type(error.get("code")) is int and 400 <= error["code"] < 600
            ), "invalid LFS object error status"
            assert (
                isinstance(error.get("message"), str) and error["message"]
            ), "missing LFS object error diagnostic"
            obj["error"] = {**error, "message": "@diagnostic"}
        if isinstance(obj.get("actions"), dict):
            actions = {}
            for name, action in obj["actions"].items():
                action = dict(action)
                headers = {}
                for key, value in (action.get("header") or {}).items():
                    assert isinstance(key, str) and isinstance(
                        value, str
                    ), "invalid LFS action HTTP header"
                    lower = key.lower()
                    if lower in headers:
                        if lower == "accept":
                            headers[lower] += "," + value
                        else:
                            assert (
                                headers[lower] == value
                            ), "conflicting LFS action HTTP header"
                    else:
                        headers[lower] = value
                # RFC9110: no Accept field imposes no media-type restriction.
                # Other missing headers (notably Authorization) are not defaulted.
                # Basic download is a raw object; upload/verify return the
                # pinned product's LFS JSON status. Other negotiated adapters
                # and unknown actions have no assumed media/default semantics.
                response_type = (
                    {
                        "download": "application/octet-stream",
                        "upload": "application/vnd.git-lfs+json",
                        "verify": "application/vnd.git-lfs+json",
                    }.get(name)
                    if payload["transfer"] == "basic"
                    else None
                )
                if response_type is not None:
                    headers.setdefault("accept", "*/*")
                for key, value in list(headers.items()):
                    if key.lower() != "accept" or response_type is None:
                        continue
                    ranges = []
                    for part in value.split(","):
                        media, *params = part.strip().lower().split(";")
                        quality = 1.0
                        for param in params:
                            assert param.strip().startswith(
                                "q="
                            ), "unknown LFS Accept parameter"
                            quality = float(param.strip()[2:])
                            assert 0 <= quality <= 1, "invalid LFS Accept quality"
                        ranges.append((media.strip(), quality))
                    specificity = {"*/*": 0, "application/*": 1, response_type: 2}
                    matches = [
                        (specificity[media], q)
                        for media, q in ranges
                        if media in specificity
                    ]
                    rank = max((r for r, q in matches), default=-1)
                    quality = max((q for r, q in matches if r == rank), default=0)
                    assert quality > 0, (
                        "LFS "
                        + name
                        + " action does not accept its "
                        + response_type
                        + " response"
                    )
                    headers[key] = response_type
                action["header"] = headers
                actions[name] = action
            obj["actions"] = actions
        objects.append(obj)
    return {**payload, "objects": objects}


def generated_commit_metadata(value):
    """Only optional CommitMeta.created, never lifecycle or caller-specified dates.

    Gitea's FileCommitResponse leaves this field at Go's zero value; Git commit
    conversion also emits zero metadata on parent/tree references. The schema
    makes it optional and the public task permits generated timestamps to vary.
    SHA, URL, parent order, author/committer dates and all other fields survive.
    """
    if "created" in value:
        stamp = value["created"]
        if stamp is not None:
            assert isinstance(
                stamp, str
            ), "CommitMeta.created must be a timestamp or null"
            parsed = datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            assert parsed.tzinfo is not None, "CommitMeta.created lacks a timezone"
    return {k: v for k, v in value.items() if k != "created"}


def repository_time_page(page, collection, field, descending, number, limit, norm):
    """Check a real chronological page against this run's complete collection.

    All record fields remain compared, including those on the observed page.
    Only selection/order among timestamps which vary with this run's clock is
    replaced by independent rank, identity, and pagination assertions.
    """
    by_name = {x["full_name"]: x for x in collection}
    assert len(by_name) == len(
        collection
    ), "duplicate repository in complete collection"
    names = [x["full_name"] for x in page]
    assert len(names) == len(set(names)), "duplicate repository on page"
    assert all(
        name in by_name for name in names
    ), "page contains an unfiltered repository"
    stamp = lambda x: datetime.datetime.fromisoformat(x[field].replace("Z", "+00:00"))
    for item in page:
        whole = by_name[item["full_name"]]
        assert stamp(item) == stamp(
            whole
        ), "repository sort key disagrees across queries"
        assert norm.clean(item) == norm.clean(
            whole
        ), "repository page fields disagree with complete record"
    offset = (number - 1) * limit
    ranks = sorted((stamp(x) for x in collection), reverse=descending)[
        offset : offset + limit
    ]
    assert [
        stamp(x) for x in page
    ] == ranks, "repository page violates chronological ranks or page size"
    return {
        "data": sorted(collection, key=lambda x: x["full_name"]),
        "page_observation": {
            "page": number,
            "limit": limit,
            "returned_count": len(page),
            "chronological_order": True,
        },
    }


class Normalize:
    # These are supplied/displayed business values, never opaque identities.
    # Typed wrappers keep alias-looking user text out of the identity graph.
    LITERAL_FIELDS = {
        "title", "body", "description", "full_name", "name", "login",
        "username", "location", "website", "email", "filename", "tag_name",
        "target_url", "path",
    }
    # Wall-clock observations only; due dates, time estimates, counters, state retained.
    CLOCK = {
        "created_at",
        "updated_at",
        "created",
        "updated",
        "last_login",
        "merged_at",
        "closed_at",
        "published_at",
        "last_update",
        "timestamp",
        "committed_date",
        "authored_date",
        "locked_at",
        "archived_at",
        "submitted_at",
        # Never-mirrored repositories carry the zero instant; its spelling (Z or +00:00) is not behaviour.
        "mirror_updated",
    }

    def __init__(self, base):
        self.base = base
        self.ids = {}
        self.opaque = {}
        self.next = Counter()
        self.tree_targets = {}

    def tree_identity(self, scope, value):
        assert isinstance(value, str) and re.fullmatch(
            "[0-9a-f]{40}", value
        ), "tree reference must be a Git object identifier"
        return self.identity(
            "tree:" + scope, self.tree_targets.get((scope, value), value)
        )

    def identity(self, kind, value):
        if type(value) in (int, float):
            value = numeric_identity(value)
        if value in (None, 0, ""):
            return value
        k = (kind, str(value))
        if k not in self.ids:
            self.next[kind] += 1
            self.ids[k] = f'@{urllib.parse.quote(kind,safe="-._")}:{self.next[kind]}'
        return self.ids[k]

    def kind(self, obj, hint):
        if "locked_at" in obj and "path" in obj:
            return "lfs-lock"
        if "version" in obj and "type" in obj and "name" in obj:
            return "package-version"
        if "sha256" in obj and "sha512" in obj and "name" in obj:
            return "package-file"
        if "login" in obj or "username" in obj and "avatar_url" in obj:
            return "user"
        if "full_name" in obj and ("owner" in obj or "clone_url" in obj):
            return "repo"
        # PR primary keys use their own table; their repository-local number is
        # deliberately shared with Issue and with both /issues and /pulls URLs.
        if {"head", "base", "number"} <= obj.keys():
            return "pull"
        if ("index" in obj or "number" in obj) and (
            "title" in obj or "pull_request" in obj
        ):
            return "issue"
        if "tag_name" in obj and "tarball_url" in obj:
            return "release"
        if "color" in obj and "name" in obj:
            return "label"
        if "due_on" in obj or "open_issues" in obj and "title" in obj:
            return "milestone"
        if "permission" in obj and "units" in obj and "name" in obj:
            return "team"
        # Reviews and statuses can also have body/user/html_url. Their primary
        # IDs belong to independent tables; review html_url anchors are comments.
        if "status" in obj and "context" in obj and "target_url" in obj:
            return "status"
        if "state" in obj and "commit_id" in obj and "context" in obj:
            return "status"
        if "state" in obj and "commit_id" in obj and "body" in obj:
            return "review"
        if "body" in obj and "user" in obj and "html_url" in obj:
            return "comment"
        if "subject" in obj and "unread" in obj:
            return "notification"
        if "sha1" in obj and "scopes" in obj:
            return "token"
        if "browser_download_url" in obj and "download_count" in obj:
            return "asset"
        return hint

    @staticmethod
    def repository_scope(url, default=""):
        path = urllib.parse.urlsplit(url).path
        m = re.match(r"^/?(?:api/v1/)?repos/([^/]+)/([^/]+)(?:/|$)", path)
        if not m:
            m = re.match(
                r"^/([^/]+)/([^/]+)/(?:commit|commits|git|src|raw|wiki|pulls|issues|releases|branches|tags)(?:/|$)",
                path,
            )
        if not m:
            return default
        name = urllib.parse.unquote(m[1] + "/" + m[2])
        if "/wiki/" in path or path.endswith("/wiki"):
            name += ".wiki"
        return name

    def text(self, s, scope="", uri=False):
        if uri:
            s = canonical_uri(s)
        scope = self.repository_scope(s, scope)
        # Only this run's origin (including same-port loopback hostname aliases)
        # can become @origin. A wrong port or a prefix lookalike is a broken link.
        def local_origin(match):
            return "@origin" if application_origin_matches(self.base, match[0]) else match[0]
        s = re.sub(
            r"https?://[^/?#\s]+", local_origin, s
        )
        s = s.replace("\r\n", "\n")
        # Repository-local issue numbers, object IDs in URLs, and UUIDs retain bijective relationships.
        s = re.sub(
            r"(/(?:api/v1/repos/)?([^/]+)/([^/]+)/(?:issues|pulls)/)(\d+)",
            lambda m: m[1]
            + str(self.identity("issue-number:" + m[2] + "/" + m[3], m[4])),
            s,
        )
        for segment, kind in [
            ("comments", "comment"),
            ("reviews", "review"),
            ("releases", "release"),
            ("milestones", "milestone"),
            ("labels", "label"),
            ("threads", "notification"),
            ("teams", "team"),
        ]:
            s = re.sub(
                r"(/" + segment + r"/)(\d+)",
                lambda m: m[1] + str(self.identity(kind, m[2])),
                s,
            )
        s = re.sub(
            r"(#issuecomment-)(\d+)",
            lambda m: m[1] + str(self.identity("comment", m[2])),
            s,
        )
        s = re.sub(
            r"(/blobs/uploads/)([^/?]+)",
            lambda m: m[1] + str(self.identity("registry-upload", m[2])),
            s,
        )
        s = re.sub(
            r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
            lambda m: self.identity("uuid", m[0]),
            s,
        )
        s = re.sub(
            r"(/git/trees/)([0-9a-f]{40})\b",
            lambda m: m[1] + self.tree_identity(scope, m[2]),
            s,
        )
        # Content-addressed Git commit/tree/blob IDs are opaque but consistent across calls.
        s = re.sub(
            r"\b[0-9a-f]{40}\b", lambda m: self.identity("oid:" + scope, m[0]), s
        )
        s = re.sub(r"/avatars/[a-f0-9]+", "/avatars/@avatar", s)
        return s

    def clean(self, v, hint="object", key="", scope=""):
        if key in self.LITERAL_FIELDS or key in {"content", "content_base64"} and isinstance(v, str):
            if v is None:
                return None
            assert isinstance(v, str), "business text field must be a string or null: " + key
            return {"@literal": v.replace("\r\n", "\n")}
        if isinstance(v, dict):
            assert "@literal" not in v, "response cannot supply a private literal observation marker"
            if v.get("type") == "dir":
                # Pinned ContentsResponse builds /git/blobs URLs for directories
                # too. Context corroborates their tree target before cleaning.
                # Canonicalize only this known directory link representation.
                def directory_url(value):
                    return (
                        value.replace("/git/blobs/", "/git/trees/")
                        if isinstance(value, str)
                        else value
                    )

                v = {**v}
                if "git_url" in v:
                    v["git_url"] = directory_url(v["git_url"])
                if isinstance(v.get("_links"), dict) and "git" in v["_links"]:
                    v["_links"] = {
                        **v["_links"],
                        "git": directory_url(v["_links"]["git"]),
                    }
            # File mutation responses may repeat the same verification at the
            # commit level. A contradictory duplicate must fail, not disappear.
            if (
                isinstance(v.get("commit"), dict)
                and "verification" in v
                and ("content" in v or "files" in v)
            ):
                commit = v["commit"]
                if "verification" in commit:
                    assert (
                        commit["verification"] == v["verification"]
                    ), "file commit verification contradicts response verification"
                    commit = {k: x for k, x in commit.items() if k != "verification"}
                v = {**v, "commit": generated_commit_metadata(commit)}
            # CommitMeta references have only identity, URL and generated time.
            if (
                {"sha", "url"} <= v.keys()
                and v.keys() <= {"sha", "url", "created"}
                and isinstance(v["url"], str)
                and re.search(r"/git/(?:commits|trees)/", v["url"])
            ):
                v = generated_commit_metadata(v)
            # PRs are issue resources too. Empty issue-only metadata is an
            # admissible extension; nonempty authors/assets/refs remain scored.
            if {"head", "base", "mergeable", "number"} <= v.keys():
                v = {
                    "assets": [],
                    "original_author": "",
                    "original_author_id": 0,
                    "ref": "",
                    **v,
                }
            if {
                "merged",
                "merged_at",
                "html_url",
                "draft",
            } <= v.keys() and key == "pull_request":
                # Optional useful links may extend the issue's PR projection.
                # Only the correct same-resource endpoints are admissible.
                for field, suffix in [("patch_url", ".patch"), ("diff_url", ".diff")]:
                    expected = v["html_url"] + suffix
                    if field in v:
                        assert isinstance(v[field], str) and self.text(
                            v[field], scope, uri=True
                        ) == self.text(
                            expected, scope, uri=True
                        ), "PR extension link identifies another resource"
                    v = {**v, field: expected}
            if (
                "full_name" in v
                and v.get("has_issues") is False
                and "internal_tracker" in v
            ):
                tracker = v["internal_tracker"]
                if tracker is not None:
                    assert isinstance(tracker, dict) and set(tracker) == {
                        "enable_time_tracker",
                        "allow_only_contributors_to_track_time",
                        "enable_issue_dependencies",
                    }, "unknown disabled tracker fields"
                    assert all(
                        type(x) is bool for x in tracker.values()
                    ), "disabled tracker flags must be booleans"
                # These options have no effective unit while has_issues=false.
                # Enabling the unit and its actual flags remain strictly tested.
                v = {k: x for k, x in v.items() if k != "internal_tracker"}
            for field in ("url", "html_url", "issue_url", "pull_request_url"):
                if isinstance(v.get(field), str):
                    scope = self.repository_scope(v[field], scope)
            if hint == "npm-search" and isinstance(v.get("objects"), list):
                # Equal-score search results have no specified secondary ordering.
                v = {
                    **v,
                    "objects": sorted(
                        v["objects"],
                        key=lambda x: (
                            x.get("package", {}).get("scope", ""),
                            x.get("package", {}).get("name", ""),
                            x.get("package", {}).get("version", ""),
                        ),
                    ),
                }
            kind = self.kind(v, hint)
            out = {}
            for k, val in sorted(v.items()):
                if (
                    k == "time"
                    and isinstance(val, dict)
                    and hint in ("npm", "npm-search")
                ):
                    out[k] = {
                        version: ("@time" if stamp else stamp)
                        for version, stamp in val.items()
                    }
                elif k == "date" and hint in ("npm", "npm-search"):
                    out[k] = "@time" if val else val
                elif k in {"due_on", "due_date"} and val is not None:
                    # Due dates are business data: compare the same instant, do
                    # not erase it like generated wall-clock timestamps.
                    assert isinstance(val, str), "due date must be a timestamp or null"
                    stamp = datetime.datetime.fromisoformat(val.replace("Z", "+00:00"))
                    assert stamp.tzinfo is not None, "due date lacks a timezone"
                    out[k] = stamp.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
                elif k == "color" and isinstance(val, str) and re.fullmatch(r"[0-9a-fA-F]{6}", val):
                    out[k] = val.lower()
                elif k in self.CLOCK:
                    # Preserve presence/nullness of lifecycle times, never their wall clock.
                    if val is not None:
                        assert isinstance(val, str), (
                            "timestamp must be a string or null: " + k
                        )
                        stamp = datetime.datetime.fromisoformat(
                            val.replace("Z", "+00:00")
                        )
                        assert stamp.tzinfo is not None, (
                            "timestamp lacks a timezone: " + k
                        )
                    out[k] = (
                        None
                        if val is None
                        else ("@unset" if str(val).startswith("0001-") else "@time")
                    )
                elif k in ("number", "index") and kind in ("issue", "pull"):
                    val = numeric_identity(val)
                    url = v.get("html_url", v.get("url", ""))
                    match = re.search(
                        r"/(?:api/v1/repos/)?([^/]+)/([^/]+)/(?:issues|pulls)/", url
                    )
                    out[k] = (
                        self.identity("issue-number:" + match[1] + "/" + match[2], val)
                        if match
                        else val
                    )
                elif k == "id":
                    oid = isinstance(val, str) and re.fullmatch("[0-9a-f]{40}", val)
                    if kind == "lfs-lock":
                        assert isinstance(val, str) and bool(
                            val
                        ), "LFS lock identity must be a nonempty string"
                    elif oid:
                        # Git objects use string IDs, but a user/repo/etc cannot
                        # masquerade as a Git object just by choosing 40 hex chars.
                        assert kind in (
                            "object",
                            "commit",
                            "author",
                            "committer",
                            "commiter",
                        ), "numeric resource identity cannot be a Git hash"
                    else:
                        val = numeric_identity(val)
                    out[k] = self.identity("oid:" + scope if oid else kind, val)
                elif k == "sha" and (
                    v.get("type") in ("tree", "dir")
                    or isinstance(v.get("tree"), list)
                    or "/git/trees/" in str(v.get("url", ""))
                ):
                    out[k] = self.tree_identity(scope, val)
                elif k == "shasum" or k == "sha1" and kind == "package-file":
                    out[k] = (
                        val  # Package integrity is content-derived, not opaque Git identity.
                    )
                elif k == "token_last_eight" and kind == "token":
                    assert (
                        isinstance(val, str)
                        and isinstance(v.get("sha1"), str)
                        and v["sha1"].endswith(val)
                    ), "token suffix must match the issued token"
                    out[k] = "@token-suffix" if val else val
                elif k == "units" and kind == "team":
                    out[k] = sorted(val)
                elif k.endswith("_id"):
                    which = {
                        "repo_id": "repo",
                        "repository_id": "repo",
                        "user_id": "user",
                        "owner_id": "user",
                        "milestone_id": "milestone",
                        "issue_id": "issue",
                        "comment_id": "comment",
                        "review_id": "review",
                        "pull_request_review_id": "review",
                        "team_id": "team",
                        "release_id": "release",
                        "pull_request_id": "pull",
                        "original_author_id": "user",
                    }.get(k)
                    out[k] = (
                        self.identity(which, numeric_identity(val, nullable=True))
                        if which
                        else self.clean(val, kind, k, scope)
                    )
                elif k in ("sha1", "token") and hint == "token":
                    out[k] = "@secret" if val else val
                elif k in ("avatar_url",):
                    out[k] = self.text(val, scope, uri=True) if val else val
                elif k == "ssh_url" and kind == "repo" and isinstance(val, str):
                    # SSH is explicitly unassessed. RUN_USER is the deployment's
                    # Unix account, not a public fixture; host/repository survive.
                    out[k] = re.sub(
                        r"^(?:[^/@:\s]+)@([^/:]+):", r"@ssh-account@\1:", val
                    )
                elif k in (
                    "url",
                    "html_url",
                    "issue_url",
                    "pull_request_url",
                ) and isinstance(val, str):
                    out[k] = self.text(val, scope, uri=True)
                    # IDs embedded in URLs refer to the same returned resource.
                    for seg, t in [
                        ("comments", "comment"),
                        ("reviews", "review"),
                        ("releases", "release"),
                        ("milestones", "milestone"),
                        ("labels", "label"),
                        ("threads", "notification"),
                        ("teams", "team"),
                    ]:
                        out[k] = re.sub(
                            r"(/" + seg + r"/)(\d+)",
                            lambda m: m[1] + str(self.identity(t, m[2])),
                            out[k],
                        )
                    out[k] = re.sub(
                        r"(#issuecomment-)(\d+)",
                        lambda m: m[1] + str(self.identity("comment", m[2])),
                        out[k],
                    )
                elif k == "date" and hint in (
                    "commit",
                    "committer",
                    "commiter",
                    "author",
                ):
                    out[k] = "@time" if val else val
                elif k == "language" and kind == "repo":
                    # The primary language comes from an asynchronous statistics pass; its value depends on timing,
                    # not on the request. Only its type is part of the contract.
                    assert isinstance(val, str), "repository language must be a string"
                    out[k] = "@language"
                elif k == "size" and kind == "repo":
                    assert (
                        numeric_identity(val) >= 0
                    ), "repository storage size must be a nonnegative JSON integer"
                    out[k] = "@nonnegative"
                else:
                    out[k] = self.clean(
                        val,
                        (
                            k
                            if k in ("author", "committer", "commiter", "commit")
                            else kind
                        ),
                        k,
                        scope,
                    )
            return out
        if isinstance(v, list):
            if hint == "package-list":
                v = sorted(
                    v,
                    key=lambda x: (
                        x.get("type", ""),
                        x.get("name", ""),
                        x.get("version", ""),
                    ),
                )
            if hint == "branch-list":
                # API order is commit_time DESC, name ASC. Wall-clock resolution
                # can change whether successive commits tie across fresh runs.
                ranks = [
                    (
                        -datetime.datetime.fromisoformat(
                            x["commit"]["timestamp"].replace("Z", "+00:00")
                        ).timestamp(),
                        x["name"],
                    )
                    for x in v
                ]
                assert ranks == sorted(
                    ranks
                ), "branch list violates commit-time/name ordering"
                assert len({x["name"] for x in v}) == len(
                    v
                ), "duplicate branch identity"
                v = sorted(v, key=lambda x: x["name"])
            return [self.clean(x, hint, key, scope) for x in v]
        if isinstance(v, str):
            return self.text(
                v,
                scope,
                uri=key.endswith("_url")
                or key in ("url", "self", "html", "git", "link", "website"),
            )
        return v


class AliasGraph:
    """Compare opaque identities by a persistent typed bijection, not counters.

    Counters label observations, not product behavior. Missing an unrelated
    earlier entity must not change a later correct entity's score. Bindings are
    transactional per CASE: an otherwise failed response cannot poison future
    unrelated comparisons. Every successful relationship stays constrained.

    Response objects may carry fields the reference does not have; every
    reference field must be present and equal. Data-keyed maps
    (languages, npm versions and tags, team unit maps, LFS actions and headers)
    and empty objects stay exact: an extra entry there is different data.
    """

    TOKEN = re.compile(r"@[A-Za-z][A-Za-z0-9_.%+-]*:[0-9]+")
    FIELD = re.compile(r"^[a-z_][a-z0-9_]*$")
    MAPS = {"units_map", "versions", "dependencies", "devDependencies", "peerDependencies", "optionalDependencies",
            "dist-tags", "time", "actions", "header", "headers"}

    def __init__(self):
        self.forward = {}
        self.reverse = {}

    def compare(self, actual, expected):
        forward = dict(self.forward)
        reverse = dict(self.reverse)

        def walk(a, e, path, parent=None):
            # JSON numeric values retain the pre-graph equality semantics (1
            # equals 1.0); booleans are a distinct type, never numeric aliases.
            if type(a) in (int, float) and type(e) in (int, float):
                assert a == e, path + ": different numeric value"
                return
            assert type(a) is type(e), path + ": different value type"
            if isinstance(e, dict):
                markers = ({"@literal"}, {"@unordered"})
                if e.keys() in markers or a.keys() in markers or not e or parent in self.MAPS \
                        or not all(self.FIELD.match(k) for k in e):
                    assert a.keys() == e.keys(), path + ": different fields"
                else:
                    missing = sorted(set(e) - set(a))
                    assert not missing, path + ": missing fields " + ", ".join(missing[:5])
                if e.keys() == {"@literal"}:
                    assert isinstance(a["@literal"], str) and a["@literal"] == e["@literal"], (
                        path + ": different business text"
                    )
                    return
                if e.keys() == {"@unordered"}:
                    av, ev = a["@unordered"], e["@unordered"]
                    assert (
                        isinstance(av, list)
                        and isinstance(ev, list)
                        and len(av) == len(ev)
                    ), (path + ": different collection length")

                    # Match constraints, not serialized alias counters. Compare
                    # already-bound identities first; each trial is transactional.
                    # Business labels in collection records resolve unbound IDs.
                    def bindings(x):
                        return sum(
                            m[0] in forward for m in self.TOKEN.finditer(json.dumps(x))
                        )

                    todo = sorted(ev, key=bindings, reverse=True)

                    def match(index, remaining):
                        if index == len(todo):
                            return True
                        for pos in remaining:
                            f, r = dict(forward), dict(reverse)
                            try:
                                walk(av[pos], todo[index], path + "{member}")
                                if match(index + 1, [x for x in remaining if x != pos]):
                                    return True
                            except AssertionError:
                                pass
                            forward.clear()
                            forward.update(f)
                            reverse.clear()
                            reverse.update(r)
                        return False

                    assert match(0, list(range(len(av)))), (
                        path + ": unordered membership or identity relationships differ"
                    )
                    return
                for k in e:
                    walk(a[k], e[k], path + "." + k, k)
            elif isinstance(e, list):
                assert len(a) == len(e), path + ": different collection length"
                for i, (av, ev) in enumerate(zip(a, e)):
                    walk(av, ev, path + "[" + str(i) + "]", parent)
            elif isinstance(e, str):
                at = list(self.TOKEN.finditer(a))
                et = list(self.TOKEN.finditer(e))
                assert self.TOKEN.split(a) == self.TOKEN.split(e) and len(at) == len(
                    et
                ), (path + ": different text or link")
                for am, em in zip(at, et):
                    av, ev = am[0], em[0]
                    assert av.rsplit(":", 1)[0] == ev.rsplit(":", 1)[0], (
                        path + ": different identity namespace"
                    )
                    assert forward.get(ev, av) == av and reverse.get(av, ev) == ev, (
                        path + ": inconsistent identity relationship"
                    )
                    forward[ev] = av
                    reverse[av] = ev
            else:
                assert a == e, path + ": different value"

        walk(actual, expected, "$")
        self.forward, self.reverse = forward, reverse


class Headers(dict):
    """Response headers with case-insensitive lookup (HTTP field names are case-insensitive)."""

    def __init__(self, values=()):
        super().__init__({str(k).lower(): v for k, v in dict(values or {}).items()})

    def get(self, key, default=None):
        return super().get(str(key).lower(), default)

    def __getitem__(self, key):
        return super().__getitem__(str(key).lower())

    def __setitem__(self, key, value):
        super().__setitem__(str(key).lower(), value)

    def __contains__(self, key):
        return super().__contains__(str(key).lower())

    def setdefault(self, key, default=None):
        return super().setdefault(str(key).lower(), default)


class Response:
    """What a program check sees of one product response: status, allowed headers, exact bytes."""

    def __init__(self, status, headers, content, url, request):
        self.status_code, self.headers, self.content, self.url, self.request = status, Headers(headers), content, url, request

    @property
    def text(self):
        return self.content.decode("utf-8", errors="replace")

    def json(self, **kwargs):
        return json.loads(self.content.decode("utf-8"), **kwargs)


class BrokerHTTP:
    """requests-compatible HTTP over the runtime's api operation: the request is prepared exactly as requests would
    send it (query encoding, JSON, form and multipart bodies, Basic auth) and the response bytes come back verbatim."""

    def __init__(self, broker, origin=ORIGIN):
        self.broker, self.origin = broker, origin

    def request(self, method, path, *, auth=None, headers=None, params=None, json=None, data=None, files=None):
        prepared = requests.Request(method.upper(), self.origin + path, params=params, json=json, data=data,
                                    files=files, headers=headers, auth=auth).prepare()
        url = urllib.parse.urlsplit(prepared.url)
        rpc = {"op": "api", "method": prepared.method,
               "path": (url.path or "/") + ("?" + url.query if url.query else ""), "binary": True}
        forwarded = {}
        for key, value in prepared.headers.items():
            lower = key.lower()
            if lower == "content-type":
                rpc["content_type"] = value
            elif lower in API_HEADERS:
                forwarded[lower] = value
            elif lower not in TRANSPORT_HEADERS:
                raise ValueError("header not available through the black-box api: " + key)
        if forwarded:
            rpc["headers"] = forwarded
        body = prepared.body
        if body is not None:
            rpc["body_base64"] = base64.b64encode(body if isinstance(body, bytes) else str(body).encode()).decode()
        try:
            answer = self.broker.call(rpc)
        except BrokerError as exc:
            # The runtime could not complete the product request (connection refused, timeout, malformed reply).
            raise AssertionError("candidate HTTP request failed: " + exc.detail[:300]) from None
        assert not answer.get("truncated"), "the product response exceeds the black-box response limit"
        content = base64.b64decode(answer.get("body_base64") or "")
        return Response(answer["status"], answer.get("headers"), content, prepared.url, prepared)


class GitRelay:
    """Local HTTP endpoint for the real Git client: each request is forwarded through the runtime's api operation
    (Git smart HTTP is one of its product protocols), so Git checks use the same channel as the model."""

    FORWARD = {"authorization", "accept", "content-type", "git-protocol"}

    def __init__(self, broker):
        relay = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def body(self):
                if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
                    data = bytearray()
                    while True:
                        size = int(self.rfile.readline().split(b";")[0].strip() or b"0", 16)
                        if size == 0:
                            while self.rfile.readline() not in (b"\r\n", b"\n", b""):
                                pass
                            break
                        data.extend(self.rfile.read(size))
                        self.rfile.readline()
                    data = bytes(data)
                else:
                    data = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                encoding = self.headers.get("Content-Encoding", "").lower()
                if encoding == "gzip":
                    data = gzip.decompress(data)
                elif encoding == "deflate":
                    data = zlib.decompress(data)
                return data

            def forward(self):
                data = self.body() if self.command in ("POST", "PUT") else b""
                rpc = {"op": "api", "method": self.command, "path": self.path, "binary": True}
                headers = {k.lower(): v for k, v in self.headers.items() if k.lower() in relay.FORWARD}
                if "content-type" in headers:
                    rpc["content_type"] = headers.pop("content-type")
                if headers:
                    rpc["headers"] = headers
                if data:
                    rpc["body_base64"] = base64.b64encode(data).decode()
                try:
                    answer = relay.broker.call(rpc)
                    status, content = answer["status"], base64.b64decode(answer.get("body_base64") or "")
                    reply = {k: v for k, v in (answer.get("headers") or {}).items()
                             if k not in ("content-length", "transfer-encoding")}
                except BrokerError as exc:
                    status, content, reply = 502, ("black-box request failed: " + exc.detail).encode(), {}
                relay.requests += 1
                self.send_response(status)
                for key, value in reply.items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(content)

            do_GET = do_POST = do_PUT = do_HEAD = forward

        self.broker, self.requests = broker, 0
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class Context:
    """Public access to one candidate instance (through the runtime) plus the observation normalizers."""

    def __init__(self, broker, out):
        self.broker = broker
        self.base = ORIGIN
        self.out = pathlib.Path(out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.http = BrokerHTTP(broker, ORIGIN)
        self.state = State()
        self.norm = Normalize(self.base)
        self.creds = dict(CREDS)
        self.raw = []
        self.aliases = AliasGraph()
        self.tree_cache = {}
        self.private_content = {}
        self.relay = None
        self.scratch = None
        self.current_case = None

    @property
    def git_base(self):
        """Origin of the local Git relay (started on first use)."""
        if self.relay is None:
            self.relay = GitRelay(self.broker)
        return self.relay.base

    @property
    def work(self):
        """Private scratch directory for Git clients (never inside the evidence)."""
        if self.scratch is None:
            self.scratch = pathlib.Path(tempfile.mkdtemp(prefix="gitea-check-"))
        return self.scratch

    def close(self):
        if self.relay is not None:
            self.relay.close()
        if self.scratch is not None:
            shutil.rmtree(self.scratch, ignore_errors=True)

    def restart_server(self):
        """Restart the product process with the same data directory (runtime op restart)."""
        status = self.broker.call({"op": "restart"})
        assert status.get("ready"), "the application did not come back after a restart: " + str(status.get("detail"))
        return status

    def running(self):
        return bool(self.broker.call({"op": "status"}).get("running"))

    def request(
        self,
        method,
        path,
        actor="alice",
        body=None,
        params=None,
        headers=None,
        data=None,
        files=None,
    ):
        auth = None
        if actor == "invalid":
            auth = ("bob", "definitely-wrong-password")
        elif actor:
            auth = (actor, self.creds.get(actor, CREDS.get(actor, "")))
        h = dict(headers or {})
        if actor and actor.startswith("token:"):
            auth = None
            h["Authorization"] = "token " + str(self.state[actor[6:]]["sha1"])
        r = self.http.request(method, path if path.startswith("/") else "/api/v1/" + path, auth=auth, headers=h,
                              params=params, json=body, data=data, files=files)
        try:
            payload = r.json(parse_float=json_number)
        except ValueError:
            payload = r.text
        item = {
            "method": method,
            "path": path,
            "actor": actor,
            "request": body,
            "params": params,
            "status": r.status_code,
            "body": payload,
        }
        self.raw.append(item)
        assert r.status_code < 500, f"candidate HTTP server error {r.status_code}: {str(payload)[:300]}"
        if r.status_code < 400:
            self.remember_private_content(payload, self.norm.repository_scope(r.url))
            self.remember_private_content(body, self.norm.repository_scope(r.url))
        r.pbp_actor = actor
        r.pbp_request_body = body
        return r, payload

    def get_raw(self, path, actor=None):
        """One request whose response bytes matter more than their JSON form (downloads, raw files)."""
        auth = (actor, self.creds[actor]) if actor else None
        return self.http.request("GET", path, auth=auth)

    def remember_private_content(self, value, scope=""):
        # Learn protected fixture text only from successful, scoped operations.
        # No candidate storage access or universal information-flow claim.
        if isinstance(value, list):
            for item in value:
                self.remember_private_content(item, scope)
        elif isinstance(value, dict):
            if value.get("private") is True and isinstance(value.get("full_name"), str):
                scope = value["full_name"]
                self.private_content.setdefault(scope, set())
            repository = value.get("repository")
            if isinstance(repository, dict) and repository.get("private") is True:
                scope = repository.get("full_name", scope)
                self.private_content.setdefault(scope, set())
            if scope in self.private_content:
                for field in ("title", "body", "description", "content", "content_base64"):
                    text = value.get(field)
                    if isinstance(text, str) and text.strip():
                        self.private_content[scope].add(text)
                        if field in ("content", "content_base64"):
                            try:
                                decoded = base64.b64decode("".join(text.split()), validate=True).decode("utf-8")
                            except (ValueError, UnicodeError):
                                continue
                            # Short generic words are not reliable secret-text
                            # signatures; the full encoded value remains checked.
                            if len(decoded.strip()) > 12:
                                self.private_content[scope].add(decoded)
            for item in value.values():
                if isinstance(item, (dict, list)):
                    self.remember_private_content(item, scope)

    def notification_permissions(self, payload, actor):
        """Optional notification permissions are checked against the live repo.

        Upstream intentionally omits them because its notification converter
        only has minimum read access. Fill the same authoritative projection in
        both runs; never discard permissions or accept contradictory extras.
        """
        cache = {}

        def repository(repo):
            if repo is None:
                return None
            name = repo["full_name"]
            if name not in cache:
                r, complete = self.request("GET", "repos/" + name, actor)
                assert r.status_code == 200 and isinstance(
                    complete.get("permissions"), dict
                ), "notification repository permission projection unavailable"
                cache[name] = complete["permissions"]
            permissions = cache[name]
            if "permissions" in repo and repo["permissions"] is not None:
                assert (
                    repo["permissions"] == permissions
                ), "notification permissions contradict repository permissions"
            result = {**repo, "permissions": permissions}
            if isinstance(repo.get("parent"), dict):
                result["parent"] = repository(repo["parent"])
            return result

        def walk(value):
            if isinstance(value, list):
                return [walk(x) for x in value]
            if (
                isinstance(value, dict)
                and {"subject", "unread", "repository"} <= value.keys()
            ):
                return {**value, "repository": repository(value["repository"])}
            return value

        return walk(payload)

    def local_resource_path(self, href):
        """Follow only the local application's returned resource, without redirects."""
        assert isinstance(href, str) and href, "advertised resource URL is missing"
        target = urllib.parse.urlsplit(urllib.parse.urljoin(self.base + "/", href))
        assert application_origin_matches(self.base, target.geturl()), (
            "advertised resource leaves application origin"
        )
        assert (
            target.username is None and target.password is None and not target.fragment
        ), "invalid advertised resource URL"
        return urllib.parse.urlunsplit(("", "", target.path, target.query, ""))

    def tag_commit_references(self, payload, url, actor):
        """A tag object and its peeled commit can address the same commit URL.

        Keep their distinct returned IDs. Only replace the link after all three
        actual resources (tag ID, advertised commit SHA, returned URL) resolve
        to exactly the same complete commit, including content and parents.
        """
        scope = self.norm.repository_scope(url)

        def target(oid):
            assert re.fullmatch("[0-9a-f]{40}", str(oid)), "invalid tag/commit identity"
            rr, commit = self.request(
                "GET", "repos/" + scope + "/git/commits/" + oid, actor
            )
            assert (
                rr.status_code == 200 and isinstance(commit, dict) and commit.get("sha")
            ), "tag commit resource is unavailable"
            return commit

        def walk(value):
            if isinstance(value, list):
                return [walk(x) for x in value]
            if not isinstance(value, dict):
                return value
            if {
                "id",
                "name",
                "message",
                "commit",
                "zipball_url",
                "tarball_url",
            } <= value.keys():
                assert scope, "tag repository relationship missing"
                meta = value["commit"]
                assert isinstance(meta, dict), "invalid tag commit metadata"
                expected = target(meta["sha"])
                assert (
                    expected["sha"] == meta["sha"]
                ), "tag advertises a different commit identity"
                assert (
                    target(value["id"]) == expected
                ), "tag ID resolves to another commit"
                path = self.local_resource_path(meta["url"])
                parsed = urllib.parse.urlsplit(path)
                m = re.fullmatch(
                    r"/api/v1/repos/([^/]+/[^/]+)/git/commits/([0-9a-f]{40})",
                    parsed.path,
                )
                assert (
                    m and m[1] == scope
                ), "tag commit URL identifies another repository"
                rr, actual = self.request("GET", path, actor)
                assert (
                    rr.status_code == 200 and actual == expected
                ), "tag commit URL does not resolve to its complete advertised commit"
                return {
                    **value,
                    "commit": {
                        **meta,
                        "url": self.base
                        + "/api/v1/repos/"
                        + scope
                        + "/git/commits/"
                        + meta["sha"],
                    },
                }
            return {k: walk(x) for k, x in value.items()}

        return walk(payload)

    def tree_references(self, payload, url, actor):
        """Resolve Gitea treeish references, retaining actual tree relationships.

        The pinned API accepts a commit or a tree and echoes its ResolvedID.
        A full commit's advertised tree must resolve to that commit's contents.
        Tree identities are deduplicated only after their complete immediate
        entries agree; blob/tree entry identities, modes, paths and sizes remain
        observable. This does not equate commit IDs with tree IDs.
        """

        def target(scope, oid):
            assert scope and re.fullmatch(
                "[0-9a-f]{40}", str(oid)
            ), "invalid tree reference"
            cachekey = (scope, oid, actor)
            if cachekey not in self.tree_cache:
                entries = []
                page = 1
                total = None
                while True:
                    rr, obj = self.request(
                        "GET",
                        "repos/" + scope + "/git/trees/" + oid,
                        actor,
                        params={"per_page": 50, "page": page},
                    )
                    assert rr.status_code == 200 and isinstance(
                        obj, dict
                    ), "advertised tree reference is not readable"
                    batch = obj.get("tree") or []
                    assert isinstance(batch, list), "tree entries must be a collection"
                    if total is None:
                        total = obj["total_count"]
                    assert (
                        obj["total_count"] == total
                    ), "tree size changed during resolution"
                    entries.extend(batch)
                    if len(entries) >= total:
                        break
                    assert batch and page < 50, "incomplete tree resolution"
                    page += 1
                assert (
                    len(entries) == total and len({x["path"] for x in entries}) == total
                ), "duplicate or missing tree entry"
                projection = sorted(
                    (
                        {
                            k: x[k]
                            for k in ("path", "mode", "type", "size", "sha")
                            if k in x
                        }
                        for x in entries
                    ),
                    key=lambda x: x["path"],
                )
                signature = json.dumps(
                    projection, sort_keys=True, separators=(",", ":")
                )
                self.tree_cache[cachekey] = signature
                key = (scope, oid)
                assert (
                    key not in self.norm.tree_targets
                    or self.norm.tree_targets[key] == signature
                ), "immutable tree identity changed its contents"
                self.norm.tree_targets[key] = signature
            return self.tree_cache[cachekey]

        def metadata(meta, scope, expected=None, legacy_directory=False):
            signature = target(scope, meta["sha"])
            if expected is not None:
                assert (
                    signature == expected
                ), "advertised tree differs from its commit tree"
            link = meta.get("url")
            if link:
                parsed = urllib.parse.urlsplit(self.local_resource_path(link))
                segment = r"(?:trees|blobs)" if legacy_directory else "trees"
                m = re.fullmatch(
                    r"/api/v1/repos/([^/]+/[^/]+)/git/" + segment + r"/([0-9a-f]{40})",
                    parsed.path,
                )
                assert (
                    m and m[1] == scope and target(scope, m[2]) == signature
                ), "tree URL does not identify its advertised contents"

        def walk(value, scope):
            if isinstance(value, list):
                for x in value:
                    walk(x, scope)
            elif isinstance(value, dict):
                for key in ("url", "html_url"):
                    if isinstance(value.get(key), str):
                        scope = self.norm.repository_scope(value[key], scope)
                commit = value.get("commit")
                if (
                    isinstance(commit, dict)
                    and isinstance(commit.get("tree"), dict)
                    and value.get("sha")
                ):
                    metadata(commit["tree"], scope, target(scope, value["sha"]))
                elif isinstance(value.get("tree"), dict) and value.get("sha"):
                    metadata(value["tree"], scope, target(scope, value["sha"]))
                if value.get("sha") and (
                    value.get("type") == "tree"
                    or isinstance(value.get("tree"), list)
                    or "/git/trees/" in str(value.get("url", ""))
                ):
                    metadata(value, scope)
                if value.get("sha") and value.get("type") == "dir":
                    for link in (
                        value.get("git_url"),
                        value.get("_links", {}).get("git"),
                    ):
                        metadata(
                            {"sha": value["sha"], "url": link},
                            scope,
                            legacy_directory=True,
                        )
                for child in value.values():
                    walk(child, scope)

        walk(payload, self.norm.repository_scope(url))
        return payload

    def observe(self, r, payload, hint="object"):
        status = r.status_code
        if status in (301, 302, 303, 307, 308):
            location = self.local_resource_path(r.headers.get("Location"))
            return {"status": status, "location": self.norm.text(location, uri=True)}
        if status >= 400:
            # Wording and DB-engine diagnostics are not an implementation requirement.
            if status in (401, 403, 404):
                scope = self.norm.repository_scope(r.url)
                protected = self.private_content.get(scope, ())
                supplied = []
                def request_text(value, field=""):
                    if isinstance(value, dict):
                        for key, item in value.items():
                            request_text(item, key)
                    elif isinstance(value, list):
                        for item in value:
                            request_text(item, field)
                    elif isinstance(value, str):
                        supplied.append(" ".join(value.split()))
                        if field in ("content", "content_base64"):
                            try:
                                supplied.append(" ".join(base64.b64decode("".join(value.split()), validate=True).decode("utf-8").split()))
                            except (ValueError, UnicodeError):
                                pass
                request_text(getattr(r, "pbp_request_body", None))

                def no_private_text(value):
                    # Inspect raw/plain text, HTML and JSON string leaves before
                    # benign error representations collapse to the same result.
                    forms = (
                        value,
                        html.unescape(value),
                        re.sub(r"<[^>]*>", " ", html.unescape(value)),
                    )
                    for secret in protected:
                        needle = " ".join(secret.split())
                        if any(needle in text for text in supplied):
                            continue  # Echoing the caller's own input reveals no new content.
                        assert all(
                            needle not in " ".join(form.split()) for form in forms
                        ), "denied API response exposes known private resource text"

                def no_resource_data(value):
                    if isinstance(value, list):
                        for item in value:
                            no_resource_data(item)
                    elif isinstance(value, dict):
                        # Error/problem titles and details may explain the denial.
                        # Resource DTOs, including nested arrays, may not carry
                        # protected content, identities or permission projections.
                        signatures = (
                            {"owner", "full_name"}, {"name", "private"},
                            {"content", "sha"}, {"path", "sha"},
                            {"body", "user", "id"}, {"head", "base", "number"},
                        )
                        assert not any(fields <= value.keys() for fields in signatures), (
                            "denied API response exposes resource data"
                        )
                        permissions = value.get("permissions")
                        assert not (isinstance(permissions, dict) and any(
                            type(permissions.get(k)) is bool for k in ("read", "write", "admin", "pull", "push")
                        )), "denied API response exposes resource permissions"
                        assert not (
                            {"login", "id"} <= value.keys()
                            or {"title", "number"} <= value.keys()
                        ), "denied API response exposes resource identity"
                        for item in value.values():
                            no_resource_data(item)
                    elif isinstance(value, str):
                        no_private_text(value)

                no_private_text(r.text)
                no_resource_data(payload)
            val = {"error": True}
        elif hint == "raw-bytes":
            # Raw file payloads are bytes, even when requests guesses a charset
            # or the file happens to contain parseable JSON.
            val = {"bytes_base64": base64.b64encode(r.content).decode()}
        elif hint == "markdown":
            from markup_observation import observe_markup

            val = observe_markup(payload)
        else:
            path = urllib.parse.urlsplit(r.url).path
            if re.match(r"^/api/v1/repos/[^/]+/[^/]+/(?:contents(?:/|$)|git/blobs/)", path):
                git_blob_content(payload)
            if (
                path.endswith(".git/info/lfs/objects/batch")
                and isinstance(payload, dict)
                and "objects" in payload
            ):
                payload = lfs_batch_payload(getattr(r, "pbp_verified_lfs", payload))
            payload = self.notification_permissions(
                payload, getattr(r, "pbp_actor", "alice")
            )
            payload = self.tag_commit_references(
                payload, r.url, getattr(r, "pbp_actor", "alice")
            )
            payload = self.tree_references(
                payload, r.url, getattr(r, "pbp_actor", "alice")
            )
            val = self.norm.clean(
                payload, hint, scope=self.norm.repository_scope(r.url)
            )
        return {"status": status, "body": val}

    def pull_ready(self, path, mergeable, initial=None, timeout=25, stable_for=2):
        """Observe a stable PR after background checks; never retry a mutation.

        Creation can return true before a queued check temporarily sets false.
        Require sustained agreement, resetting on any changed graph/state key.
        Only the computed mergeable field of a mutation response is stabilized;
        its other response fields remain scored exactly as originally returned.
        """
        deadline = time.monotonic() + timeout
        since = None
        previous = None
        last = None
        while time.monotonic() < deadline:
            r, p = self.request("GET", path, "alice")
            last = (r.status_code, p)
            assert r.status_code == 200, (
                "PR readiness resource unavailable: " + str(last)[:500]
            )
            key = (
                p["id"],
                p["number"],
                p["state"],
                p["merged"],
                p["head"]["sha"],
                p["base"]["sha"],
                p["mergeable"],
            )
            if initial is not None:
                expected = (
                    initial["id"],
                    initial["number"],
                    initial["state"],
                    initial["merged"],
                    initial["head"]["sha"],
                    initial["base"]["sha"],
                )
                assert (
                    key[:-1] == expected
                ), "PR identity/state/graph changed while awaiting its computed readiness"
            if p["mergeable"] == mergeable:
                if key != previous:
                    since = time.monotonic()
                if since is not None and time.monotonic() - since >= stable_for:
                    return p
            else:
                since = None
            previous = key
            time.sleep(0.1)
        raise AssertionError(
            "PR did not reach stable mergeable="
            + str(mergeable)
            + ": "
            + str(last)[:700]
        )


class Suite:
    def __init__(self):
        self.cases = []
        self.ids = set()

    def add(self, family, scenario, step, action, channel="api", description=""):
        if family.endswith("fixture"):
            channel = "setup"
        cid = f"{channel}.{family}.{scenario}.{step}"
        if cid in self.ids:
            raise ValueError("duplicate " + cid)
        self.ids.add(cid)
        self.cases.append(
            Case(cid, family, scenario, channel, description or step, action)
        )
        return cid

    def api(
        self,
        family,
        scenario,
        step,
        method,
        path,
        actor="alice",
        body=None,
        params=None,
        save=None,
        status=None,
        want=None,
        check=None,
        hint="object",
        headers=None,
        data=None,
        eventually=None,
        settle_pull=None,
        before=None,
        temporal_page=None,
    ):
        def action(c, relaxed=False):
            pp = resolve(path, c)
            bb = resolve(body, c)
            qq = resolve(params, c)
            aa = resolve(actor, c)
            if before:
                before(c)
            r, p = c.request(
                method, pp, aa, bb, qq, resolve(headers, c), resolve(data, c)
            )
            if relaxed:
                # Unscored setup: any success status; keep only the values later steps need.
                assert 200 <= r.status_code < 300, f"setup {method} {pp}: status {r.status_code}; {str(p)[:300]}"
                if save:
                    c.state[save] = p
                return None
            if eventually:
                deadline = time.monotonic() + 15
                while (
                    not isinstance(p, dict)
                    or any(p.get(k) != v for k, v in eventually.items())
                ) and time.monotonic() < deadline:
                    time.sleep(0.15)
                    r, p = c.request(
                        method, pp, aa, bb, qq, resolve(headers, c), resolve(data, c)
                    )
                subset(p, eventually)
            if settle_pull is not None and r.status_code < 400:
                endpoint = p["url"] if isinstance(p.get("url"), str) else ""
                endpoint = urllib.parse.urlsplit(endpoint).path
                match = re.fullmatch(
                    r"/(?:api/v1/repos/)?([^/]+/[^/]+/pulls/\d+)", endpoint
                )
                assert match, "PR response lacks its resource URL"
                endpoint = "/api/v1/repos/" + match[1]
                ready = c.pull_ready(endpoint, settle_pull, initial=p)
                p = {**p, "mergeable": ready["mergeable"]}
            if temporal_page and r.status_code < 400:
                assert (
                    method == "GET" and pp == "repos/search"
                ), "temporal page helper is scoped to repository search"
                collection = []
                page = 1
                while True:
                    rr, complete = c.request(
                        "GET",
                        pp,
                        aa,
                        params={
                            **qq,
                            "sort": "alpha",
                            "order": "asc",
                            "page": page,
                            "limit": 50,
                        },
                    )
                    assert (
                        rr.status_code == 200
                    ), "complete repository collection unavailable"
                    collection.extend(complete["data"])
                    if len(complete["data"]) < 50:
                        break
                    page += 1
                    assert (
                        page <= 20
                    ), "repository fixture exceeded bounded collection size"
                p = {
                    **p,
                    **repository_time_page(
                        p["data"],
                        collection,
                        temporal_page,
                        qq["order"] == "desc",
                        qq["page"],
                        qq["limit"],
                        c.norm,
                    ),
                }
            if save and r.status_code < 400:
                c.state[save] = p
            assert (
                r.status_code < 500
            ), f"upstream/candidate server error {r.status_code}: {str(p)[:300]}"
            if status is not None:
                assert r.status_code in (
                    [status] if isinstance(status, int) else status
                ), f"{method} {pp}: status {r.status_code}; {str(p)[:350]}"
            if want:
                subset(p, resolve(want, c))
            if check:
                check(c, r, p)
            observation = c.observe(r, p, hint)
            # Only explicit per-case alternatives are equivalent. Validate the
            # actual response and confidentiality first; never merge all denials.
            if status is not None and not isinstance(status, int):
                observation["status"] = min(status)
            return observation

        return self.add(
            family,
            scenario,
            step,
            action,
            description=f'{method} {path if isinstance(path,str) else "<relational resource>"} as {actor}',
        )

    def manifest(self):
        return [
            dict(
                id=x.id,
                family=x.family,
                scenario=x.scenario,
                channel=x.channel,
                scored=x.channel != "setup",
                description=x.description,
            )
            for x in self.cases
        ]
