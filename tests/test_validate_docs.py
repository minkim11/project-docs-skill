"""Run with: python -m unittest discover -s tests -v (no application required)."""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/validate_docs.py"
spec = importlib.util.spec_from_file_location("validate_docs", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

MVP = """# Notes — MVP 0.1

- 버전: 0.1
- 상태: Draft

## 구현 범위와 업무 규칙
### REQ-001 — Create a note
Save the user's text.

## 완료 기준
| ID | 요구사항 | 검증 가능한 조건 |
|---|---|---|
| AC-001 | REQ-001 | Saving text returns the saved note. |
"""

CURRENT = "- 현재 MVP: [MVP](docs/v0.1/MVP.md)\n"

API = """openapi: 3.1.0
info: {title: Notes, version: '1.0'}
paths:
  /notes:
    post:
      operationId: createNote
      x-requirements: [REQ-001, AC-001]
      responses:
        '201':
          description: Created
          content:
            application/json:
              schema: {$ref: '#/components/schemas/Note'}
components:
  schemas:
    Note: {type: object}
"""


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.write("docs/v0.1/MVP.md", MVP)
        self.write("docs/implementation/ARCHITECTURE.md", "# Architecture\n\n적용 MVP: 0.1\n\nREQ-001\n")
        self.write("docs/implementation/CONVENTIONS.md", "# Conventions\n\n적용 MVP: 0.1\n")
        self.write("AGENTS.md", CURRENT + "[Criteria](docs/v0.1/MVP.md#완료-기준)\n")

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def issues(self, **options):
        return module.Validator(self.root, **options).run()

    def codes(self, **options):
        return {item[2] for item in self.issues(**options)}

    def test_valid_handoff_and_no_writes(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual([], self.issues(require_implementation=True))
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_id_duplicates_dangling_refs_and_coverage(self):
        self.write("docs/v0.1/MVP.md", MVP + "\n### REQ-001 — Duplicate\n### REQ-002 — Uncovered\nREQ-999\n")
        self.assertTrue({"duplicate-id", "req-coverage", "unknown-id"} <= self.codes())

    def test_empty_acceptance_condition(self):
        self.write("docs/v0.1/MVP.md", MVP.replace("Saving text returns the saved note.", ""))
        self.assertIn("ac-condition", self.codes())

    def test_retired_ids_in_change_summary_are_historical(self):
        self.write("docs/v0.1/MVP.md", MVP.replace("- 상태: Draft", "- 상태: Draft\n- 변경 요약: REQ-099 was replaced by REQ-001."))
        self.assertEqual([], self.issues())

    def test_versions_links_and_placeholders(self):
        self.write("docs/implementation/ARCHITECTURE.md", "적용 MVP: 0.2\n{{미정 양식}}\n[Missing](gone.md)\n")
        self.assertTrue({"mvp-version", "placeholder", "link"} <= self.codes())

    def test_anchor_and_reference_definition(self):
        self.write("AGENTS.md", CURRENT + "[MVP][spec]\n[spec]: docs/v0.1/MVP.md#missing\n")
        self.assertIn("anchor", self.codes())

    def test_examples_are_not_active_links_or_requirements(self):
        self.write("AGENTS.md", CURRENT + "```md\nREQ-999 {{example}} [gone](missing.md)\n```\n`[gone](missing.md)`\n")
        self.assertEqual([], self.issues())

    def test_prd_not_read_without_explicit_option_even_via_link(self):
        self.write("docs/product/PRD.md", "# Product\n{{unfinished}}\n")
        self.write("AGENTS.md", CURRENT + "[Product](docs/product/PRD.md#product)\n")
        original = module.Validator.read
        with patch.object(module.Validator, "read", autospec=True, side_effect=original) as read:
            self.assertEqual({"anchor-scope"}, self.codes())
            self.assertNotIn("docs/product/PRD.md", [call.args[1] for call in read.call_args_list])
        self.assertIn("placeholder", self.codes(include_product=True))

    def test_missing_core_document_only_required_on_handoff(self):
        (self.root / "docs/implementation/CONVENTIONS.md").unlink()
        self.assertEqual([], self.issues())
        self.assertIn("required-file", self.codes(require_implementation=True))

    def test_missing_mvp_is_unverified_not_a_success(self):
        (self.root / "docs/v0.1/MVP.md").unlink()
        self.assertTrue(any(item[:3] == ("SKIP", "docs/v0.1/MVP.md", "id-check") for item in self.issues()))

    def test_other_versions_are_not_read_even_with_product_scope(self):
        self.write("docs/v0.0/MVP.md", MVP + "\n{{historical unfinished template}}\n")
        self.write("docs/v0.2/MVP.md", "{{future draft}} REQ-999\n")
        self.write("docs/product/PRD.md", "# Product\n")
        original = module.Validator.read
        for include_product in (False, True):
            with self.subTest(include_product=include_product):
                with patch.object(module.Validator, "read", autospec=True, side_effect=original) as read:
                    self.assertEqual([], self.issues(include_product=include_product))
                    read_paths = [call.args[1] for call in read.call_args_list]
                    self.assertNotIn("docs/v0.0/MVP.md", read_paths)
                    self.assertNotIn("docs/v0.2/MVP.md", read_paths)

    def test_explicit_mvp_overrides_current_without_reading_it(self):
        self.write("AGENTS.md", CURRENT)
        self.write("docs/v0.2/MVP.md", MVP.replace("0.1", "0.2").replace("REQ-001", "REQ-002").replace("AC-001", "AC-002"))
        self.write("docs/implementation/ARCHITECTURE.md", "적용 MVP: 0.2\nREQ-002\n")
        self.write("docs/implementation/CONVENTIONS.md", "적용 MVP: 0.2\n")
        self.write("docs/implementation/openapi.yaml", API.replace("REQ-001", "REQ-002").replace("AC-001", "AC-002"))
        original = module.Validator.read
        with patch.object(module.Validator, "read", autospec=True, side_effect=original) as read:
            issues = self.issues(mvp_path="docs/v0.2/MVP.md")
        if importlib.util.find_spec("yaml"):
            self.assertEqual([], issues)
        else:
            self.assertEqual({"yaml-parser"}, {item[2] for item in issues})
        self.assertNotIn("docs/v0.1/MVP.md", [call.args[1] for call in read.call_args_list])
        (self.root / "docs/implementation/openapi.yaml").unlink()
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), str(self.root), "--mvp", "docs/v0.2/MVP.md"], capture_output=True)
        self.assertEqual(0, result.returncode)

    def test_missing_pointer_never_selects_the_latest_folder(self):
        self.write("AGENTS.md", "# Instructions\n")
        self.write("docs/v99.0/MVP.md", MVP)
        validator = module.Validator(self.root)
        self.assertIn("mvp-selection", {item[2] for item in validator.run()})
        self.assertIsNone(validator.mvp_path)
        self.assertNotIn("docs/v99.0/MVP.md", validator.docs)
        self.assertTrue(any(item[0] == "ERROR" and item[2] == "mvp-selection" for item in self.issues(require_implementation=True)))

    def test_handoff_override_must_agree_with_current_mvp(self):
        self.write("AGENTS.md", CURRENT)
        self.write("docs/v0.2/MVP.md", MVP.replace("0.1", "0.2"))
        self.write("docs/implementation/ARCHITECTURE.md", "적용 MVP: 0.2\nREQ-001\n")
        self.write("docs/implementation/CONVENTIONS.md", "적용 MVP: 0.2\n")
        self.assertEqual([], self.issues(mvp_path="docs/v0.2/MVP.md"))
        self.assertIn("mvp-handoff", self.codes(mvp_path="docs/v0.2/MVP.md", require_implementation=True))
        self.write("AGENTS.md", CURRENT.replace("v0.1", "v0.2"))
        self.assertEqual([], self.issues(mvp_path="docs/v0.2/MVP.md", require_implementation=True))

    def test_handoff_override_does_not_bypass_missing_or_ambiguous_entry(self):
        for content in ("# Instructions\n", CURRENT + CURRENT, CURRENT.replace("docs/v0.1/MVP.md", "docs/product/PRD.md")):
            with self.subTest(content=content):
                self.write("AGENTS.md", content)
                self.assertIn("mvp-selection", self.codes(mvp_path="docs/v0.1/MVP.md", require_implementation=True))

    def test_ambiguous_pointer_is_an_error(self):
        self.write("AGENTS.md", CURRENT + CURRENT)
        self.assertIn("mvp-selection", self.codes())

    def test_invalid_mvp_targets_cannot_open_product_or_other_paths(self):
        self.write("docs/product/PRD.md", "# Private planning document\n")
        original = module.Validator.read
        for target in ("docs/product/PRD.md", "../PRD.md", "docs/v0.1/../product/PRD.md", "docs/v0.1/MVP.md#heading"):
            with self.subTest(target=target):
                with patch.object(module.Validator, "read", autospec=True, side_effect=original) as read:
                    self.assertIn("mvp-selection", self.codes(mvp_path=target))
                    self.assertNotIn("docs/product/PRD.md", [call.args[1] for call in read.call_args_list])

    def test_mvp_version_must_match_its_folder(self):
        self.write("docs/v0.1/MVP.md", MVP.replace("0.1", "0.2"))
        self.assertIn("mvp-folder-version", self.codes())

    def test_versioned_mvp_can_link_to_shared_contract(self):
        self.write("docs/v0.1/MVP.md", MVP + "\n[Architecture](../implementation/ARCHITECTURE.md#architecture)\n")
        self.assertEqual([], self.issues())

    def test_legacy_layout_is_reported_without_reading_legacy_mvp(self):
        self.write("docs/implementation/MVP.md", "{{legacy document}}\n")
        original = module.Validator.read
        with patch.object(module.Validator, "read", autospec=True, side_effect=original) as read:
            self.assertIn("legacy-mvp", self.codes())
        self.assertNotIn("docs/implementation/MVP.md", [call.args[1] for call in read.call_args_list])

    def test_link_outside_root_not_opened(self):
        self.write("AGENTS.md", CURRENT + "[outside](../secret.md#heading)\n")
        self.assertIn("outside-root", self.codes())

    def test_invalid_link_does_not_abort_other_links_or_documents(self):
        self.write("AGENTS.md", CURRENT + "[invalid](bad%00path.md)\n[missing](gone.md)\n")
        self.write("docs/implementation/CONVENTIONS.md", "적용 MVP: 0.2\n")
        issues = self.issues()
        self.assertEqual(2, sum(issue[2] == "link" for issue in issues))
        self.assertIn("mvp-version", {issue[2] for issue in issues})

    def test_unreadable_file_does_not_abort_other_documents(self):
        original = module.Path.read_text

        def read(path, *args, **kwargs):
            if path.name == "ARCHITECTURE.md":
                raise PermissionError("Test permission denied")
            return original(path, *args, **kwargs)

        self.write("docs/implementation/CONVENTIONS.md", "적용 MVP: 0.2\n")
        with patch.object(module.Path, "read_text", read):
            self.assertTrue({"read", "mvp-version"} <= self.codes())

    def test_inaccessible_root_returns_a_reported_error(self):
        validator = module.Validator(self.root)
        with patch.object(module.Path, "is_dir", side_effect=PermissionError("Test permission denied")):
            issues = validator.run()
        self.assertEqual(("ERROR", ".", "root"), issues[0][:3])

    def test_unresolvable_file_path_is_reported(self):
        validator = module.Validator(self.root)
        with patch.object(module.Path, "resolve", side_effect=RuntimeError("Symlink loop")):
            self.assertIsNone(validator.read("AGENTS.md"))
        self.assertEqual("read", validator.issues[0][2])

    def test_unreadable_directory_does_not_abort_other_directories(self):
        original = module.os.walk

        def walk(path, onerror):
            if path.name == "implementation":
                onerror(PermissionError(13, "Test permission denied", str(path)))
                return iter(())
            return original(path, onerror=onerror)

        self.write("docs/decisions/0001-storage.md", "# Storage\n{{unfilled}}\n")
        with patch.object(module.os, "walk", side_effect=walk):
            self.assertTrue({"scan", "placeholder"} <= self.codes())

    def test_scan_error_without_filename_does_not_abort_other_directories(self):
        original = module.os.walk

        def walk(path, onerror):
            if path.name == "implementation":
                onerror(FileNotFoundError("Directory disappeared without a filename"))
                return iter(())
            return original(path, onerror=onerror)

        self.write("docs/decisions/0001-storage.md", "{{unfilled}}\n")
        with patch.object(module.os, "walk", side_effect=walk):
            self.assertTrue({"scan", "placeholder"} <= self.codes())

    def test_scan_iterator_failure_does_not_abort_other_directories(self):
        original = module.os.walk

        def walk(path, onerror):
            if path.name == "implementation":
                yield str(path), [], ["ARCHITECTURE.md"]
                raise failure("Scanning interrupted")
            yield from original(path, onerror=onerror)

        self.write("docs/decisions/0001-storage.md", "{{unfilled}}\n")
        for failure in (OSError, RecursionError):
            with self.subTest(failure=failure.__name__):
                with patch.object(module.os, "walk", side_effect=walk):
                    self.assertTrue({"scan", "placeholder"} <= self.codes())

    def test_cli_reports_unicode_errors_under_ascii_output(self):
        self.write("AGENTS.md", CURRENT + "[missing](missing-🌱.md)\n")
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), str(self.root)],
                                capture_output=True, env={**os.environ, "PYTHONIOENCODING": "ascii"})
        self.assertEqual(1, result.returncode)
        self.assertIn(b"[link]", result.stdout)
        self.assertNotIn(b"Traceback", result.stderr)

    def test_resolved_document_cannot_bypass_read_scope(self):
        self.write("docs/product/PRD.md", "# Product\n")
        with patch.object(module.Path, "resolve", return_value=self.root / "docs/product/PRD.md"):
            validator = module.Validator.__new__(module.Validator)
            validator.root, validator.include_product, validator.issues = self.root, False, []
            validator.mvp_path = None
            self.assertIsNone(validator.read("AGENTS.md"))
            self.assertEqual("read-scope", validator.issues[0][2])

    def test_no_yaml_dependency_is_reported(self):
        self.write("docs/implementation/openapi.yaml", API)
        with patch.dict(sys.modules, {"yaml": None}):
            self.assertTrue(any(item[0] == "SKIP" and item[2] == "yaml-parser" for item in self.issues()))

    @unittest.skipUnless(importlib.util.find_spec("yaml"), "PyYAML not installed")
    def test_api_valid_and_invalid_contract_links(self):
        self.write("docs/implementation/openapi.yaml", API)
        self.assertEqual([], self.issues())
        self.write("docs/implementation/openapi.yaml", API.replace("REQ-001", "REQ-999").replace("schemas/Note", "schemas/Missing"))
        self.assertTrue({"unknown-id", "api-ref"} <= self.codes())

    @unittest.skipUnless(importlib.util.find_spec("yaml"), "PyYAML not installed")
    def test_api_ref_requires_canonical_array_index(self):
        contract = API.replace("Note: {type: object}", "Note: {allOf: [{type: object}]}")
        for index in ("0", "-1", "00", "+0", "1"):
            with self.subTest(index=index):
                self.write("docs/implementation/openapi.yaml",
                           contract.replace("schemas/Note'", f"schemas/Note/allOf/{index}'"))
                self.assertEqual(set() if index == "0" else {"api-ref"}, self.codes())

    @unittest.skipUnless(importlib.util.find_spec("yaml"), "PyYAML not installed")
    def test_paths_extensions_are_metadata(self):
        self.write("docs/implementation/openapi.yaml",
                   API.replace("paths:\n", "paths:\n  x-note: {$ref: 'opaque-data'}\n"))
        self.assertEqual([], self.issues())

    @unittest.skipUnless(importlib.util.find_spec("yaml"), "PyYAML not installed")
    def test_external_ref_violates_single_file_contract(self):
        for ref in ("", "#"):
            with self.subTest(ref=ref):
                self.write("docs/implementation/openapi.yaml", API.replace("#/components/schemas/Note", ref))
                self.assertEqual([], self.issues())
        for ref in ("parts.yaml#/Note", "https://example.com/parts.yaml#/Note"):
            with self.subTest(ref=ref):
                self.write("docs/implementation/openapi.yaml", API.replace("#/components/schemas/Note", ref))
                self.assertEqual([("ERROR", "api-single-file")],
                                 [(level, code) for level, _, code, _ in self.issues()])

    @unittest.skipUnless(importlib.util.find_spec("yaml"), "PyYAML not installed")
    def test_additional_openapi_files_are_rejected_and_examples_are_allowed(self):
        self.write("docs/implementation/openapi.yaml", API)
        self.write("docs/implementation/examples/note.yaml", "note: example\n")
        self.write("docs/implementation/examples/input.json", '{"openapi": "payload text"}')
        self.assertEqual([], self.issues())
        yaml_path = "docs/implementation/parts/notes.yml"
        json_path = "docs/implementation/another.json"
        self.write(yaml_path, API)
        self.write(json_path, '{"openapi": "3.1.0", "paths": {}}')
        for canonical_exists in (True, False):
            with self.subTest(canonical_exists=canonical_exists):
                if not canonical_exists:
                    (self.root / "docs/implementation/openapi.yaml").unlink()
                self.assertEqual({("ERROR", yaml_path, "api-single-file"), ("ERROR", json_path, "api-single-file")},
                                 {(level, path, code) for level, path, code, _ in self.issues()})

    @unittest.skipUnless(importlib.util.find_spec("yaml"), "PyYAML not installed")
    def test_deep_yaml_returns_error_without_traceback(self):
        self.write("docs/implementation/openapi.yaml", "value: " + "[" * 1200 + "0" + "]" * 1200)
        self.assertIn("yaml-depth", self.codes())
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), str(self.root)], capture_output=True)
        self.assertEqual(1, result.returncode)
        self.assertIn(b"[yaml-depth]", result.stdout)
        self.assertNotIn(b"Traceback", result.stderr)

    @unittest.skipUnless(importlib.util.find_spec("yaml"), "PyYAML not installed")
    def test_duplicate_yaml_keys_are_errors(self):
        duplicate_path = API.replace("paths:\n", "paths:\n  /notes:\n    get:\n      operationId: lostGet\n      x-requirements: [REQ-999]\n")
        duplicate_schema = API.replace("Note: {type: object}", "Note: {type: object, type: string}")
        duplicate_info = API.replace("title: Notes", "title: First, title: Notes")
        for contract in (duplicate_path, duplicate_schema, duplicate_info):
            with self.subTest(contract=contract):
                self.write("docs/implementation/openapi.yaml", contract)
                self.assertIn("yaml", self.codes())

    @unittest.skipUnless(importlib.util.find_spec("yaml"), "PyYAML not installed")
    def test_yaml_merge_override_is_allowed_but_duplicate_base_keys_are_not(self):
        contract = API.replace("info: {title: Notes, version: '1.0'}",
                               "x-info-defaults: &base {title: Base, version: '1.0'}\ninfo:\n  <<: *base\n  title: Notes")
        self.write("docs/implementation/openapi.yaml", contract)
        self.assertEqual([], self.issues())
        self.write("docs/implementation/openapi.yaml", contract.replace("title: Base", "title: First, title: Base"))
        self.assertIn("yaml", self.codes())

    @unittest.skipUnless(importlib.util.find_spec("yaml"), "PyYAML not installed")
    def test_schema_names_and_properties_do_not_hide_refs(self):
        import yaml
        for name in ("example", "examples", "default", "const", "enum"):
            for as_property in (False, True):
                with self.subTest(name=name, as_property=as_property):
                    api = yaml.safe_load(API)
                    missing = {"$ref": "#/components/schemas/Missing"}
                    if as_property:
                        api["components"]["schemas"]["Note"]["properties"] = {name: missing}
                    else:
                        api["components"]["schemas"][name] = missing
                    self.write("docs/implementation/openapi.yaml", yaml.safe_dump(api))
                    self.assertIn("api-ref", self.codes())

    @unittest.skipUnless(importlib.util.find_spec("yaml"), "PyYAML not installed")
    def test_literal_example_and_schema_annotation_data_are_not_refs(self):
        import yaml
        api = yaml.safe_load(API)
        literal = {"$ref": "#/not-a-contract-reference"}
        media = api["paths"]["/notes"]["post"]["responses"]["201"]["content"]["application/json"]
        media["example"] = literal
        media["examples"] = {"payload": {"value": literal}}
        schema = api["components"]["schemas"]["Note"]
        schema.update({"default": literal, "const": literal, "enum": [literal], "examples": [literal]})
        api["x-custom-data"] = literal
        self.write("docs/implementation/openapi.yaml", yaml.safe_dump(api))
        self.assertEqual([], self.issues())

    @unittest.skipUnless(importlib.util.find_spec("yaml"), "PyYAML not installed")
    def test_example_object_reference_is_checked(self):
        import yaml
        api = yaml.safe_load(API)
        media = api["paths"]["/notes"]["post"]["responses"]["201"]["content"]["application/json"]
        media["examples"] = {"payload": {"$ref": "#/components/examples/Missing"}}
        self.write("docs/implementation/openapi.yaml", yaml.safe_dump(api))
        self.assertIn("api-ref", self.codes())

    @unittest.skipUnless(importlib.util.find_spec("yaml"), "PyYAML not installed")
    def test_yaml_scalar_conversion_errors_are_reported_without_traceback(self):
        self.write("docs/implementation/openapi.yaml", API + "\nx-release-date: 2026-02-30\n")
        self.write("docs/implementation/CONVENTIONS.md", "적용 MVP: 0.2\n")
        self.assertTrue({"yaml", "mvp-version"} <= self.codes())
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), str(self.root)], capture_output=True)
        self.assertEqual(1, result.returncode)
        self.assertIn(b"[yaml]", result.stdout)
        self.assertNotIn(b"Traceback", result.stderr)

    @unittest.skipUnless(importlib.util.find_spec("yaml"), "PyYAML not installed")
    def test_unhashable_yaml_key_is_reported_without_type_error(self):
        self.write("docs/implementation/openapi.yaml", API + "\n? [a, b]\n: invalid-key\n")
        self.assertIn("yaml", self.codes())

    @unittest.skipUnless(importlib.util.find_spec("yaml"), "PyYAML not installed")
    def test_recursive_yaml_alias_does_not_loop_during_ref_traversal(self):
        contract = API.replace("Note: {type: object}", "Note: &note\n      type: object\n      properties:\n        child: *note")
        self.write("docs/implementation/openapi.yaml", contract)
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), str(self.root)], capture_output=True, timeout=10)
        self.assertIn(b"Checked", result.stdout)
        self.assertNotIn(b"Traceback", result.stderr)

    @unittest.skipUnless(importlib.util.find_spec("yaml"), "PyYAML not installed")
    def test_api_syntax_empty_paths_and_duplicate_operations(self):
        self.write("docs/implementation/openapi.yaml", "paths: [")
        self.assertIn("yaml", self.codes())
        self.write("docs/implementation/openapi.yaml", "openapi: 3.1.0\ninfo: {title: Notes, version: '1'}\npaths: {}\n")
        self.assertIn("api-paths", self.codes())
        import yaml
        api = yaml.safe_load(API)
        api["paths"]["/other"] = api["paths"]["/notes"]
        self.write("docs/implementation/openapi.yaml", yaml.safe_dump(api))
        self.assertIn("operation-id", self.codes())

    def test_cli_exit_codes(self):
        def run(*extra):
            return subprocess.run([sys.executable, "-B", str(SCRIPT), str(self.root), *extra], capture_output=True)
        self.assertEqual(0, run("--require-implementation").returncode)
        (self.root / "AGENTS.md").unlink()
        self.assertEqual(1, run("--require-implementation").returncode)
        self.write("AGENTS.md", CURRENT + "[old](docs/product/PRD.md#old)\n")
        self.write("docs/product/PRD.md", "# Old\n")
        self.assertEqual(2, run().returncode)


if __name__ == "__main__":
    unittest.main()
