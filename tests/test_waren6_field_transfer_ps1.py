import hashlib
import json
import os
import pathlib
import re
import subprocess
import tempfile
import unittest
import zipfile

try:
    from cryptography.hazmat.primitives import hashes, hmac, padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
except Exception:
    hashes = hmac = padding = Cipher = algorithms = modes = PBKDF2HMAC = None


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "waren6.ps1"


def extract_recombine_helper(source):
    function_start = source.index("function Write-WAren6RecombineHelper")
    script_start = source.index("@'\n", function_start) + 3
    script_end = source.index("\n'@ | Out-File", script_start)
    return source[script_start:script_end]


def sha256_hex(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def write_zip(path, name="case/hello.txt", body=b"hello from WAren6"):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, body)


def encrypt_waren6_transfer(plain_path, encrypted_path, password):
    if PBKDF2HMAC is None:
        raise unittest.SkipTest("cryptography package is unavailable")

    plaintext = plain_path.read_bytes()
    salt = os.urandom(16)
    iv = os.urandom(16)
    iterations = 200000
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=64,
        salt=salt,
        iterations=iterations,
    )
    key_material = kdf.derive(password.encode("utf-8"))
    aes_key = key_material[:32]
    mac_key = key_material[32:]
    header = {
        "schema": "waren6.transfer.encrypted.v1",
        "algorithm": "AES-256-CBC+HMAC-SHA256",
        "kdf": "PBKDF2-HMAC-SHA256",
        "iterations": iterations,
        "salt_b64": __import__("base64").b64encode(salt).decode("ascii"),
        "iv_b64": __import__("base64").b64encode(iv).decode("ascii"),
        "plaintext_name": plain_path.name,
        "plaintext_size": len(plaintext),
        "plaintext_sha256": hashlib.sha256(plaintext).hexdigest().upper(),
    }
    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    padder = padding.PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()
    encryptor = Cipher(algorithms.AES(aes_key), modes.CBC(iv)).encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    body = b"WA6ENC1\n" + len(header_bytes).to_bytes(4, "little") + header_bytes + ciphertext
    signer = hmac.HMAC(mac_key, hashes.SHA256())
    signer.update(body)
    encrypted_path.write_bytes(body + signer.finalize())


class PowerShellFieldTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text(encoding="utf-8", errors="replace")

    def test_short_and_long_telegram_transfer_flags_are_declared(self):
        source = self.source

        self.assertRegex(source, r"\[Alias\('doc'[^)]*\)\]\s*\r?\n\s*\[switch\]\$Doctor")
        self.assertIn('"doctor" = "Doctor"', source)
        self.assertIn('"doc" = "Doctor"', source)
        self.assertRegex(source, r"\[Alias\('tg'[^)]*\)\]\s*\r?\n\s*\[string\]\$TelegramBotToken")
        self.assertRegex(source, r"\[Alias\('cid'[^)]*\)\]\s*\r?\n\s*\[string\]\$TelegramChatId")
        self.assertRegex(source, r"\[Alias\('ad'[^)]*\)\]\s*\r?\n\s*\[switch\]\$TelegramAutoDelete")
        self.assertRegex(source, r"\[Alias\('enc'[^)]*\)\][\s\S]{0,240}\[string\]\$TelegramEncryptPassword")
        self.assertRegex(source, r"\[Alias\('keep-case-folder'[^)]*\)\]\s*\r?\n\s*\[switch\]\$KeepCaseDirectoryAfterArchive")
        self.assertIn('"telegram" = "TelegramBotToken"', source)
        self.assertIn('"chat-id" = "TelegramChatId"', source)
        self.assertIn('"autodelete" = "TelegramAutoDelete"', source)
        self.assertIn('"encrypt" = "TelegramEncryptPassword"', source)
        self.assertIn('"tg-api-base" = "TelegramApiBase"', source)
        self.assertIn('"keep-case-folder" = "KeepCaseDirectoryAfterArchive"', source)

    def test_sensitive_values_are_redacted_before_logging_or_manifest(self):
        source = self.source

        self.assertIn("function Protect-WAren6CommandLine", source)
        self.assertIn("TelegramBotToken", source)
        self.assertIn("TelegramEncryptPassword", source)
        self.assertIn("[REDACTED]", source)
        self.assertRegex(source, r"Protect-WAren6CommandLine\s+-CommandLine\s+\(\[Environment\]::CommandLine\)")
        self.assertIn('$global:WAren6Version = "1.1.0"', source)
        self.assertNotIn('Write-WAren6Output "(sessionDBSecret):', source)
        self.assertNotIn('Write-WAren6Output "(clientKey):', source)
        self.assertNotIn('Write-WAren6Output "(publisherKey):', source)
        self.assertNotIn('Write-WAren6Output "EncryptionKey-BC', source)
        self.assertNotIn('Write-WAren6Output "(DBKEY):', source)
        self.assertNotIn("[BitConverter]::ToString($kek)", source)
        self.assertNotIn("[BitConverter]::ToString($gcm_key)", source)
        self.assertNotIn("[BitConverter]::ToString($second_cipher_text)", source)
        self.assertNotIn("[BitConverter]::ToString($encKey)", source)
        self.assertNotIn("[BitConverter]::ToString($IV)", source)
        self.assertIn('Write-Verbose "kek: [redacted; sha256:', source)
        self.assertIn('Write-Verbose "gcm_key: [redacted; sha256:', source)
        self.assertIn('Write-Verbose "Decrypted-BC nsCipherText(padded): [redacted; sha256:', source)
        self.assertIn('Write-Verbose "EncryptionKey-BC (encKey): [redacted; sha256:', source)
        self.assertIn('Write-Verbose "(IV-BC): [redacted; sha256:', source)
        self.assertNotIn('"dpapi_blob: $dpapi_hex"', source)
        self.assertNotIn('"wrapped_key: $wrapped_key_hex"', source)
        self.assertNotIn('"nonce: $nonce_hex"', source)
        self.assertNotIn('"cipher_text: $cipher_text_hex"', source)
        self.assertNotIn('"gcm_tag: $gcm_tag_hex"', source)
        self.assertNotIn('Write-WAren6Output "UserKey: $hexUserKey"', source)
        self.assertNotIn('Write-Verbose "NS18: $(ConvertTo-HexString($ns18Output))"', source)
        self.assertNotIn('Write-Verbose "ID: $devID"', source)
        self.assertIn("dpapi_blob_sha256:", source)
        self.assertIn("wrapped_key_sha256:", source)
        self.assertIn("cipher_text_sha256:", source)
        self.assertIn('Write-WAren6Output "UserKey: [redacted; sha256:', source)
        self.assertIn('Write-Verbose "NS18: [redacted; sha256:', source)
        self.assertIn('Write-Verbose "ID: [redacted; sha256:', source)
        self.assertNotIn("Write-Verbose $WhatsAppPath", source)
        self.assertIn("Write-Verbose $verboseSourcePath", source)
        self.assertIn('Write-Verbose "Copying $verboseSourcePath to $verboseOutputPath"', source)
        self.assertIn("$pythonOutput = & $pythonExe @pythonArgs 2>&1", source)
        self.assertIn('Protect-WAren6PathText -Text ([string]$line) -CaseRoot $targetOutput', source)
        self.assertIn("Write-Warning \"  [X] waren6.py exited with error code: $pythonExitCode\"", source)
        self.assertIn('"--no-progress"', source)
        self.assertNotIn('"ODUID: $hexWhatsAppAppUID" | Out-File', source)
        self.assertNotIn('"DBKEY: $hexDBKey" | Out-File', source)
        self.assertIn("ODUID_SHA256:", source)
        self.assertIn("DBKEY_SHA256:", source)

    def test_copy_directory_fails_closed_for_acquisition_errors(self):
        source = self.source

        self.assertIn("Destination directory must not be the source directory or inside it.", source)
        self.assertIn('throw "Error during copy operation: $($_.Exception.Message)"', source)
        self.assertNotIn('Write-Error "Error during copy operation: $($_.Exception.Message)"', source)
        self.assertIn("/NJH", source)
        self.assertIn("/NJS", source)
        self.assertIn("$robocopyOutput = & robocopy.exe @robocopyArgs 2>&1", source)
        self.assertIn("Protect-WAren6PathText -Text ([string]$line) -CaseRoot $global:targetOutput", source)
        self.assertNotIn('Start-Process -FilePath "robocopy.exe"', source)

    def test_runtime_capture_has_best_effort_close_guard(self):
        source = self.source

        self.assertIn("function Disable-WAren6WhatsAppClose", source)
        self.assertIn("function Enable-WAren6WhatsAppClose", source)
        self.assertIn("function Invoke-WAren6WhatsAppRuntimeLaunch", source)
        self.assertIn("function Hide-WAren6WhatsAppWindowsForPeriod", source)
        self.assertRegex(source, r"\[Alias\('foreground-runtime'[^)]*\)\]\s*\r?\n\s*\[switch\]\$ForegroundRuntime")
        self.assertIn('"foreground-runtime" = "ForegroundRuntime"', source)
        self.assertRegex(source, r"Invoke-WAren6RuntimeStore8Capture[\s\S]*\[switch\]\$BlockClose")
        self.assertIn("$runtimeHidden = -not $ForegroundRuntime", source)
        self.assertRegex(source, r"Invoke-WAren6RuntimeStore8Capture\s+-OutputDirectory\s+\$runtimeCaptureRoot\s+-Silent:\$runtimeHidden\s+-BlockClose:\$ForegroundRuntime")
        self.assertRegex(source, r"Invoke-WAren6RuntimeStore8Capture\s+-OutputDirectory\s+\$CasePath\s+-Silent:\$runtimeHidden\s+-BlockClose:\$ForegroundRuntime")

    def test_runtime_capture_exports_quote_context_for_live_replies(self):
        source = self.source

        self.assertIn("quoted_stanza_id", source)
        self.assertIn("quoted_participant", source)
        self.assertIn("quoted_msg_body", source)
        self.assertIn("quoted_msg_type", source)
        self.assertRegex(source, r"quotedStanzaID|quotedStanzaId")
        self.assertRegex(source, r"quotedParticipant")
        self.assertRegex(source, r"quotedMsg")

    def test_archive_prefers_zstd_tar_with_zip_fallback_and_verification(self):
        source = self.source

        self.assertIn("function Test-WAren6TarZstdAvailable", source)
        self.assertIn("function New-WAren6CaseArchive", source)
        self.assertIn("function Test-WAren6ArchiveReadable", source)
        self.assertIn(".tar.zst", source)
        self.assertIn(".zip", source)
        self.assertRegex(source, r"tar\.exe[\s\S]*--zstd")
        self.assertRegex(source, r"Test-WAren6ArchiveReadable\s+-ArchivePath\s+\$archivePath")

    def test_plain_run_cleans_extracted_case_folder_after_verified_archive(self):
        source = self.source

        self.assertIn("function Remove-WAren6CaseDirectoryAfterArchive", source)
        self.assertIn("$effectiveDeleteCaseDirectoryAfterArchive = -not $KeepCaseDirectoryAfterArchive", source)
        self.assertIn("-DeleteCaseDirectoryAfterArchive:$effectiveDeleteCaseDirectoryAfterArchive", source)
        self.assertRegex(source, r"New-WAren6CaseArchive\s+-Source\s+\$targetOutput[\s\S]{0,180}-BaseName\s+\$archiveBaseName(?!\s+-DeleteSource)")
        self.assertRegex(source, r"Remove-WAren6CaseDirectoryAfterArchive\s+-CasePath\s+\$targetOutput\s+-ArchivePath\s+\$archivePath")
        self.assertRegex(source, r"Test-WAren6ArchiveReadable\s+-ArchivePath\s+\$ArchivePath")
        self.assertIn("cleaned after archive verification", source)
        self.assertIn("return $rootManifestPath", source)

    def test_python_unify_failure_keeps_case_and_exits_failed(self):
        source = self.source

        self.assertIn("$pythonAttempted = $false", source)
        self.assertIn("$pythonFailed = $false", source)
        self.assertIn("$pythonAttempted = $true", source)
        self.assertIn("$pythonFailed = $true", source)
        self.assertIn("Unified DB was not completed. Keeping extracted case folder for inspection and re-run.", source)
        self.assertIn('$unifiedDbWasBuilt = [bool]$modeInfo.pythonUnified', source)
        self.assertRegex(source, r"if\s*\(\$DeleteCaseDirectoryAfterArchive\s+-and\s+-not\s+\$pythonFailed")
        self.assertIn("|                   EXTRACTION INCOMPLETE                    |", source)
        self.assertIn("| Access DB:        not built; see Python error above", source)
        self.assertIn("| Case folder:      kept for inspection", source)
        self.assertRegex(source, r"if\s*\(\$pythonFailed\)\s*{[\s\S]{0,80}exit\s+1")
        self.assertIn("Unfinished case folder kept locally for later --unify.", source)
        self.assertRegex(
            source,
            r"if\s*\(-not\s+\$pythonFailed\)\s*{[\s\S]{0,120}\$autoDeleteCandidates\s*=\s*@\(\$targetOutput\)\s*\+\s*\$autoDeleteCandidates",
        )

    def test_telegram_transfer_splits_only_for_transfer_and_verified_delete_is_gated(self):
        source = self.source

        self.assertIn("function Split-WAren6TransferFile", source)
        self.assertIn("function Write-WAren6TransferManifest", source)
        self.assertIn("function Invoke-WAren6TelegramTransfer", source)
        self.assertIn("function Invoke-WAren6VerifiedAutoDelete", source)
        self.assertIn("sendDocument", source)
        self.assertIn("52428800", source)
        self.assertRegex(source, r"if\s*\(\$TelegramBotToken\)")
        self.assertRegex(source, r"if\s*\(\$TelegramAutoDelete\s+-and\s+\$telegramResult\.success\)")
        self.assertIn("$deletePaths = @()", source)
        self.assertIn("if ($deletePaths.Count -gt 0)", source)

    def test_checksum_helpers_do_not_depend_on_clipboard(self):
        source = self.source

        self.assertNotIn("Set-Clipboard", source)
        self.assertNotIn("function Get-MD5Checksum", source)
        self.assertNotIn("function Get-SHA512Checksum", source)
        self.assertNotIn("MD5 checksum", source)
        self.assertNotIn("SHA512 checksum", source)
        self.assertIn("SHA-256 Checksum", source)

    def test_get_id_redacts_by_default_and_raw_output_is_explicit(self):
        source = self.source

        self.assertRegex(source, r"\[Alias\('show-secret-id'[^)]*\)\]\s*\r?\n\s*\[switch\]\$ShowSecretId")
        self.assertIn('"show-secret-id" = "ShowSecretId"', source)
        self.assertNotIn('Write-WAren6Output "ODUID: $ODUID_HEX"', source)
        self.assertRegex(source, r"if\s*\(\$ShowSecretId\)\s*{[\s\S]{0,180}ODUID:\s*\$ODUID_HEX")
        self.assertRegex(source, r"Raw ODUID hidden[\s\S]{0,120}--show-secret-id")

    def test_reports_are_opt_in_and_default_unify_args_are_lean(self):
        source = self.source

        self.assertRegex(source, r"\[Alias\('reports'[^)]*\)\]\s*\r?\n\s*\[switch\]\$GenerateReports")
        self.assertIn('"reports" = "GenerateReports"', source)
        self.assertRegex(source, r"if\s*\(\$GenerateReports\)\s*{[\s\S]{0,360}--reports-dir")
        self.assertNotRegex(source, r"\$pyArgs\s*=\s*@\([\s\S]{0,320}--reports-dir")

    def test_start_transcript_uses_minimal_header_only_when_supported(self):
        source = self.source

        self.assertIn("(Get-Command Start-Transcript).Parameters.ContainsKey('UseMinimalHeader')", source)
        self.assertRegex(source, r"if\s*\(\$supportsMinimalHeader\)")

    def test_recombine_helper_does_not_clobber_single_file_transfer(self):
        source = self.source
        helper = extract_recombine_helper(source)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            payload = tmp_path / "WAren6_20260511225935.tar.zst.wa6enc"
            original = b"single telegram payload"
            payload.write_bytes(original)
            digest = hashlib.sha256(original).hexdigest().upper()
            manifest = {
                "schema": "waren6.telegram.transfer.v1",
                "encrypted": False,
                "original_archive": {
                    "name": "WAren6_20260511225935.tar.zst",
                    "size": len(original),
                    "sha256": digest,
                },
                "transfer_file": {
                    "name": payload.name,
                    "size": len(original),
                    "sha256": digest,
                },
                "parts": [
                    {
                        "index": 1,
                        "name": payload.name,
                        "size": len(original),
                        "sha256": digest,
                    }
                ],
            }
            (tmp_path / "WAren6_transfer_manifest.json").write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )
            helper_path = tmp_path / "WAren6_recombine.ps1"
            helper_path.write_text(helper, encoding="utf-8")

            result = subprocess.run(
                [
                    "powershell",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(helper_path),
                    "-NoExtract",
                ],
                cwd=tmp,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(payload.read_bytes(), original)
            self.assertIn("Recombined archive", result.stdout)

    def test_recombine_helper_extracts_unencrypted_transfer_without_password(self):
        source = self.source
        helper = extract_recombine_helper(source)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            archive = tmp_path / "WAren6_20260511225935.zip"
            write_zip(archive)
            digest = sha256_hex(archive)
            manifest = {
                "schema": "waren6.telegram.transfer.v1",
                "encrypted": False,
                "original_archive": {
                    "name": archive.name,
                    "size": archive.stat().st_size,
                    "sha256": digest,
                },
                "transfer_file": {
                    "name": archive.name,
                    "size": archive.stat().st_size,
                    "sha256": digest,
                },
                "parts": [
                    {
                        "index": 1,
                        "name": archive.name,
                        "size": archive.stat().st_size,
                        "sha256": digest,
                    }
                ],
            }
            (tmp_path / "WAren6_transfer_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            helper_path = tmp_path / "WAren6_recombine.ps1"
            helper_path.write_text(helper, encoding="utf-8")

            result = subprocess.run(
                [
                    "powershell",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(helper_path),
                ],
                cwd=tmp,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Extracted folder", result.stdout)
            self.assertTrue((tmp_path / "WAren6_20260511225935" / "case" / "hello.txt").exists())

    def test_recombine_helper_decrypts_then_extracts_encrypted_transfer(self):
        source = self.source
        helper = extract_recombine_helper(source)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            archive = tmp_path / "WAren6_20260511225935.zip"
            payload = tmp_path / "WAren6_20260511225935.zip.wa6enc"
            write_zip(archive)
            plain_digest = sha256_hex(archive)
            encrypt_waren6_transfer(archive, payload, "correct horse")
            archive.unlink()
            payload_digest = sha256_hex(payload)
            manifest = {
                "schema": "waren6.telegram.transfer.v1",
                "encrypted": True,
                "original_archive": {
                    "name": archive.name,
                    "size": 0,
                    "sha256": plain_digest,
                },
                "transfer_file": {
                    "name": payload.name,
                    "size": payload.stat().st_size,
                    "sha256": payload_digest,
                },
                "parts": [
                    {
                        "index": 1,
                        "name": payload.name,
                        "size": payload.stat().st_size,
                        "sha256": payload_digest,
                    }
                ],
            }
            (tmp_path / "WAren6_transfer_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            helper_path = tmp_path / "WAren6_recombine.ps1"
            helper_path.write_text(helper, encoding="utf-8")

            result = subprocess.run(
                [
                    "powershell",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(helper_path),
                    "-Password",
                    "correct horse",
                ],
                cwd=tmp,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Decrypted archive", result.stdout)
            self.assertIn("Extracted folder", result.stdout)
            self.assertEqual(sha256_hex(archive), plain_digest)
            self.assertTrue((tmp_path / "WAren6_20260511225935" / "case" / "hello.txt").exists())

    def test_recombine_helper_wrong_password_leaves_no_decrypted_archive_or_folder(self):
        source = self.source
        helper = extract_recombine_helper(source)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            archive = tmp_path / "WAren6_20260511225935.zip"
            payload = tmp_path / "WAren6_20260511225935.zip.wa6enc"
            write_zip(archive)
            plain_digest = sha256_hex(archive)
            encrypt_waren6_transfer(archive, payload, "correct horse")
            archive.unlink()
            payload_digest = sha256_hex(payload)
            manifest = {
                "schema": "waren6.telegram.transfer.v1",
                "encrypted": True,
                "original_archive": {
                    "name": archive.name,
                    "size": 0,
                    "sha256": plain_digest,
                },
                "transfer_file": {
                    "name": payload.name,
                    "size": payload.stat().st_size,
                    "sha256": payload_digest,
                },
                "parts": [
                    {
                        "index": 1,
                        "name": payload.name,
                        "size": payload.stat().st_size,
                        "sha256": payload_digest,
                    }
                ],
            }
            (tmp_path / "WAren6_transfer_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            helper_path = tmp_path / "WAren6_recombine.ps1"
            helper_path.write_text(helper, encoding="utf-8")

            result = subprocess.run(
                [
                    "powershell",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(helper_path),
                    "-Password",
                    "wrong horse",
                    "-MaxPasswordAttempts",
                    "1",
                ],
                cwd=tmp,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Unable to decrypt transfer after 1 attempt(s).", result.stderr)
            self.assertFalse(archive.exists())
            self.assertFalse((tmp_path / "WAren6_20260511225935").exists())

    def test_recombine_helper_prompts_for_encrypted_password_and_limits_attempts(self):
        helper = extract_recombine_helper(self.source)

        self.assertIn("Read-Host -AsSecureString", helper)
        self.assertIn("$MaxPasswordAttempts = 3", helper)
        self.assertIn("for ($passwordAttempt = 1; $passwordAttempt -le $MaxPasswordAttempts; $passwordAttempt++)", helper)
        self.assertIn("Unable to decrypt transfer after $MaxPasswordAttempts attempt(s).", helper)
        self.assertIn("Remove-Item -LiteralPath $OutputPath -Force -ErrorAction SilentlyContinue", helper)

    def test_recombine_helper_hashing_retries_transient_file_locks(self):
        source = self.source

        self.assertRegex(source, r"function Get-Sha256[\s\S]*RetryCount")
        self.assertIn("Start-Sleep -Milliseconds $DelayMilliseconds", source)
        self.assertIn("FileShare]::ReadWrite", source)

    def test_logs_are_written_to_case_and_uploaded_before_autodelete(self):
        source = self.source

        self.assertIn("function Start-WAren6Log", source)
        self.assertIn("function Write-WAren6Log", source)
        self.assertIn("logs.txt", source)
        self.assertRegex(source, r"\$script:WAren6LogPath")
        self.assertRegex(source, r"Invoke-WAren6TelegramTransfer[\s\S]*\$LogPath")

    def test_doctor_runs_before_evidence_acquisition_modes(self):
        source = self.source

        self.assertIn("function Invoke-WAren6Doctor", source)
        doctor_gate = source.rindex("if ($Doctor)")
        unify_gate = source.rindex("if ($UnifyOnly)")
        start_call = source.rindex("Start-WAren6 `")
        self.assertLess(doctor_gate, unify_gate)
        self.assertLess(doctor_gate, start_call)
        self.assertRegex(source, r"Invoke-WAren6Doctor[\s\S]*exit\s+\$doctorExit")


if __name__ == "__main__":
    unittest.main()
