"""Validate workspace link targets against the current tree and pending changes."""
from collections import deque
import os
from pathlib import Path
import stat
import blackbox_runtime as runtime


def link_text(target):
    return (isinstance(target, str) and bool(target) and len(target) <= 4096
            and not target.startswith("/") and "\\" not in target
            and not any(ord(char) < 32 or ord(char) == 127 for char in target))


def validate_links(workspace, changes):
    """Reject links whose resolved destination leaves the workspace, including pending links.

    Pending entries replace the corresponding existing entry when resolving paths.
    Dangling targets below the workspace are allowed; cycles are rejected. This
    checks link semantics. File creation must independently use safe directory handles.
    """
    root = Path(workspace).absolute()
    overlay = {}
    for name, value in changes.items():
        name = name.removeprefix("/workspace/")
        parts = tuple(part for part in name.split("/") if part not in ("", "."))
        if not parts or ".." in parts or name.startswith("/"):
            raise ValueError("a file path must stay below the workspace")
        overlay[parts] = value.get("symlink") if isinstance(value, dict) and "symlink" in value else None
    links = {}
    count = 0
    def scan(fd, parts):
        nonlocal count
        for name, info in runtime.list_directory(fd):
            count += 1
            if count > 20000:
                raise ValueError("the workspace tree exceeds 20000 entries")
            rel = tuple(parts) + (name,)
            if stat.S_ISLNK(info.st_mode):
                links[rel] = os.readlink(name, dir_fd=fd)
            elif stat.S_ISDIR(info.st_mode):
                with runtime.open_relative(fd, name, directory=True) as child:
                    scan(child, rel)
    with runtime.open_directory(root) as root_fd:
        scan(root_fd, ())
    for parts, target in overlay.items():
        if target is None:
            links.pop(parts, None)
        else:
            if not link_text(target):
                raise ValueError("symlink targets must be relative workspace paths")
            links[parts] = target

    def target_parts(target):
        if target.startswith("/"):
            try:
                return list(Path(target).relative_to(root).parts), True
            except ValueError:
                raise ValueError("symlink target must resolve inside the workspace") from None
        return target.split("/"), False

    def resolve(parts, target):
        current = list(parts[:-1])
        pending, absolute = target_parts(target)
        if absolute:
            current = []
        pending = deque(pending)
        followed = 0
        while pending:
            item = pending.popleft()
            if item in ("", "."):
                continue
            if item == "..":
                if not current:
                    raise ValueError("symlink target must resolve inside the workspace")
                current.pop()
                continue
            entry_parts = tuple(current + [item])
            if entry_parts in overlay:
                link = overlay[entry_parts]
            elif entry_parts in links:
                link = links[entry_parts]
            else:
                link = None
            if link is None:
                current.append(item)
                continue
            followed += 1
            if followed > 40:
                raise ValueError("symlink targets contain a loop or too many links")
            expanded, absolute = target_parts(link)
            if absolute:
                current = []
            pending.extendleft(reversed(expanded))
        return root.joinpath(*current)

    for parts, target in links.items():
        resolve(parts, target)
