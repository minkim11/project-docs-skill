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
        self.write("docs/implementation/MVP.md", MVP)
        self.write("docs/implementation/ARCHITECTURE.md", "# Architecture\n\n적용 MVP: 0.1\n\nREQ-001\n")
        self.write("docs/implementation/CONVENTIONS.md", "# Conventions\n\n적용 MVP: 0.1\n")
        self.write("AGENTS.md", "[MVP](docs/implementation/MVP.md#완료-기준)\n")

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
        self.write("docs/implementation/MVP.md", MVP + "\n### REQ-001 — Duplicate\n### REQ-002 — Uncovered\nREQ-999\n")
        self.assertTrue({"duplicate-id", "req-coverage", "unknown-id"} <= self.codes())

    def test_empty_acceptance_condition(self):
        self.write("docs/implementation/MVP.md", MVP.replace("Saving text returns the saved note.", ""))
        self.assertIn("ac-condition", self.codes())

    def test_retired_ids_in_change_summary_are_historical(self):
        self.write("docs/implementation/MVP.md", MVP.replace("- 상태: Draft", "- 상태: Draft\n- 변경 요약: REQ-099 was replaced by REQ-001."))
        self.assertEqual([], self.issues())

    def test_versions_links_and_placeholders(self):
        self.write("docs/implementation/ARCHITECTURE.md", "적용 MVP: 0.2\n{{미정 양식}}\n[Missing](gone.md)\n")
        self.assertTrue({"mvp-version", "placeholder", "link"} <= self.codes())

    def test_anchor_and_reference_definition(self):
        self.write("AGENTS.md", "[MVP][spec]\n[spec]: docs/implementation/MVP.md#missing\n")
        self.assertIn("anchor", self.codes())

    def test_examples_are_not_active_links_or_requirements(self):
        self.write("AGENTS.md", "```md\nREQ-999 {{example}} [gone](missing.md)\n```\n`[gone](missing.md)`\n")
        self.assertEqual([], self.issues())

    def test_prd_not_read_without_explicit_option_even_via_link(self):
        self.write("docs/product/PRD.md", "# Product\n{{unfinished}}\n")
        self.write("AGENTS.md", "[Product](docs/product/PRD.md#product)\n")
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
        (self.root / "docs/implementation/MVP.md").unlink()
        self.assertTrue(any(item[:3] == ("SKIP", "docs/implementation/MVP.md", "id-check") for item in self.issues()))

    def test_link_outside_root_not_opened(self):
        self.write("AGENTS.md", "[outside](../secret.md#heading)\n")
        self.assertIn("outside-root", self.codes())

    def test_invalid_link_does_not_abort_other_links_or_documents(self):
        self.write("AGENTS.md", "[invalid](bad%00path.md)\n[missing](gone.md)\n")
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

    def test_cli_reports_unicode_errors_under_ascii_output(self):
        self.write("AGENTS.md", "[missing](missing-🌱.md)\n")
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
    def test_deep_yaml_returns_error_without_traceback(self):
        self.write("docs/implementation/openapi.yaml", "value: " + "[" * 1200 + "0" + "]" * 1200)
        self.assertIn("yaml-depth", self.codes())
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), str(self.root)], capture_output=True)
        self.assertEqual(1, result.returncode)
        self.assertIn(b"[yaml-depth]", result.stdout)
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
        self.write("AGENTS.md", "[old](docs/product/PRD.md#old)\n")
        self.write("docs/product/PRD.md", "# Old\n")
        self.assertEqual(2, run().returncode)


if __name__ == "__main__":
    unittest.main()
