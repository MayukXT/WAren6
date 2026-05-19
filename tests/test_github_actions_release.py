import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


class GitHubActionsReleaseTests(unittest.TestCase):
    def test_reader_ci_is_scoped_to_reader_changes(self):
        workflow = WORKFLOWS / "reader-ci.yml"
        self.assertTrue(workflow.exists(), "reader CI workflow should exist")
        source = workflow.read_text(encoding="utf-8")

        self.assertIn("name: Reader CI", source)
        self.assertIn("pull_request:", source)
        self.assertIn("paths:", source)
        self.assertIn("waren6-reader/**", source)
        self.assertIn(".github/workflows/reader-release.yml", source)
        self.assertNotIn("waren6.py", source)
        self.assertNotIn("airgap/**", source)
        self.assertIn("npm ci", source)
        self.assertIn("npm test", source)
        self.assertIn("cargo test", source)

    def test_combined_public_release_workflow_is_removed(self):
        self.assertFalse((WORKFLOWS / "public-release.yml").exists())

    def test_reader_release_workflow_builds_only_reader_assets(self):
        workflow = WORKFLOWS / "reader-release.yml"
        self.assertTrue(workflow.exists(), "reader release workflow should exist")
        source = workflow.read_text(encoding="utf-8")

        self.assertIn("name: Reader Release", source)
        self.assertIn("reader-v*", source)
        self.assertIn("release_tag=reader-v$version", source)
        self.assertIn("WAren6 Reader v$version", source)
        self.assertIn("WAren6-Reader-Setup-v$version.exe", source)
        self.assertIn("WAren6-Reader-v$version-x64.msi", source)
        self.assertIn("WAren6-Reader-Portable-v$version.exe", source)
        self.assertIn("WAren6-Reader-latest.json", source)
        self.assertIn("latest.json", source)
        self.assertIn("reader-latest", source)
        self.assertIn("npm run check:release-version -- --tag ${{ steps.versions.outputs.release_tag }}", source)
        self.assertIn("npm run tauri -- build", source)
        self.assertIn("cargo install cargo-audit --locked", source)
        self.assertIn("cargo audit", source)
        self.assertIn("TAURI_SIGNING_PRIVATE_KEY", source)
        self.assertIn("TAURI_SIGNING_PRIVATE_KEY_PASSWORD", source)
        self.assertIn("gh release create $tag", source)
        self.assertNotIn("WAren6-FieldKit", source)
        self.assertNotIn("build-airgap-package", source)
        self.assertNotIn("wheels-cache", source)

    def test_fieldkit_release_workflow_builds_only_fieldkit_assets(self):
        workflow = WORKFLOWS / "field-kit-release.yml"
        self.assertTrue(workflow.exists(), "field kit release workflow should exist")
        source = workflow.read_text(encoding="utf-8")

        self.assertIn("name: Field Kit Release", source)
        self.assertIn("fieldkit-v*", source)
        self.assertIn("fieldkit-version.json", source)
        self.assertIn("release_tag=fieldkit-v$version", source)
        self.assertIn("WAren6 Field Kit v$version", source)
        self.assertIn("WAren6-FieldKit-v$version.zip", source)
        self.assertIn("WAren6-FieldKit-v$version.sha256.txt", source)
        self.assertIn("python -m unittest discover -s tests -p 'test*.py'", source)
        self.assertIn("uses: actions/cache@v4", source)
        self.assertIn("id: wheels-cache", source)
        self.assertIn("path: wheels", source)
        self.assertIn("build-airgap-package.ps1", source)
        self.assertIn("gh release create $tag", source)
        self.assertNotIn("npm run tauri -- build", source)
        self.assertNotIn("TAURI_SIGNING_PRIVATE_KEY", source)
        self.assertNotIn("cargo audit", source)
        self.assertNotIn("WAren6-Reader", source)

    def test_reader_workflows_share_rust_cache_key(self):
        reader_release = (WORKFLOWS / "reader-release.yml").read_text(encoding="utf-8")
        reader_ci = (WORKFLOWS / "reader-ci.yml").read_text(encoding="utf-8")

        for source in (reader_release, reader_ci):
            self.assertIn("uses: swatinem/rust-cache@v2", source)
            self.assertIn("shared-key: windows-tauri-reader", source)

    def test_versions_are_independent(self):
        release_index = json.loads((ROOT / "version.json").read_text(encoding="utf-8"))
        fieldkit_json = json.loads((ROOT / "fieldkit-version.json").read_text(encoding="utf-8"))
        package_json = json.loads((ROOT / "waren6-reader" / "package.json").read_text(encoding="utf-8"))
        tauri_json = json.loads((ROOT / "waren6-reader" / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
        cargo_toml = (ROOT / "waren6-reader" / "src-tauri" / "Cargo.toml").read_text(encoding="utf-8")
        cargo_match = re.search(r'^version\s*=\s*"([^"]+)"', cargo_toml, re.MULTILINE)

        self.assertIsNotNone(cargo_match)
        self.assertEqual(fieldkit_json["latest_version"], "1.1.0")
        self.assertEqual(fieldkit_json["tag"], "fieldkit-v1.1.0")
        self.assertEqual(release_index["field_kit"]["latest_version"], "1.1.0")
        self.assertEqual(release_index["reader"]["latest_version"], "1.7.0")
        self.assertEqual(package_json["version"], "1.7.0")
        self.assertEqual(tauri_json["version"], "1.7.0")
        self.assertEqual(cargo_match.group(1), "1.7.0")

    def test_reader_updater_configuration_uses_reader_latest_metadata(self):
        tauri_json = json.loads((ROOT / "waren6-reader" / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
        cargo_toml = (ROOT / "waren6-reader" / "src-tauri" / "Cargo.toml").read_text(encoding="utf-8")
        capabilities = json.loads((ROOT / "waren6-reader" / "src-tauri" / "capabilities" / "default.json").read_text(encoding="utf-8"))

        self.assertTrue(tauri_json["bundle"]["createUpdaterArtifacts"])
        self.assertEqual(
            tauri_json["plugins"]["updater"]["endpoints"],
            ["https://raw.githubusercontent.com/MayukXT/WAren6/reader-latest/latest.json"],
        )
        self.assertEqual(tauri_json["plugins"]["updater"]["windows"]["installMode"], "basicUi")
        self.assertIn("tauri-plugin-updater", cargo_toml)
        self.assertIn("tauri-plugin-process", cargo_toml)
        self.assertIn("updater:default", capabilities["permissions"])
        self.assertIn("process:allow-restart", capabilities["permissions"])
        self.assertIsInstance(tauri_json["app"]["security"]["csp"], str)
        self.assertIn("https://raw.githubusercontent.com", tauri_json["app"]["security"]["csp"])

    def test_reader_tauri_dialog_plugins_share_major_minor_version(self):
        package_lock = json.loads((ROOT / "waren6-reader" / "package-lock.json").read_text(encoding="utf-8"))
        npm_version = package_lock["packages"]["node_modules/@tauri-apps/plugin-dialog"]["version"]

        cargo_lock = (ROOT / "waren6-reader" / "src-tauri" / "Cargo.lock").read_text(encoding="utf-8")
        match = re.search(r'name = "tauri-plugin-dialog"\s+version = "([^"]+)"', cargo_lock)
        self.assertIsNotNone(match, "Cargo.lock should include tauri-plugin-dialog")
        cargo_version = match.group(1)

        self.assertEqual(npm_version.split(".")[:2], cargo_version.split(".")[:2])

    def test_release_docs_explain_separate_tag_cutting(self):
        reader_readme = (ROOT / "waren6-reader" / "README.md").read_text(encoding="utf-8")
        root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
        knowledge = (ROOT / "LLM.txt").read_text(encoding="utf-8")
        airgap_readme = (ROOT / "airgap" / "README.md").read_text(encoding="utf-8")
        requirements = (ROOT / "requirements-lock.txt").read_text(encoding="utf-8")

        self.assertIn("WAren6 Reader v1.7.0", reader_readme)
        self.assertIn("reader-v1.7.0", reader_readme)
        self.assertIn("fieldkit-v1.1.0", root_readme)
        self.assertIn("WAren6-FieldKit-v1.1.0.zip", root_readme)
        self.assertIn("WAren6 Reader v1.7.0", root_readme)
        self.assertIn("Reader Release", root_readme)
        self.assertIn("Field Kit Release", root_readme)
        self.assertIn("Reader installer", root_readme)
        self.assertIn("portable EXE", root_readme)
        self.assertIn("## Main Features", root_readme)
        self.assertIn("not only a decrypt script", root_readme)
        self.assertIn("Telegram bot transfer mode", root_readme)
        self.assertIn("-enc", root_readme)
        self.assertIn("-ad", root_readme)
        self.assertIn("offline and air-gapped work", root_readme)
        self.assertIn("WAren6_unify_later.txt", root_readme)
        self.assertIn("Run Terminal/PowerShell as Administrator", root_readme)
        self.assertIn(".\\waren6.ps1 -r -c <folder>", root_readme)
        self.assertIn(".\\airgap\\install-offline-deps.ps1", root_readme)
        self.assertIn("cryptography", requirements)
        self.assertIn("WAren6-FieldKit-v1.1.0.zip", knowledge)
        self.assertIn("WAren6 Reader v1.7.0", knowledge)
        self.assertIn("WAren6-Reader-latest.json", knowledge)
        self.assertIn("Run Terminal/PowerShell as Administrator", knowledge)
        self.assertIn("Run Terminal/PowerShell as Administrator", airgap_readme)
        self.assertNotIn("same release titled `WAren6 v1.7.0`", knowledge)


if __name__ == "__main__":
    unittest.main()
