#!/usr/bin/env python3
"""Read-only structural checks for generated Project Docs documents (Python 3.10+)."""

import argparse
from collections import Counter
import os
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit


ID = re.compile(r"\b(?:REQ|AC)-\d{3,}\b")
METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
MVP_LOCATION = re.compile(r"docs/v([A-Za-z0-9][A-Za-z0-9._-]*)/MVP\.md")


def prose(text):
    """Ignore fenced examples and HTML comments when checking Markdown prose."""
    result, fence = [], None
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if match:
            marker = match[1]
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            result.append("")
        else:
            result.append(line if fence is None else "")
    return re.sub(r"<!--.*?-->", "", "\n".join(result), flags=re.S)


def anchors(text):
    seen, result = Counter(), set()
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", prose(text), re.M):
        heading = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", heading)
        base = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        suffix = f"-{seen[base]}" if seen[base] else ""
        result.add(base + suffix)
        seen[base] += 1
    result.update(re.findall(r'''\bid=["']([^"']+)["']''', text))
    return result


class Validator:
    def __init__(self, root, include_product=False, require_implementation=False, mvp_path=None):
        self.root = Path(root).resolve()
        self.include_product = include_product
        self.require_implementation = require_implementation
        self.issues = []
        self.docs = {}
        self.ids = set()
        self.version = None
        self.requested_mvp = mvp_path
        self.mvp_path = None

    def report(self, level, path, code, message):
        self.issues.append((level, path, code, message))

    def read(self, relative):
        path = self.root / relative
        try:
            resolved = path.resolve()
            if not resolved.is_relative_to(self.root):
                self.report("ERROR", relative, "outside-root", "Document resolves outside project root.")
                return None
            folders = ["docs/implementation", "docs/decisions"]
            if self.include_product:
                folders.append("docs/product")
            selected_mvp = self.root / self.mvp_path if self.mvp_path else None
            if resolved not in (self.root / "AGENTS.md", selected_mvp) and not any(resolved.is_relative_to(self.root / folder) for folder in folders):
                self.report("SKIP", relative, "read-scope", "Resolved document is outside selected scope.")
                return None
            return path.read_text(encoding="utf-8-sig")
        except (OSError, ValueError, RuntimeError) as exc:
            self.report("ERROR", relative, "read", str(exc))
            return None

    def is_file(self, relative):
        try:
            return (self.root / relative).is_file()
        except (OSError, ValueError) as exc:
            self.report("ERROR", relative, "file-access", str(exc))
            return False

    def run(self):
        try:
            root_exists = self.root.is_dir()
        except (OSError, ValueError) as exc:
            self.report("ERROR", ".", "root", f"Cannot inspect project root: {exc}")
            return self.issues
        if not root_exists:
            self.report("ERROR", ".", "root", "Project root does not exist.")
            return self.issues
        if self.require_implementation:
            for relative in ("AGENTS.md",
                             "docs/implementation/ARCHITECTURE.md", "docs/implementation/CONVENTIONS.md"):
                if not self.is_file(relative):
                    self.report("ERROR", relative, "required-file", "Required handoff document is missing.")
        candidates = [self.root / "AGENTS.md"]
        folders = ["docs/implementation", "docs/decisions"]
        if self.include_product:
            folders.append("docs/product")
        for folder in folders:
            # walk reports inaccessible subdirectories instead of silently omitting them.
            def scan_error(exc):
                if not (isinstance(exc, FileNotFoundError) and exc.filename is not None
                        and Path(exc.filename) == self.root / folder):
                    self.report("ERROR", folder, "scan", str(exc))

            try:
                for parent, directories, files in os.walk(self.root / folder, onerror=scan_error):
                    directories.sort()
                    candidates.extend(Path(parent) / name for name in sorted(files) if name.endswith(".md"))
            except (OSError, RecursionError) as exc:
                scan_error(exc)
        for path in candidates:
            relative = path.relative_to(self.root).as_posix()
            if relative == "docs/implementation/MVP.md":
                self.report("ERROR", relative, "legacy-mvp", "Legacy MVP path; migrate only when the project layout change is authorized.")
                continue
            if self.is_file(relative):
                text = self.read(relative)
                if text is not None:
                    self.docs[relative] = text
        self.select_mvp()
        if self.require_implementation and not self.mvp_path:
            self.report("ERROR", "AGENTS.md", "mvp-selection", "Handoff requires a valid current MVP entry in AGENTS.md.")
        api = "docs/implementation/openapi.yaml"
        api_exists = self.is_file(api)
        if not self.docs and not api_exists:
            self.report("ERROR", ".", "no-docs", "No documents found in selected scope.")
        self.mvp()
        for relative, text in self.docs.items():
            body = prose(text)
            if re.search(r"\{\{[^{}]+\}\}", body):
                self.report("ERROR", relative, "placeholder", "Unfilled template placeholder outside code fences.")
            if relative.startswith("docs/implementation/") and not relative.endswith("/MVP.md"):
                version = re.search(r"^적용 MVP:\s*(\S+)", body, re.M)
                if not version:
                    self.report("ERROR", relative, "mvp-version", "Missing '적용 MVP: <version>'.")
                elif self.version and version[1] != self.version:
                    self.report("ERROR", relative, "mvp-version", f"Expected MVP {self.version}, found {version[1]}.")
            if relative in ("AGENTS.md", self.mvp_path) or relative.startswith("docs/implementation/"):
                if self.mvp_path in self.docs:
                    active = re.sub(r"^- 변경 요약:.*?(?=^## |\Z)", "", body, flags=re.M | re.S) if relative == self.mvp_path else body
                    for identifier in sorted(set(ID.findall(active)) - self.ids):
                        self.report("ERROR", relative, "unknown-id", f"{identifier} is not defined in current MVP.")
            self.links(relative, body)
        if api_exists:
            self.openapi(api)
        return self.issues

    def select_mvp(self):
        target = self.requested_mvp
        if target is None or self.require_implementation:
            entries = re.findall(r"^- 현재 MVP:[^\n]*$", prose(self.docs.get("AGENTS.md", "")), re.M)
            if not entries:
                if self.require_implementation:
                    self.report("ERROR", "AGENTS.md", "mvp-selection", "Handoff requires the current MVP entry, even with --mvp.")
                elif any(path.startswith("docs/implementation/") for path in self.docs):
                    self.report("SKIP", "AGENTS.md", "mvp-selection", "No current MVP entry; no version is selected automatically.")
                return
            match = re.fullmatch(r"- 현재 MVP:\s*\[[^\]\n]+\]\(([^)\n]+)\)\s*", entries[0])
            if len(entries) != 1 or not match:
                self.report("ERROR", "AGENTS.md", "mvp-selection", "Expected exactly one '- 현재 MVP: [MVP](docs/v<version>/MVP.md)' entry.")
                return
            current = match[1]
            if not MVP_LOCATION.fullmatch(current):
                self.report("ERROR", "AGENTS.md", "mvp-selection", "Current MVP entry must use docs/v<version>/MVP.md with no query or fragment.")
                return
            if target is None:
                target = current
            elif target != current:
                self.report("ERROR", "AGENTS.md", "mvp-handoff", f"Handoff target {target} differs from current MVP {current}.")
        if not isinstance(target, str) or not MVP_LOCATION.fullmatch(target):
            self.report("ERROR", "AGENTS.md", "mvp-selection", "MVP target must be docs/v<version>/MVP.md with no query or fragment.")
            return
        self.mvp_path = target
        if not self.is_file(target):
            self.report("ERROR", target, "required-file", "Selected MVP does not exist.")
            return
        text = self.read(target)
        if text is not None:
            self.docs[target] = text

    def mvp(self):
        relative = self.mvp_path
        if relative not in self.docs:
            if any(ID.search(prose(text)) for path, text in self.docs.items()
                   if path == "AGENTS.md" or path.startswith("docs/implementation/")):
                self.report("SKIP", relative or "AGENTS.md", "id-check", "Selected MVP unavailable; cannot resolve REQ/AC references.")
            return
        body = prose(self.docs[relative])
        version = re.search(r"^- 버전:\s*(\S+)\s*$", body, re.M)
        status = re.search(r"^- 상태:\s*(Draft|Ready)\s*$", body, re.M)
        if version:
            self.version = version[1]
            if MVP_LOCATION.fullmatch(relative)[1] != self.version:
                self.report("ERROR", relative, "mvp-folder-version", "MVP header version does not match its version directory.")
        else:
            self.report("ERROR", relative, "metadata", "Missing '- 버전: <version>'.")
        if not status:
            self.report("ERROR", relative, "metadata", "Status must be Draft or Ready.")
        requirements = re.findall(r"^#{2,6}\s+(REQ-\d{3,})\b", body, re.M)
        section = re.search(r"^## 완료 기준\s*$\n(.*?)(?=^## |\Z)", body, re.M | re.S)
        criteria = re.findall(r"^\|\s*`?(AC-\d{3,})`?\s*\|([^|]*)\|([^\n]*)", section[1] if section else "", re.M)
        for kind, values in (("REQ", requirements), ("AC", [item[0] for item in criteria])):
            if not values:
                self.report("ERROR", relative, "missing-id", f"No {kind} definitions found.")
            for identifier, count in Counter(values).items():
                if count > 1:
                    self.report("ERROR", relative, "duplicate-id", f"{identifier} is defined {count} times.")
        self.ids = set(requirements) | {item[0] for item in criteria}
        covered = set()
        for identifier, refs, condition in criteria:
            linked = set(re.findall(r"\bREQ-\d{3,}\b", refs))
            if not linked:
                self.report("ERROR", relative, "ac-requirement", f"{identifier} has no associated REQ.")
            if not condition.strip(" |"):
                self.report("ERROR", relative, "ac-condition", f"{identifier} has no acceptance condition.")
            covered.update(linked)
        for identifier in sorted(set(requirements) - covered):
            self.report("ERROR", relative, "req-coverage", f"{identifier} has no AC.")

    def links(self, relative, body):
        # Standard inline links and reference definitions; code examples are excluded.
        body = re.sub(r"(`+).*?\1", "", body)
        inline = re.findall(r"\[[^\]\n]*\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)", body)
        definitions = dict(re.findall(r"^\s{0,3}\[([^]\n]+)\]:\s*(<[^>]+>|\S+)", body, re.M))
        for target in inline + list(definitions.values()):
            target = target.strip("<>")
            try:
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc or not target:
                    continue
                path = (self.root / relative).parent / unquote(parsed.path) if parsed.path else self.root / relative
                path = path.resolve()
                if not path.is_relative_to(self.root):
                    self.report("ERROR", relative, "outside-root", f"Link leaves project root: {target}")
                    continue
                if not path.exists():
                    self.report("ERROR", relative, "link", f"Missing target: {target}")
                    continue
                linked = path.relative_to(self.root).as_posix()
                if parsed.fragment and path.suffix.lower() == ".md":
                    if linked not in self.docs:
                        self.report("SKIP", relative, "anchor-scope", f"Anchor target outside selected document scope: {target}")
                    elif unquote(parsed.fragment) not in anchors(self.docs[linked]):
                        self.report("ERROR", relative, "anchor", f"Missing heading/id: {target}")
            except (OSError, ValueError, RuntimeError) as exc:
                self.report("ERROR", relative, "link", f"Cannot inspect {target}: {exc}")

    def openapi(self, relative):
        text = self.read(relative)
        if text is None:
            return
        try:
            import yaml
        except ImportError:
            self.report("SKIP", relative, "yaml-parser", "PyYAML unavailable; YAML and API checks not run. No installation attempted.")
            return

        checked_mappings = set()

        class UniqueKeyLoader(yaml.SafeLoader):
            def flatten_mapping(loader, node):
                # Check explicit keys before YAML merges insert inherited keys.
                if id(node) not in checked_mappings:
                    checked_mappings.add(id(node))
                    seen = set()
                    for key_node, _ in node.value:
                        key = "<<" if key_node.tag == "tag:yaml.org,2002:merge" else loader.construct_object(key_node)
                        try:
                            duplicate = key in seen
                            seen.add(key)
                        except TypeError as exc:
                            raise yaml.constructor.ConstructorError("while constructing a mapping", node.start_mark,
                                                                    "found an unhashable key", key_node.start_mark) from exc
                        if duplicate:
                            raise yaml.constructor.ConstructorError("while constructing a mapping", node.start_mark,
                                                                    f"found duplicate key {key!r}", key_node.start_mark)
                return super().flatten_mapping(node)

        try:
            api = yaml.load(text, Loader=UniqueKeyLoader)
        except (yaml.YAMLError, ValueError, OverflowError) as exc:
            self.report("ERROR", relative, "yaml", str(exc))
            return
        except RecursionError:
            self.report("ERROR", relative, "yaml-depth", "YAML nesting exceeds the parser's supported depth.")
            return
        if not isinstance(api, dict) or not isinstance(api.get("openapi"), str) or not re.fullmatch(r"3\.\d+\.\d+", api["openapi"]):
            self.report("ERROR", relative, "api-header", "Expected an OpenAPI mapping and string version.")
            return
        info = api.get("info")
        if not isinstance(info, dict) or any(not isinstance(info.get(key), str) or not info[key].strip()
                                             for key in ("title", "version")):
            self.report("ERROR", relative, "api-info", "info.title and info.version must be nonempty strings.")
        elif any(re.search(r"\{\{.*?\}\}", info[key]) for key in ("title", "version")):
            self.report("ERROR", relative, "placeholder", "Unfilled API title/version.")
        paths = api.get("paths")
        if not isinstance(paths, dict) or not paths:
            self.report("ERROR", relative, "api-paths", "paths must contain the current HTTP contract.")
            return
        if self.mvp_path not in self.docs:
            self.report("SKIP", relative, "id-check", "Current MVP unavailable; cannot resolve x-requirements.")

        def pointer(ref):
            node = api
            try:
                for part in unquote(ref[2:]).split("/"):
                    key = part.replace("~1", "/").replace("~0", "~")
                    node = node[int(key)] if isinstance(node, list) else node[key]
                return node
            except (KeyError, IndexError, TypeError, ValueError):
                self.report("ERROR", relative, "api-ref", f"Unresolved JSON Pointer: {ref}")
                return None

        named_maps = {"paths", "webhooks", "schemas", "properties", "patternProperties", "$defs", "definitions",
                      "dependentSchemas", "dependencies", "responses", "headers", "parameters", "requestBodies",
                      "callbacks", "links", "securitySchemes", "content", "encoding"}
        literals = {"example", "default", "const", "enum"}
        visited, pending = set(), [(api, "object")]
        while pending:
            node, kind = pending.pop()
            if isinstance(node, (dict, list)):
                identity = (id(node), kind)
                if identity in visited:
                    continue
                visited.add(identity)
            if isinstance(node, dict):
                is_names = kind in {"names", "example-names"}
                ref = node.get("$ref") if not is_names else None
                if isinstance(ref, str):
                    if ref.startswith("#/"):
                        pointer(ref)
                    else:
                        self.report("SKIP", relative, "api-ref-scope", f"External or named-anchor reference not resolved: {ref}")
                for key, value in node.items():
                    if is_names:
                        pending.append((value, "example-object" if kind == "example-names" else "object"))
                    elif key in literals or (kind == "example-object" and key == "value"):
                        continue
                    elif isinstance(key, str) and key.startswith("x-"):
                        continue
                    elif key == "examples":
                        if isinstance(value, dict):
                            pending.append((value, "example-names"))
                    else:
                        pending.append((value, "names" if key in named_maps else "object"))
            elif isinstance(node, list):
                pending.extend((value, "object") for value in node)
        seen, operations, referenced_items = set(), 0, False
        for path, item in paths.items():
            if not isinstance(path, str) or not path.startswith("/") or not isinstance(item, dict):
                self.report("ERROR", relative, "api-path", f"Invalid path item: {path}")
                continue
            if "$ref" in item:
                referenced_items = True
                self.report("SKIP", relative, "api-operation-scope", f"Referenced Path Item not inspected for operations: {path}")
                continue
            for method, operation in item.items():
                if method not in METHODS:
                    continue
                operations += 1
                label = f"{method.upper()} {path}"
                if not isinstance(operation, dict):
                    self.report("ERROR", relative, "api-operation", f"{label}: expected an operation mapping.")
                    continue
                name = operation.get("operationId")
                if not isinstance(name, str) or not name.strip():
                    self.report("ERROR", relative, "operation-id", f"{label}: missing operationId.")
                elif name in seen:
                    self.report("ERROR", relative, "operation-id", f"Duplicate operationId: {name}")
                else:
                    seen.add(name)
                linked = operation.get("x-requirements")
                if not isinstance(linked, list) or not linked or any(not isinstance(x, str) or not ID.fullmatch(x) for x in linked):
                    self.report("ERROR", relative, "api-requirements", f"{label}: x-requirements must be a nonempty REQ/AC ID array.")
                elif self.mvp_path in self.docs:
                    for identifier in sorted(set(linked) - self.ids):
                        self.report("ERROR", relative, "unknown-id", f"{label}: unknown {identifier}.")
        if not operations and not referenced_items:
            self.report("ERROR", relative, "api-operations", "No HTTP operations found in paths.")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", type=Path, help="Target project, not the skill/template directory")
    parser.add_argument("--include-product", action="store_true", help="Also read docs/product (planning/MVP scope work only)")
    parser.add_argument("--mvp", help="Explicit docs/v<version>/MVP.md target; otherwise use the current MVP entry in AGENTS.md")
    parser.add_argument("--require-implementation", action="store_true", help="Require core handoff documents and agreement with AGENTS.md's current MVP")
    args = parser.parse_args()
    try:
        validator = Validator(args.project_root, args.include_product, args.require_implementation, args.mvp)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR . [root] Cannot resolve project root: {exc}")
        return 1
    issues = validator.run()
    for level, path, code, message in issues:
        print(f"{level} {path} [{code}] {message}")
    errors = sum(item[0] == "ERROR" for item in issues)
    skipped = sum(item[0] == "SKIP" for item in issues)
    print(f"Checked {len(validator.docs)} Markdown files; errors={errors}, skipped={skipped}.")
    print("NOT CHECKED: business meaning, duplicate prose, Ready approval, full OpenAPI schema, application behavior.")
    return 1 if errors else 2 if skipped else 0


if __name__ == "__main__":
    raise SystemExit(main())
