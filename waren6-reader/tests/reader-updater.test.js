import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import {
  buildPortableUpdateRequest,
  checkForReaderUpdate,
  compareVersions,
  updateStatusText,
} from "../src/reader-updater.js";

const releaseManifest = {
  version: "1.7.0",
  release_date: "2026-05-17T12:00:00Z",
  release_url: "https://github.com/MayukXT/WAren6/releases/tag/reader-v1.7.0",
  changelog: "Reader OTA assets.",
  assets: {
    reader_portable: {
      name: "WAren6-Reader-Portable-v1.7.0.exe",
      url: "https://github.com/MayukXT/WAren6/releases/download/reader-v1.7.0/WAren6-Reader-Portable-v1.7.0.exe",
      sha256: "a".repeat(64),
    },
  },
};

test("reader updater uses reader-specific latest metadata", async () => {
  const source = readFileSync(new URL("../src/reader-updater.js", import.meta.url), "utf8");

  assert.match(source, /reader-latest\/WAren6-Reader-latest\.json/);
  assert.doesNotMatch(source, /releases\/latest\/download\/WAren6-latest\.json/);
});

test("version comparison handles reader update ordering", () => {
  assert.equal(compareVersions("1.7.0", "1.6.0"), 1);
  assert.equal(compareVersions("1.6.0", "1.7.0"), -1);
  assert.equal(compareVersions("1.7.0", "1.7.0"), 0);
  assert.equal(compareVersions("v1.6.10", "1.6.2"), 1);
});

test("checkForReaderUpdate reports an available update from WAren6 metadata", async () => {
  const result = await checkForReaderUpdate({
    currentVersion: "1.6.0",
    fetchImpl: async () => ({
      ok: true,
      json: async () => releaseManifest,
    }),
  });

  assert.equal(result.status, "available");
  assert.equal(result.latestVersion, "1.7.0");
  assert.equal(result.releaseUrl, releaseManifest.release_url);
  assert.equal(result.portableAsset.name, "WAren6-Reader-Portable-v1.7.0.exe");
});

test("checkForReaderUpdate reports up-to-date when versions match", async () => {
  const result = await checkForReaderUpdate({
    currentVersion: "1.7.0",
    fetchImpl: async () => ({
      ok: true,
      json: async () => releaseManifest,
    }),
  });

  assert.equal(result.status, "current");
  assert.equal(result.latestVersion, "1.7.0");
});

test("portable update request includes download url, hash, and version", () => {
  const request = buildPortableUpdateRequest(releaseManifest);

  assert.deepEqual(request, {
    downloadUrl: releaseManifest.assets.reader_portable.url,
    sha256: releaseManifest.assets.reader_portable.sha256,
    version: "1.7.0",
  });
});

test("update status text covers visible modal states", () => {
  assert.equal(updateStatusText("checking"), "Checking for updates...");
  assert.equal(updateStatusText("current"), "You are up to date.");
  assert.equal(updateStatusText("available"), "Update available.");
  assert.equal(updateStatusText("failed"), "Update check failed.");
  assert.equal(updateStatusText("installed"), "Update installed. Restarting Reader...");
  assert.equal(updateStatusText("portable"), "Portable update ready. Reader will restart after replacement.");
});

test("reader update checks run at startup, info open, and manual button", () => {
  const main = readFileSync(new URL("../src/main.js", import.meta.url), "utf8");

  assert.match(main, /let readerUpdateCheckPromise = null;/);
  assert.match(main, /async function checkReaderUpdates\(\{ force = false \} = \{\}\)/);
  assert.match(main, /refreshReaderAppInfo\(\)\.then\(\(\) => checkReaderUpdates\(\)\)/);
  assert.match(main, /btnReaderInfo\?\.addEventListener\('click', async \(\) => \{[\s\S]*checkReaderUpdates\(\{ force: true \}\);[\s\S]*\}\);/);
  assert.match(main, /btnCheckReaderUpdate\?\.addEventListener\('click', \(\) => \{[\s\S]*checkReaderUpdates\(\{ force: true \}\);[\s\S]*\}\);/);
});
