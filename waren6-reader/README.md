# WAren6 Reader

Local Tauri viewer for `unified_whatsapp.db`.

## Development

```powershell
npm install
npm run tauri dev
```

The UI source is in `src/`. The Rust backend is in `src-tauri/`.

## Tests

```powershell
npm test
cd src-tauri
cargo test
```

## Release

Reader ships from its own release line, starting here with `WAren6 Reader v1.7.0`. GitHub Actions builds and publishes the release assets from `reader-v*` tags.

Before release, keep these versions synchronized:

- `package.json`
- `src-tauri/tauri.conf.json`
- `src-tauri/Cargo.toml`

Local guard:

```powershell
npm run check:release-version -- --tag reader-v1.7.0
```

The `Reader Release` workflow uploads the Reader setup EXE, MSI, portable EXE, Tauri updater `latest.json`, and `WAren6-Reader-latest.json`.

Installed Reader builds use signed Tauri updater artifacts. Portable Reader builds verify the SHA-256 hash from `WAren6-Reader-latest.json` before replacing the EXE.
