"""Semantic observation for the Markdown API, independent of renderer CSS/wrappers."""

from html.parser import HTMLParser
import re


def compact(value):
    return re.sub(r"\s+", " ", value).strip()


class Markup(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.active = []
        self.semantic = []
        self.checkboxes = []
        self.lists = []
        self.list_structure = []
        self.tables = []
        self.table_structure = []

    def close_cells(self):
        if not self.tables:
            return
        boundary = self.tables[-1]["boundary"]
        previous = next((i for i in range(len(self.active) - 1, boundary - 1, -1)
                         if self.active[i]["tag"] in ("th", "td")), None)
        if previous is not None:
            while len(self.active) > previous:
                self.handle_endtag(self.active[-1]["tag"])

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        assert tag not in (
            "script",
            "iframe",
            "object",
            "embed",
        ), "executable markup survives sanitization"
        assert not any(
            k.lower().startswith("on") for k in attrs
        ), "event handler survives sanitization"
        assert not (
            re.sub(r"[\t\r\n]", "", attrs.get("href", "")).strip().lower().startswith("javascript:")
        ), "unsafe link survives sanitization"
        alias = {"b": "strong", "i": "em", "s": "del", "strike": "del"}
        tag = alias.get(tag, tag)
        if tag in ("ul", "ol"):
            node = {"kind": tag, "items": []}
            if tag == "ol":
                node.update(start=int(attrs.get("start", "1")), reversed="reversed" in attrs)
            parent = next((x.get("list_item") for x in reversed(self.active)
                           if "list_item" in x), None)
            (parent["children"] if parent is not None else self.list_structure).append(node)
            self.lists.append({"boundary": len(self.active), "node": node})
        elif tag == "li" and self.lists:
            # HTML permits omitted </li> before the next sibling. Preserve the
            # same semantic records as explicit end tags, including nested lists.
            boundary = self.lists[-1]["boundary"]
            previous = next(
                (i for i in range(len(self.active) - 1, boundary - 1, -1)
                 if self.active[i]["tag"] == "li"),
                None,
            )
            if previous is not None:
                while len(self.active) > previous:
                    self.handle_endtag(self.active[-1]["tag"])
        if tag == "input" and attrs.get("type", "").lower() == "checkbox":
            self.checkboxes.append("checked" in attrs)
            parent = next((x.get("list_item") for x in reversed(self.active)
                           if "list_item" in x), None)
            if parent is not None:
                parent["checks"].append("checked" in attrs)
        if tag == "table":
            node = {"rows": []}
            self.table_structure.append(node)
            self.tables.append({"node": node, "row": None, "boundary": len(self.active)})
        elif tag == "tr" and self.tables:
            self.close_cells()
            row = []
            self.tables[-1]["node"]["rows"].append(row)
            self.tables[-1]["row"] = row
        elif tag in ("th", "td"):
            self.close_cells()
        if (
            tag
            in (
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
                "strong",
                "em",
                "del",
                "code",
                "pre",
                "li",
                "th",
                "td",
                "blockquote",
            )
            or tag == "a"
            and attrs.get("href", "")
            and not attrs["href"].startswith("#")
        ):
            item = {"tag": tag, "text": [], "href": attrs.get("href")}
            if tag == "li" and self.lists:
                node = {"text": "", "checks": [], "children": []}
                self.lists[-1]["node"]["items"].append(node)
                item["list_item"] = node
            if tag in ("th", "td") and self.tables:
                table = self.tables[-1]
                if table["row"] is None:
                    table["row"] = []
                    table["node"]["rows"].append(table["row"])
                node = {"kind": tag, "text": "", "colspan": int(attrs.get("colspan", "1")),
                        "rowspan": int(attrs.get("rowspan", "1"))}
                table["row"].append(node)
                item["table_cell"] = node
            self.active.append(item)
        if tag in ("p", "div", "br", "li", "tr", "h1", "h2", "h3", "pre"):
            self.handle_data(" ")

    def handle_endtag(self, tag):
        tag = {"b": "strong", "i": "em", "s": "del", "strike": "del"}.get(tag, tag)
        if tag in ("ul", "ol") and self.lists:
            boundary = self.lists.pop()["boundary"]
            while len(self.active) > boundary:
                self.handle_endtag(self.active[-1]["tag"])
        if tag in ("tr", "table") and self.tables:
            self.close_cells()
            if tag == "table":
                self.tables.pop()
            else:
                self.tables[-1]["row"] = None
        for i in range(len(self.active) - 1, -1, -1):
            if self.active[i]["tag"] == tag:
                item = self.active.pop(i)
                entry = {"kind": tag, "text": compact("".join(item["text"]))}
                for field in ("list_item", "table_cell"):
                    if field in item:
                        item[field]["text"] = entry["text"]
                if tag == "a":
                    entry["href"] = item["href"]
                self.semantic.append(entry)
                break
        if tag in ("p", "div", "br", "li", "tr", "h1", "h2", "h3", "pre"):
            self.handle_data(" ")

    def handle_data(self, text):
        self.text.append(text)
        for entry in self.active:
            entry["text"].append(text)


def observe_markup(html):
    assert isinstance(html, str), "Markdown API must return rendered text"
    parser = Markup()
    parser.feed(html)
    parser.close()
    # Valid HTML may omit closing li/td/th/tr tags. Finish the pending semantic
    # records without changing their list/table ownership.
    while parser.active:
        parser.handle_endtag(parser.active[-1]["tag"])
    return {
        "text": compact("".join(parser.text)),
        "semantics": parser.semantic,
        "task_checks": parser.checkboxes,
        "lists": parser.list_structure,
        "tables": parser.table_structure,
    }
