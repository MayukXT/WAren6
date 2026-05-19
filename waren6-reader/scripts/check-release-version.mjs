import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

function parseArgs(argv) {
  const args = {
    project: path.resolve(path.dirname(fileURLToPath(import.meta.url)), ".."),
    tag: "",
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--project") {
      args.project = path.resolve(argv[++i] || "");
    } else if (arg === "--tag") {
      args.tag = argv[++i] || "";
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  return args;
}

function readJson(file) {
  return JSON.parse(readFileSync(file, "utf8"));
}

function readCargoVersion(cargoToml) {
  const match = readFileSync(cargoToml, "utf8").match(/^version\s*=\s*"([^"]+)"/m);
  if (!match) {
    throw new Error(`Could not find package version in ${cargoToml}`);
  }
  return match[1];
}

function checkReleaseVersion({ project, tag }) {
  const packageVersion = readJson(path.join(project, "package.json")).version;
  const tauriVersion = readJson(path.join(project, "src-tauri", "tauri.conf.json")).version;
  const cargoVersion = readCargoVersion(path.join(project, "src-tauri", "Cargo.toml"));
  const errors = [];

  if (packageVersion !== tauriVersion) {
    errors.push(`package.json version ${packageVersion} does not match tauri.conf.json version ${tauriVersion}`);
  }
  if (cargoVersion !== tauriVersion) {
    errors.push(`Cargo.toml version ${cargoVersion} does not match tauri.conf.json version ${tauriVersion}`);
  }

  const expectedTag = `reader-v${tauriVersion}`;
  if (tag && tag !== expectedTag) {
    errors.push(`release tag ${tag} does not match app version; expected ${expectedTag}`);
  }

  return {
    ok: errors.length === 0,
    version: tauriVersion,
    expectedTag,
    errors,
  };
}

try {
  const result = checkReleaseVersion(parseArgs(process.argv.slice(2)));
  if (!result.ok) {
    console.error(result.errors.join("\n"));
    process.exit(1);
  }
  console.log(`release_version=${result.version}`);
  console.log(`release_tag=${result.expectedTag}`);
} catch (error) {
  console.error(error.message);
  process.exit(1);
}
