import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";

const scriptPath = path.resolve("scripts/check-release-version.mjs");

function writeFixture(version) {
  const root = mkdtempSync(path.join(tmpdir(), "waren6-reader-version-"));
  mkdirSync(path.join(root, "src-tauri"), { recursive: true });
  writeFileSync(
    path.join(root, "package.json"),
    JSON.stringify({ version }, null, 2),
  );
  writeFileSync(
    path.join(root, "src-tauri", "tauri.conf.json"),
    JSON.stringify({ version }, null, 2),
  );
  writeFileSync(
    path.join(root, "src-tauri", "Cargo.toml"),
    `[package]\nname = "waren6-reader"\nversion = "${version}"\n`,
  );
  return root;
}

test("release version check accepts matching reader release tag and versions", () => {
  const fixture = writeFixture("1.2.3");

  const result = spawnSync(
    process.execPath,
    [scriptPath, "--project", fixture, "--tag", "reader-v1.2.3"],
    { encoding: "utf8" },
  );

  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /release_version=1\.2\.3/);
  assert.match(result.stdout, /release_tag=reader-v1\.2\.3/);
});

test("release version check rejects a tag that does not match app version", () => {
  const fixture = writeFixture("1.2.3");

  const result = spawnSync(
    process.execPath,
    [scriptPath, "--project", fixture, "--tag", "reader-v1.2.4"],
    { encoding: "utf8" },
  );

  assert.equal(result.status, 1);
  assert.match(result.stderr, /expected reader-v1\.2\.3/);
});

test("release version check rejects generic public tags", () => {
  const fixture = writeFixture("1.2.3");

  const result = spawnSync(
    process.execPath,
    [scriptPath, "--project", fixture, "--tag", "v1.2.3"],
    { encoding: "utf8" },
  );

  assert.equal(result.status, 1);
  assert.match(result.stderr, /expected reader-v1\.2\.3/);
});
