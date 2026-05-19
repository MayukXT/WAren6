# WAren6 Field Kit And Airgap Package

The field kit is for evidence machines where the user should not need to clone the repository. It ships WAren6 runtime scripts, the PowerShell decryption dependency, offline Python wheels when available, operator docs, checksums, and a package manifest. It does not ship Reader source, tests, GitHub workflows, research notes, generated cases, or build caches.

## Build On An Online Machine

From the WAren6 repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\airgap\prepare-wheels.ps1
powershell -ExecutionPolicy Bypass -File .\airgap\build-airgap-package.ps1 -Name WAren6-FieldKit-v1.1.0
```

The package is written to:

```text
dist\airgap\WAren6-FieldKit-v1.1.0.zip
dist\airgap\WAren6-FieldKit-v1.1.0.sha256.txt
```

`prepare-wheels.ps1` builds wheels for `ccl_chromium_reader`, `cryptography`, and their dependencies. Build wheels with the same Python major/minor version you expect to use offline, because compiled wheels such as Brotli and cryptography are Python-version-specific.

## Install On An Offline Machine

Run Terminal/PowerShell as Administrator before running WAren6. The field script uses backup-mode file copy for locked WhatsApp evidence, and non-admin shells can miss or fail to copy files.

Extract the package:

```powershell
Expand-Archive .\WAren6-FieldKit-v1.1.0.zip -DestinationPath C:\Tools
cd C:\Tools\WAren6-FieldKit
```

Install Python dependencies without internet:

```powershell
powershell -ExecutionPolicy Bypass -File .\airgap\install-offline-deps.ps1
```

If script execution is blocked, use the process-scoped bypass form:

```powershell
powershell -ExecutionPolicy Bypass -File .\waren6.ps1 --dry
```

## Run Offline Acquisition

Use offline mode when the evidence machine must not launch WhatsApp or download dependencies:

```powershell
powershell -ExecutionPolicy Bypass -File .\waren6.ps1 -f --no-net -d C:\Cases\WAren6
```

For detached evidence copied from another machine:

```powershell
powershell -ExecutionPolicy Bypass -File .\waren6.ps1 -f --no-net -w C:\Cases\CollectedLocalState -i <oduid-hex> -d C:\Cases\WAren6
```

Offline mode does not run the live WhatsApp runtime supplement. It uses copied LocalState/WebView2 evidence, decrypted SQLite/WAL files, and IndexedDB extraction.

## Verify The Package

Before using the package, compare the archive hash:

```powershell
Get-FileHash .\WAren6-FieldKit-v1.1.0.zip -Algorithm SHA256
Get-Content .\WAren6-FieldKit-v1.1.0.sha256.txt
```

Inside the extracted package, inspect:

```text
WAren6.fieldkit.manifest.json
airgap\dependency-notices.md
wheels\
```

## Release Rule

Do not publish an airgap package until every included binary and wheel has acceptable redistribution terms and a matching notice in `airgap\dependency-notices.md`.
