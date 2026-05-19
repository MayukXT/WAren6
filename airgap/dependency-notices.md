# WAren6 Airgap Dependency Notices

This file is the release checklist for dependencies that may be redistributed in an offline WAren6 kit.

## Included Runtime Files

- `BouncyCastle.Cryptography.dll` - cryptographic dependency used by the PowerShell database/WAL decryption path. Keep the upstream MIT license notice with redistributed binaries.
- `wheels\ccl_chromium_reader-*.whl` - IndexedDB/Chromium storage reader used by `waren6.py`. Built from `https://github.com/cclgroupltd/ccl_chromium_reader`.
- `wheels\ccl_simplesnappy-*.whl` - dependency of `ccl_chromium_reader`. Built from `https://github.com/cclgroupltd/ccl_simplesnappy`.
- `wheels\brotli-*.whl` - Brotli decompression dependency used by Chromium storage parsing.
- `wheels\cryptography-*.whl` plus resolver dependencies - AES-CBC backend used by opaque Store 8 recovery and transfer helper tests. Keep upstream license notices with redistributed wheels.
- `python_embedded\` - optional Python runtime. If included, keep the Python Software Foundation license files from the downloaded embeddable package.

## Build Notes

Current offline wheels were prepared with:

```powershell
powershell -ExecutionPolicy Bypass -File .\airgap\prepare-wheels.ps1
```

The observed source commits during the local wheel build were:

- `ccl_chromium_reader`: `552516720761397c4d482908b6b8b08130b313a1`
- `ccl_simplesnappy`: `3d085230baa8c46cf2090ebba29bf6e8eab31087`

## Release Rule

Do not publish an air-gapped archive until every binary and wheel has a matching license notice in the archive and the release SHA-256 has been recorded.
