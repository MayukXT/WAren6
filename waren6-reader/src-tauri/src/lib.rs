use rusqlite::{Connection, OpenFlags, OptionalExtension, Row};
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::collections::HashSet;
use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::Mutex;
use tauri::Manager;
use tauri::State;
use tauri_plugin_dialog::DialogExt;

// ---------------------------------------------------------------------------
// App State
// ---------------------------------------------------------------------------

pub struct AppState {
    pub db_path: Mutex<Option<String>>,
    pub db_conn: Mutex<Option<Connection>>,
    pub cache_conn: Mutex<Option<Connection>>,
    pub db_sha256: Mutex<Option<String>>,
}

const APP_IDENTIFIER: &str = "com.mayukxt.waren6.reader";
const SEARCH_CACHE_SCHEMA_VERSION: &str = "2";

#[derive(Serialize, Clone, Debug)]
pub struct PortableUpdateSafety {
    pub safe: bool,
    pub reason: Option<String>,
}

#[derive(Serialize, Clone, Debug)]
pub struct ReaderAppInfo {
    pub version: String,
    pub install_type: String,
    pub current_exe_path: Option<String>,
    pub exe_path_is_safe: bool,
    pub exe_path_status: Option<String>,
    pub app_identifier: String,
}

// ---------------------------------------------------------------------------
// Data Models — unified_whatsapp.db schema
// ---------------------------------------------------------------------------

#[derive(Serialize, Clone)]
pub struct Chat {
    pub chat_jid: String,
    pub chat_name: Option<String>,
    pub chat_phone: Option<String>,
    pub is_group: bool,
    pub is_newsletter: bool,
    pub last_msg: Option<String>,
    pub last_msg_ts: i64,
    pub message_count: i64,
    pub sent_count: i64,
    pub recv_count: i64,
    pub unread_count: i64,
}

#[derive(Serialize, Clone)]
pub struct Message {
    pub rowid: i64,
    pub msg_id: Option<String>,
    pub chat_jid: String,
    pub from_me: Option<i64>,
    pub sender_jid: Option<String>,
    pub sender_name: Option<String>,
    pub sender_phone: Option<String>,
    pub timestamp: i64,
    pub text: Option<String>,
    pub is_group: bool,
    pub msg_key: Option<String>,
    // Message type
    pub msg_type: Option<String>,
    // Reply / quote
    pub quoted_stanza_id: Option<String>,
    pub quoted_participant: Option<String>,
    pub quoted_msg_body: Option<String>,
    pub quoted_msg_type: Option<String>,
    // Call log
    pub call_duration: Option<i64>,
    pub call_outcome: Option<String>,
    pub is_video_call: bool,
    // Media metadata
    pub media_mime_type: Option<String>,
    pub media_filename: Option<String>,
    pub media_size: Option<i64>,
    pub media_case_path: Option<String>,
    pub media_sha256: Option<String>,
    pub media_status: Option<String>,
    pub body_status: Option<String>,
    pub is_edited: bool,
    pub edited_at: Option<i64>,
    pub edit_count: i64,
    pub edit_history_status: Option<String>,
}

#[derive(Serialize, Clone)]
pub struct MediaSummary {
    pub total: i64,
    pub available: i64,
    pub missing: i64,
    pub photos: i64,
    pub videos: i64,
    pub audio: i64,
    pub documents: i64,
    pub stickers: i64,
}

#[derive(Serialize, Clone)]
pub struct MediaItem {
    pub rowid: i64,
    pub msg_key: Option<String>,
    pub chat_jid: String,
    pub chat_name: Option<String>,
    pub from_me: Option<i64>,
    pub sender_name: Option<String>,
    pub timestamp: i64,
    pub text: Option<String>,
    pub msg_type: Option<String>,
    pub media_kind: String,
    pub media_mime_type: Option<String>,
    pub media_filename: Option<String>,
    pub media_size: Option<i64>,
    pub media_case_path: Option<String>,
    pub media_sha256: Option<String>,
    pub media_status: Option<String>,
}

#[derive(Serialize, Clone)]
pub struct ContactSummary {
    pub total: i64,
    pub saved: i64,
    pub unsaved: i64,
    pub groups: i64,
    pub with_chats: i64,
    pub businesses: i64,
}

#[derive(Serialize, Clone)]
pub struct ContactItem {
    pub jid: String,
    pub lid: Option<String>,
    pub phone_jid: Option<String>,
    pub phone_number: Option<String>,
    pub display_name: Option<String>,
    pub contact_name: Option<String>,
    pub short_name: Option<String>,
    pub push_name: Option<String>,
    pub is_business: bool,
    pub is_self: bool,
    pub is_group: bool,
    pub chat_jid: Option<String>,
    pub chat_name: Option<String>,
    pub last_activity: i64,
    pub message_count: i64,
    pub sent_count: i64,
    pub recv_count: i64,
    pub media_count: i64,
    pub call_count: i64,
}

#[derive(Serialize, Clone)]
pub struct CallSummary {
    pub total: i64,
    pub missed: i64,
    pub answered: i64,
    pub declined: i64,
    pub incoming: i64,
    pub outgoing: i64,
    pub voice: i64,
    pub video: i64,
}

#[derive(Serialize, Clone)]
pub struct CallItem {
    pub rowid: i64,
    pub msg_key: Option<String>,
    pub chat_jid: String,
    pub chat_name: Option<String>,
    pub phone: Option<String>,
    pub from_me: Option<i64>,
    pub timestamp: i64,
    pub call_duration: Option<i64>,
    pub call_outcome: Option<String>,
    pub is_video_call: bool,
    pub msg_type: Option<String>,
    pub sender_name: Option<String>,
    pub sender_phone: Option<String>,
}

#[derive(Serialize, Clone)]
pub struct ContactInfo {
    pub lid: Option<String>,
    pub phone_number: Option<String>,
    pub phone_jid: Option<String>,
    pub contact_name: Option<String>,
    pub short_name: Option<String>,
    pub push_name: Option<String>,
    pub is_self: bool,
}

#[derive(Serialize, Clone)]
pub struct GroupParticipant {
    pub group_jid: String,
    pub participant_lid: Option<String>,
    pub participant_phone: Option<String>,
    pub participant_name: Option<String>,
    pub is_admin: bool,
}

#[derive(Serialize, Clone)]
pub struct SearchResult {
    pub msg: Message,
    pub chat_name: Option<String>,
}

#[derive(Serialize, Clone)]
pub struct MessageWindow {
    pub messages: Vec<Message>,
    pub target_found: bool,
    pub has_older: bool,
    pub has_newer: bool,
}

#[derive(Serialize, Clone)]
pub struct MessageReceipt {
    pub msg_key: String,
    pub receiver_jid: Option<String>,
    pub receiver_phone: Option<String>,
    pub receiver_name: Option<String>,
    pub delivery_time: Option<i64>,
    pub read_time: Option<i64>,
    pub played_time: Option<i64>,
}

/// Compact status for rendering tick marks in the UI
#[derive(Serialize, Clone)]
pub struct MessageStatus {
    pub msg_key: String,
    /// "sent" | "delivered" | "read"
    pub status: String,
}

#[derive(Serialize, Clone)]
pub struct MessageMention {
    pub msg_key: String,
    pub chat_jid: Option<String>,
    pub mention_index: i64,
    pub kind: String,
    pub target_jid: Option<String>,
    pub target_phone: Option<String>,
    pub target_name: Option<String>,
    pub display_text: Option<String>,
    pub source: Option<String>,
    pub confidence: Option<String>,
}

#[derive(Serialize, Clone)]
pub struct MessageReaction {
    pub parent_msg_key: String,
    pub sender_jid: Option<String>,
    pub sender_phone: Option<String>,
    pub sender_name: Option<String>,
    pub reaction_text: Option<String>,
    pub timestamp: Option<i64>,
}

#[derive(Serialize, Clone)]
pub struct MessageEdit {
    pub target_msg_key: String,
    pub target_chat_jid: Option<String>,
    pub target_msg_id: Option<String>,
    pub edit_event_msg_key: Option<String>,
    pub edit_index: i64,
    pub edited_at: Option<i64>,
    pub editor_jid: Option<String>,
    pub editor_phone: Option<String>,
    pub editor_name: Option<String>,
    pub previous_text: Option<String>,
    pub new_text: Option<String>,
    pub source: Option<String>,
    pub confidence: Option<String>,
}

#[derive(Serialize, Clone)]
pub struct QuoteSnapshot {
    pub rowid: i64,
    pub msg_key: Option<String>,
    pub timestamp: Option<i64>,
    pub quoted_msg_body: Option<String>,
    pub quoted_msg_type: Option<String>,
}

#[derive(Serialize, Clone)]
pub struct MessageEditHistory {
    pub msg_key: String,
    pub history_status: Option<String>,
    pub is_edited: bool,
    pub edited_at: Option<i64>,
    pub edit_count: i64,
    pub edits: Vec<MessageEdit>,
    pub quote_snapshots: Vec<QuoteSnapshot>,
}

#[derive(Serialize, Clone)]
pub struct ContactSearchResult {
    pub chat_jid: String,
    pub display_name: String,
    pub phone: Option<String>,
    pub is_group: bool,
}

#[derive(Serialize, Clone)]
pub struct ExtractionInfo {
    pub extraction_time: Option<String>,
    pub self_phone: Option<String>,
    pub total_messages: Option<String>,
    pub messages_sent: Option<String>,
    pub messages_received: Option<String>,
    pub total_contacts: Option<String>,
    pub resolved_contacts: Option<String>,
    pub total_chats: Option<String>,
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn install_type_from_path_markers(exe_path: &Path, has_uninstaller_marker: bool) -> &'static str {
    let path = exe_path.to_string_lossy().replace('/', "\\").to_lowercase();
    if path.contains("\\program files\\")
        || path.contains("\\program files (x86)\\")
        || has_uninstaller_marker
    {
        "installed"
    } else if exe_path
        .extension()
        .and_then(|value| value.to_str())
        .is_some_and(|ext| ext.eq_ignore_ascii_case("exe"))
    {
        "portable"
    } else {
        "unknown"
    }
}

fn has_uninstaller_marker(exe_path: &Path) -> bool {
    let Some(parent) = exe_path.parent() else {
        return false;
    };

    fs::read_dir(parent)
        .ok()
        .into_iter()
        .flat_map(|entries| entries.filter_map(Result::ok))
        .any(|entry| {
            let name = entry.file_name().to_string_lossy().to_lowercase();
            name.starts_with("uninstall ") && name.ends_with(".exe")
        })
}

fn detect_install_type_for_path(exe_path: &Path) -> &'static str {
    install_type_from_path_markers(exe_path, has_uninstaller_marker(exe_path))
}

fn parent_folder_is_writable(path: &Path) -> bool {
    let Some(parent) = path.parent() else {
        return false;
    };
    let probe = parent.join(format!(".waren6-update-write-test-{}", std::process::id()));
    match fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&probe)
    {
        Ok(_) => {
            let _ = fs::remove_file(probe);
            true
        }
        Err(_) => false,
    }
}

fn portable_update_safety_for_path(exe_path: &Path, parent_writable: bool) -> PortableUpdateSafety {
    if !exe_path
        .extension()
        .and_then(|value| value.to_str())
        .is_some_and(|ext| ext.eq_ignore_ascii_case("exe"))
    {
        return PortableUpdateSafety {
            safe: false,
            reason: Some("current executable is not an .exe file".to_string()),
        };
    }

    if !parent_writable {
        return PortableUpdateSafety {
            safe: false,
            reason: Some("current folder is not writable".to_string()),
        };
    }

    PortableUpdateSafety {
        safe: true,
        reason: None,
    }
}

#[cfg(test)]
fn app_info_for_exe_path(exe_path: &Path, parent_writable: bool) -> ReaderAppInfo {
    let safety = portable_update_safety_for_path(exe_path, parent_writable);
    ReaderAppInfo {
        version: env!("CARGO_PKG_VERSION").to_string(),
        install_type: install_type_from_path_markers(exe_path, false).to_string(),
        current_exe_path: Some(exe_path.to_string_lossy().into_owned()),
        exe_path_is_safe: safety.safe,
        exe_path_status: safety.reason,
        app_identifier: APP_IDENTIFIER.to_string(),
    }
}

fn normalize_sha256(value: &str) -> String {
    value
        .trim()
        .trim_start_matches("sha256:")
        .split_whitespace()
        .next()
        .unwrap_or("")
        .to_ascii_lowercase()
}

fn sha256_path(path: &Path) -> Result<String, String> {
    let mut file =
        fs::File::open(path).map_err(|e| format!("Failed to open file for hashing: {e}"))?;
    let mut hasher = Sha256::new();
    let mut buf = [0u8; 1024 * 1024];
    loop {
        let n = file
            .read(&mut buf)
            .map_err(|e| format!("Failed to read file for hashing: {e}"))?;
        if n == 0 {
            break;
        }
        hasher.update(&buf[..n]);
    }
    Ok(format!("{:x}", hasher.finalize()))
}

fn allowed_release_download_url(download_url: &str) -> bool {
    download_url.starts_with("https://github.com/MayukXT/WAren6/releases/download/reader-v")
}

fn portable_update_helper_args(
    helper_path: &Path,
    process_id: u32,
    current_exe: &Path,
    new_exe: &Path,
    backup_exe: &Path,
    log_path: &Path,
) -> Vec<String> {
    vec![
        "-NoProfile".to_string(),
        "-ExecutionPolicy".to_string(),
        "Bypass".to_string(),
        "-WindowStyle".to_string(),
        "Hidden".to_string(),
        "-File".to_string(),
        helper_path.to_string_lossy().into_owned(),
        "-ProcessId".to_string(),
        process_id.to_string(),
        "-CurrentExe".to_string(),
        current_exe.to_string_lossy().into_owned(),
        "-NewExe".to_string(),
        new_exe.to_string_lossy().into_owned(),
        "-BackupExe".to_string(),
        backup_exe.to_string_lossy().into_owned(),
        "-LogFile".to_string(),
        log_path.to_string_lossy().into_owned(),
    ]
}

fn write_portable_update_helper(
    helper_path: &Path,
    current_exe: &Path,
    new_exe: &Path,
    backup_exe: &Path,
    log_path: &Path,
) -> Result<(), String> {
    let script = r#"
param(
    [Parameter(Mandatory=$true)][int]$ProcessId,
    [Parameter(Mandatory=$true)][string]$CurrentExe,
    [Parameter(Mandatory=$true)][string]$NewExe,
    [Parameter(Mandatory=$true)][string]$BackupExe,
    [Parameter(Mandatory=$true)][string]$LogFile
)

$ErrorActionPreference = 'Stop'

function Write-UpdateLog([string]$Message) {
    $line = "$(Get-Date -Format o) $Message"
    Add-Content -LiteralPath $LogFile -Value $line
}

try {
    Wait-Process -Id $ProcessId -Timeout 30 -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500

    if (Test-Path -LiteralPath $BackupExe) {
        Remove-Item -LiteralPath $BackupExe -Force
    }

    Move-Item -LiteralPath $CurrentExe -Destination $BackupExe -Force
    try {
        Move-Item -LiteralPath $NewExe -Destination $CurrentExe -Force
        Start-Process -FilePath $CurrentExe
        Remove-Item -LiteralPath $BackupExe -Force -ErrorAction SilentlyContinue
        Write-UpdateLog 'Portable Reader update completed.'
    } catch {
        if (Test-Path -LiteralPath $BackupExe) {
            Move-Item -LiteralPath $BackupExe -Destination $CurrentExe -Force
        }
        throw
    }
} catch {
    Write-UpdateLog "Portable Reader update failed: $($_.Exception.Message)"
}
"#;

    fs::write(helper_path, script)
        .map_err(|e| format!("Failed to write portable update helper: {e}"))?;
    let _ = current_exe;
    let _ = new_exe;
    let _ = backup_exe;
    let _ = log_path;
    Ok(())
}

/// Borrow the cached connection immutably for queries.
fn with_db<F, T>(state: &State<'_, AppState>, f: F) -> Result<T, String>
where
    F: FnOnce(&Connection) -> Result<T, String>,
{
    let guard = state.db_conn.lock().unwrap();
    let conn = guard
        .as_ref()
        .ok_or("No database loaded. Please open a unified_whatsapp.db file.")?;
    f(conn)
}

fn with_db_and_cache<F, T>(state: &State<'_, AppState>, f: F) -> Result<T, String>
where
    F: FnOnce(&Connection, Option<&Connection>) -> Result<T, String>,
{
    let db_guard = state.db_conn.lock().unwrap();
    let conn = db_guard
        .as_ref()
        .ok_or("No database loaded. Please open a unified_whatsapp.db file.")?;
    let cache_guard = state.cache_conn.lock().unwrap();
    f(conn, cache_guard.as_ref())
}

fn sha256_file(path: &str) -> Result<String, String> {
    let mut file = fs::File::open(path).map_err(|e| format!("Failed to hash DB: {e}"))?;
    let mut hasher = Sha256::new();
    let mut buf = [0u8; 1024 * 1024];
    loop {
        let n = file
            .read(&mut buf)
            .map_err(|e| format!("Failed to read DB for hashing: {e}"))?;
        if n == 0 {
            break;
        }
        hasher.update(&buf[..n]);
    }
    Ok(format!("{:x}", hasher.finalize()))
}

#[tauri::command]
fn get_install_type() -> Result<String, String> {
    let exe_path = std::env::current_exe()
        .map_err(|e| format!("Failed to resolve current executable: {e}"))?;
    Ok(detect_install_type_for_path(&exe_path).to_string())
}

#[tauri::command]
fn get_app_info() -> Result<ReaderAppInfo, String> {
    let exe_path = std::env::current_exe()
        .map_err(|e| format!("Failed to resolve current executable: {e}"))?;
    let safety = portable_update_safety_for_path(&exe_path, parent_folder_is_writable(&exe_path));
    Ok(ReaderAppInfo {
        version: env!("CARGO_PKG_VERSION").to_string(),
        install_type: detect_install_type_for_path(&exe_path).to_string(),
        current_exe_path: Some(exe_path.to_string_lossy().into_owned()),
        exe_path_is_safe: safety.safe,
        exe_path_status: safety.reason,
        app_identifier: APP_IDENTIFIER.to_string(),
    })
}

#[tauri::command]
async fn install_installed_update(app: tauri::AppHandle) -> Result<(), String> {
    use tauri_plugin_updater::UpdaterExt;

    let Some(update) = app
        .updater()
        .map_err(|e| format!("Failed to initialize updater: {e}"))?
        .check()
        .await
        .map_err(|e| format!("Failed to check for Reader update: {e}"))?
    else {
        return Err("No Reader update is available.".to_string());
    };

    update
        .download_and_install(|_, _| {}, || {})
        .await
        .map_err(|e| format!("Failed to install Reader update: {e}"))?;
    app.restart();
}

#[tauri::command]
async fn install_portable_update(
    app: tauri::AppHandle,
    download_url: String,
    sha256: String,
    version: String,
) -> Result<(), String> {
    if !allowed_release_download_url(&download_url) {
        return Err("Portable update URL is not from the WAren6 GitHub release.".to_string());
    }
    if version
        .chars()
        .any(|ch| !(ch.is_ascii_alphanumeric() || ch == '.' || ch == '-' || ch == '_'))
    {
        return Err("Portable update version contains unsupported characters.".to_string());
    }

    let exe_path = std::env::current_exe()
        .map_err(|e| format!("Failed to resolve current executable: {e}"))?;
    if detect_install_type_for_path(&exe_path) != "portable" {
        return Err(
            "Portable replacement is only available for the portable Reader EXE.".to_string(),
        );
    }

    let safety = portable_update_safety_for_path(&exe_path, parent_folder_is_writable(&exe_path));
    if !safety.safe {
        return Err(safety
            .reason
            .unwrap_or_else(|| "Current Reader EXE cannot be replaced safely.".to_string()));
    }

    let expected_sha256 = normalize_sha256(&sha256);
    if expected_sha256.len() != 64 || !expected_sha256.chars().all(|ch| ch.is_ascii_hexdigit()) {
        return Err("Portable update SHA-256 is not valid.".to_string());
    }

    let update_dir = std::env::temp_dir().join(format!("waren6-reader-update-{version}"));
    fs::create_dir_all(&update_dir)
        .map_err(|e| format!("Failed to create update temp folder: {e}"))?;
    let new_exe = update_dir.join(format!("WAren6-Reader-Portable-v{version}.exe"));
    let helper_path = update_dir.join("replace-waren6-reader.ps1");
    let log_path = update_dir.join("portable-update.log");
    let backup_exe = exe_path.with_file_name(format!(
        "{}.waren6-update-backup",
        exe_path
            .file_name()
            .and_then(|name| name.to_str())
            .unwrap_or("WAren6-Reader.exe")
    ));

    let download_target = new_exe.clone();
    tauri::async_runtime::spawn_blocking(move || -> Result<(), String> {
        let mut response = reqwest::blocking::get(&download_url)
            .map_err(|e| format!("Failed to download portable Reader update: {e}"))?;
        if !response.status().is_success() {
            return Err(format!(
                "Portable Reader update download returned HTTP {}",
                response.status()
            ));
        }
        let mut file = fs::File::create(&download_target)
            .map_err(|e| format!("Failed to create downloaded Reader EXE: {e}"))?;
        std::io::copy(&mut response, &mut file)
            .map_err(|e| format!("Failed to save downloaded Reader EXE: {e}"))?;
        Ok(())
    })
    .await
    .map_err(|e| format!("Portable update task failed: {e}"))??;

    let actual_sha256 = sha256_path(&new_exe)?;
    if actual_sha256 != expected_sha256 {
        let _ = fs::remove_file(&new_exe);
        return Err(
            "Downloaded portable Reader hash did not match WAren6-Reader-latest.json.".to_string(),
        );
    }

    write_portable_update_helper(&helper_path, &exe_path, &new_exe, &backup_exe, &log_path)?;
    Command::new("powershell.exe")
        .args(portable_update_helper_args(
            &helper_path,
            std::process::id(),
            &exe_path,
            &new_exe,
            &backup_exe,
            &log_path,
        ))
        .spawn()
        .map_err(|e| format!("Failed to start portable update helper: {e}"))?;

    app.exit(0);
    Ok(())
}

fn cache_path_for<R: tauri::Runtime>(
    app: &tauri::AppHandle<R>,
    db_hash: &str,
) -> Result<String, String> {
    let dir = app
        .path()
        .app_data_dir()
        .map_err(|e| format!("Failed to resolve app data directory: {e}"))?
        .join("search-cache");
    fs::create_dir_all(&dir)
        .map_err(|e| format!("Failed to create search cache directory: {e}"))?;
    Ok(dir
        .join(format!("{db_hash}.sqlite"))
        .to_string_lossy()
        .into_owned())
}

fn build_search_cache<R: tauri::Runtime>(
    app: &tauri::AppHandle<R>,
    source_path: &str,
    source_hash: &str,
    source: &Connection,
) -> Result<Connection, String> {
    let cache_path = cache_path_for(app, source_hash)?;
    build_search_cache_at_path(cache_path, source_path, source_hash, source)
}

fn build_search_cache_at_path(
    cache_path: String,
    source_path: &str,
    source_hash: &str,
    source: &Connection,
) -> Result<Connection, String> {
    let mut cache =
        Connection::open(cache_path).map_err(|e| format!("Failed to open search cache: {e}"))?;
    cache.execute_batch(
        "
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;
        CREATE TABLE IF NOT EXISTS cache_metadata(key TEXT PRIMARY KEY, value TEXT);
        CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(source_rowid UNINDEXED, text);
        CREATE TABLE IF NOT EXISTS visible_message_order(
            rowid INTEGER PRIMARY KEY,
            chat_jid TEXT NOT NULL,
            timestamp INTEGER NOT NULL,
            msg_id TEXT,
            msg_key TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_visible_message_order_chat_ts ON visible_message_order(chat_jid, timestamp, rowid);
        CREATE INDEX IF NOT EXISTS idx_visible_message_order_chat_msgid_ts ON visible_message_order(chat_jid, msg_id, timestamp, rowid);
        CREATE INDEX IF NOT EXISTS idx_visible_message_order_msgid_ts ON visible_message_order(msg_id, timestamp, rowid);
        CREATE INDEX IF NOT EXISTS idx_visible_message_order_msg_key ON visible_message_order(msg_key);
        ",
    ).map_err(|e| format!("Failed to initialize search cache: {e}"))?;

    let existing_hash: Option<String> = cache
        .query_row(
            "SELECT value FROM cache_metadata WHERE key='source_sha256'",
            [],
            |r| r.get(0),
        )
        .optional()
        .map_err(|e| e.to_string())?;
    let existing_path: Option<String> = cache
        .query_row(
            "SELECT value FROM cache_metadata WHERE key='source_path'",
            [],
            |r| r.get(0),
        )
        .optional()
        .map_err(|e| e.to_string())?;
    let existing_schema: Option<String> = cache
        .query_row(
            "SELECT value FROM cache_metadata WHERE key='reader_cache_schema'",
            [],
            |r| r.get(0),
        )
        .optional()
        .map_err(|e| e.to_string())?;

    if existing_hash.as_deref() != Some(source_hash)
        || existing_path.as_deref() != Some(source_path)
        || existing_schema.as_deref() != Some(SEARCH_CACHE_SCHEMA_VERSION)
    {
        let tx = cache.transaction().map_err(|e| e.to_string())?;
        tx.execute("DELETE FROM messages_fts", [])
            .map_err(|e| e.to_string())?;
        tx.execute("DELETE FROM visible_message_order", [])
            .map_err(|e| e.to_string())?;
        {
            let visible_messages = visible_messages_subquery(source)?;
            let mut insert = tx
                .prepare("INSERT INTO messages_fts(source_rowid, text) VALUES (?, ?)")
                .map_err(|e| e.to_string())?;
            let can_cache_order = table_column_exists(source, "messages", "chat_jid")?
                && table_column_exists(source, "messages", "timestamp")?;
            if can_cache_order {
                let msg_id_expr = if table_column_exists(source, "messages", "msg_id")? {
                    "msg_id"
                } else {
                    "NULL AS msg_id"
                };
                let msg_key_expr = if table_column_exists(source, "messages", "msg_key")? {
                    "msg_key"
                } else {
                    "NULL AS msg_key"
                };
                let source_sql = format!(
                    "SELECT rowid, text, chat_jid, COALESCE(timestamp, 0), {msg_id_expr}, {msg_key_expr}
                     FROM {visible_messages}",
                    visible_messages = visible_messages,
                    msg_id_expr = msg_id_expr,
                    msg_key_expr = msg_key_expr,
                );
                let mut src_stmt = source.prepare(&source_sql).map_err(|e| e.to_string())?;
                let mut order_insert = tx
                    .prepare("INSERT OR REPLACE INTO visible_message_order(rowid, chat_jid, timestamp, msg_id, msg_key) VALUES (?, ?, ?, ?, ?)")
                    .map_err(|e| e.to_string())?;
                let rows = src_stmt
                    .query_map([], |r| {
                        Ok((
                            r.get::<_, i64>(0)?,
                            r.get::<_, Option<String>>(1)?,
                            r.get::<_, String>(2)?,
                            r.get::<_, i64>(3)?,
                            r.get::<_, Option<String>>(4)?,
                            r.get::<_, Option<String>>(5)?,
                        ))
                    })
                    .map_err(|e| e.to_string())?;
                for row in rows {
                    let (rowid, text, chat_jid, timestamp, msg_id, msg_key) =
                        row.map_err(|e| e.to_string())?;
                    order_insert
                        .execute(rusqlite::params![
                            rowid, chat_jid, timestamp, msg_id, msg_key
                        ])
                        .map_err(|e| e.to_string())?;
                    if let Some(text) = text {
                        if !text.trim().is_empty() {
                            insert.execute((&rowid, &text)).map_err(|e| e.to_string())?;
                        }
                    }
                }
            } else {
                let source_sql = format!(
                    "SELECT rowid, text FROM {visible_messages} WHERE text IS NOT NULL AND TRIM(text) <> ''",
                    visible_messages = visible_messages,
                );
                let mut src_stmt = source.prepare(&source_sql).map_err(|e| e.to_string())?;
                let rows = src_stmt
                    .query_map([], |r| Ok((r.get::<_, i64>(0)?, r.get::<_, String>(1)?)))
                    .map_err(|e| e.to_string())?;
                for row in rows {
                    let (rowid, text) = row.map_err(|e| e.to_string())?;
                    insert.execute((&rowid, &text)).map_err(|e| e.to_string())?;
                }
            }
        }
        tx.execute(
            "INSERT OR REPLACE INTO cache_metadata(key, value) VALUES ('source_sha256', ?)",
            [source_hash],
        )
        .map_err(|e| e.to_string())?;
        tx.execute(
            "INSERT OR REPLACE INTO cache_metadata(key, value) VALUES ('source_path', ?)",
            [source_path],
        )
        .map_err(|e| e.to_string())?;
        tx.execute(
            "INSERT OR REPLACE INTO cache_metadata(key, value) VALUES ('reader_cache_schema', ?)",
            [SEARCH_CACHE_SCHEMA_VERSION],
        )
        .map_err(|e| e.to_string())?;
        tx.commit().map_err(|e| e.to_string())?;
    }
    Ok(cache)
}

fn message_from_row(r: &Row<'_>) -> rusqlite::Result<Message> {
    Ok(Message {
        rowid: r.get(0)?,
        msg_id: r.get(1)?,
        chat_jid: r.get(2)?,
        from_me: r.get(3)?,
        sender_jid: r.get(4)?,
        sender_name: r.get(5)?,
        sender_phone: r.get(6)?,
        timestamp: r.get::<_, i64>(7).unwrap_or(0),
        text: r.get(8)?,
        is_group: r.get::<_, i64>(9).unwrap_or(0) != 0,
        msg_key: r.get(10)?,
        msg_type: r.get(11)?,
        quoted_stanza_id: r.get(12)?,
        quoted_participant: r.get(13)?,
        quoted_msg_body: r.get(14)?,
        quoted_msg_type: r.get(15)?,
        call_duration: r.get(16)?,
        call_outcome: r.get(17)?,
        is_video_call: r.get::<_, i64>(18).unwrap_or(0) != 0,
        media_mime_type: r.get(19)?,
        media_filename: r.get(20)?,
        media_size: r.get(21)?,
        media_case_path: r.get(22).ok(),
        media_sha256: r.get(23).ok(),
        media_status: r.get(24).ok(),
        body_status: r.get(25).ok(),
        is_edited: r.get::<_, i64>(26).unwrap_or(0) != 0,
        edited_at: r.get(27).ok(),
        edit_count: r.get::<_, i64>(28).unwrap_or(0),
        edit_history_status: r.get(29).ok(),
    })
}

fn table_column_exists(
    conn: &Connection,
    table_name: &str,
    column_name: &str,
) -> Result<bool, String> {
    let escaped_table = table_name.replace('"', "\"\"");
    let sql = format!("PRAGMA table_info(\"{escaped_table}\")");
    let mut stmt = conn.prepare(&sql).map_err(|e| e.to_string())?;
    let rows = stmt
        .query_map([], |r| r.get::<_, String>(1))
        .map_err(|e| e.to_string())?;
    for row in rows {
        if row.map_err(|e| e.to_string())? == column_name {
            return Ok(true);
        }
    }
    Ok(false)
}

fn visible_messages_subquery(conn: &Connection) -> Result<String, String> {
    let has_source = table_column_exists(conn, "messages", "source")?;
    let has_source_recovery = table_column_exists(conn, "messages", "source_recovery")?;
    let mut hidden_predicates: Vec<&str> = Vec::new();

    if has_source && has_source_recovery {
        hidden_predicates.push(
            "
            (
                COALESCE(m0.source, '') = 'genericStorage'
                AND COALESCE(m0.source_recovery, '') = 'sqlite_recovered_row'
                AND NULLIF(m0.text, '') IS NOT NULL
                AND EXISTS (
                    SELECT 1
                    FROM messages keyed
                    WHERE keyed.rowid <> m0.rowid
                      AND keyed.msg_key IS NOT NULL
                      AND COALESCE(keyed.source, '') <> 'genericStorage'
                      AND keyed.chat_jid = m0.chat_jid
                      AND COALESCE(keyed.timestamp, 0) = COALESCE(m0.timestamp, 0)
                      AND (
                          COALESCE(keyed.text, '') = COALESCE(m0.text, '')
                          OR (
                              NULLIF(keyed.text, '') IS NOT NULL
                              AND LENGTH(keyed.text) >= 12
                              AND (
                                  keyed.text LIKE 'http://%'
                                  OR keyed.text LIKE 'https://%'
                              )
                              AND INSTR(COALESCE(m0.text, ''), keyed.text) > 0
                          )
                      )
                      AND (
                          m0.from_me IS NULL
                          OR COALESCE(keyed.from_me, -1) = COALESCE(m0.from_me, -1)
                      )
                )
            )
        ",
        );
    }

    let has_protocol_columns = ["msg_type", "text", "chat_jid", "timestamp", "from_me"]
        .iter()
        .map(|column| table_column_exists(conn, "messages", column))
        .collect::<Result<Vec<_>, _>>()?
        .into_iter()
        .all(|exists| exists);
    if has_protocol_columns {
        hidden_predicates.push(
            "
            (
                COALESCE(m0.msg_type, '') = 'protocol'
                AND NULLIF(m0.text, '') IS NOT NULL
                AND EXISTS (
                    SELECT 1
                    FROM messages visible
                    WHERE visible.rowid <> m0.rowid
                      AND visible.chat_jid = m0.chat_jid
                      AND COALESCE(visible.text, '') = COALESCE(m0.text, '')
                      AND COALESCE(visible.msg_type, '') NOT IN (
                          'protocol','e2e_notification','notification_template',
                          'ciphertext','revoked','gp2','broadcast'
                      )
                      AND ABS(COALESCE(visible.timestamp, 0) - COALESCE(m0.timestamp, 0)) <= 300
                      AND (
                          m0.from_me IS NULL
                          OR visible.from_me IS NULL
                          OR COALESCE(visible.from_me, -1) = COALESCE(m0.from_me, -1)
                      )
                )
            )
        ",
        );
    }

    if table_exists(conn, "message_edits")? {
        hidden_predicates.push(
            "
            (
                m0.msg_key IS NOT NULL
                AND EXISTS (
                    SELECT 1
                    FROM message_edits edit
                    WHERE edit.edit_event_msg_key = m0.msg_key
                      AND edit.target_msg_key IS NOT NULL
                )
            )
        ",
        );
    }

    if hidden_predicates.is_empty() {
        return Ok("(SELECT m0.rowid AS rowid, m0.* FROM messages m0)".to_string());
    }

    Ok(format!(
        "
        (
            SELECT m0.rowid AS rowid, m0.*
            FROM messages m0
            WHERE NOT ({hidden_predicates})
        )
    ",
        hidden_predicates = hidden_predicates.join(" OR ")
    ))
}

fn message_select_sql() -> &'static str {
    "
        SELECT
            m.rowid, m.msg_id, m.chat_jid, m.from_me,
            m.sender_jid,
            COALESCE(m.sender_name, cnt_lid.contact_name, cnt_phone.contact_name, cnt_num.contact_name, cnt_lid.push_name, cnt_phone.push_name, cnt_num.push_name, cnt_lid.short_name, cnt_phone.short_name, cnt_num.short_name) AS sender_name,
            COALESCE(m.sender_phone, cnt_lid.phone_number, cnt_phone.phone_number) AS sender_phone,
            m.timestamp, m.text, m.is_group, m.msg_key,
            m.msg_type,
            m.quoted_stanza_id, m.quoted_participant, m.quoted_msg_body, m.quoted_msg_type,
            m.call_duration, m.call_outcome, m.is_video_call,
            m.media_mime_type, m.media_filename, m.media_size,
            m.media_case_path, m.media_sha256, m.media_status, m.body_status
    "
}

fn message_select_sql_from(conn: &Connection, from_sql: &str) -> Result<String, String> {
    let has_edit_columns = [
        "is_edited",
        "edited_at",
        "edit_count",
        "edit_history_status",
    ]
    .iter()
    .map(|column| table_column_exists(conn, "messages", column))
    .collect::<Result<Vec<_>, _>>()?
    .into_iter()
    .all(|exists| exists);
    let edit_columns = if has_edit_columns {
        "COALESCE(m.is_edited, 0) AS is_edited,
         m.edited_at,
         COALESCE(m.edit_count, 0) AS edit_count,
         m.edit_history_status"
    } else {
        "0 AS is_edited,
         NULL AS edited_at,
         0 AS edit_count,
         NULL AS edit_history_status"
    };
    Ok(format!("{}, {}
        FROM {} m
        LEFT JOIN contacts cnt_lid   ON cnt_lid.lid        = m.sender_jid
        LEFT JOIN contacts cnt_phone ON cnt_phone.phone_jid = m.sender_jid
        LEFT JOIN contacts cnt_num   ON cnt_num.phone_number = m.sender_phone AND m.sender_phone IS NOT NULL
    ", message_select_sql(), edit_columns, from_sql))
}

fn message_select_sql_owned(conn: &Connection) -> Result<String, String> {
    let visible_messages = visible_messages_subquery(conn)?;
    message_select_sql_from(conn, &visible_messages)
}

fn message_select_sql_base(conn: &Connection) -> Result<String, String> {
    message_select_sql_from(conn, "messages")
}

fn media_kind_for(msg_type: Option<&str>, mime_type: Option<&str>) -> &'static str {
    let msg = msg_type.unwrap_or("").to_ascii_lowercase();
    let mime = mime_type.unwrap_or("").to_ascii_lowercase();

    match msg.as_str() {
        "sticker" => "sticker",
        "image" | "album" | "gif" => "image",
        "video" | "ptv" => "video",
        "ptt" | "audio" => "audio",
        "document" => "document",
        _ if mime.starts_with("image/") => "image",
        _ if mime.starts_with("video/") => "video",
        _ if mime.starts_with("audio/") => "audio",
        _ if mime.starts_with("application/") => "document",
        _ if msg == "interactive" && !mime.is_empty() => {
            if mime.starts_with("image/") {
                "image"
            } else if mime.starts_with("video/") {
                "video"
            } else {
                "document"
            }
        }
        _ => "other",
    }
}

fn media_message_where_sql() -> &'static str {
    "
        (
            m.media_filename IS NOT NULL AND TRIM(m.media_filename) <> ''
            OR m.media_mime_type IS NOT NULL AND TRIM(m.media_mime_type) <> ''
            OR COALESCE(m.msg_type, '') IN ('image','video','sticker','ptt','audio','ptv','document','album','gif','interactive')
            OR m.body_status = 'media_only'
            OR m.media_status IS NOT NULL
        )
    "
}

fn media_message_count_sql() -> &'static str {
    "
        (
            media_filename IS NOT NULL AND TRIM(media_filename) <> ''
            OR media_mime_type IS NOT NULL AND TRIM(media_mime_type) <> ''
            OR COALESCE(msg_type, '') IN ('image','video','sticker','ptt','audio','ptv','document','album','gif','interactive')
            OR body_status = 'media_only'
            OR media_status IS NOT NULL
        )
    "
}

fn call_message_where_sql() -> &'static str {
    "
        (
            COALESCE(m.msg_type, '') = 'call_log'
            OR COALESCE(m.body_status, '') = 'call_event'
            OR m.call_outcome IS NOT NULL
            OR m.call_duration IS NOT NULL
        )
    "
}

fn call_outcome_tone(outcome: Option<&str>, duration: Option<i64>) -> &'static str {
    let raw = outcome.unwrap_or("").to_ascii_lowercase();
    if raw.contains("missed") || raw == "2" || raw == "missed_call" {
        return "missed";
    }
    if raw.contains("rejected") || raw.contains("declined") || raw == "3" {
        return "declined";
    }
    if raw.contains("accepted")
        || raw.contains("answered")
        || raw.contains("completed")
        || raw == "1"
        || duration.unwrap_or(0) > 0
    {
        return "answered";
    }
    "neutral"
}

fn db_case_root(state: &State<AppState>) -> Result<PathBuf, String> {
    let path = state
        .db_path
        .lock()
        .unwrap()
        .clone()
        .ok_or_else(|| "No database is open.".to_string())?;
    let db = PathBuf::from(path);
    db.parent()
        .map(|p| p.to_path_buf())
        .ok_or_else(|| "Unable to resolve database folder.".to_string())
}

fn resolve_case_media_path(state: &State<AppState>, path: &str) -> Result<PathBuf, String> {
    let raw = PathBuf::from(path);
    let candidate = if raw.is_absolute() {
        raw
    } else {
        db_case_root(state)?.join(raw)
    };
    let canonical = candidate
        .canonicalize()
        .map_err(|e| format!("Media file was not found: {e}"))?;
    let root = db_case_root(state)?
        .canonicalize()
        .map_err(|e| format!("Case folder was not found: {e}"))?;
    if !canonical.starts_with(root) {
        return Err("Refusing to open a media path outside the current WAren6 case.".to_string());
    }
    Ok(canonical)
}

fn build_fts_query(query: &str) -> Option<String> {
    let tokens: Vec<String> = query
        .split_whitespace()
        .filter_map(|term| {
            let token: String = term
                .chars()
                .filter(|ch| ch.is_alphanumeric() || *ch == '_')
                .collect();
            if token.is_empty() {
                None
            } else {
                Some(format!("{token}*"))
            }
        })
        .collect();

    if tokens.is_empty() {
        None
    } else {
        Some(tokens.join(" "))
    }
}

// ---------------------------------------------------------------------------
// Commands
// ---------------------------------------------------------------------------

#[tauri::command]
fn pick_db_file(app: tauri::AppHandle) -> Result<Option<String>, String> {
    let file = app
        .dialog()
        .file()
        .add_filter("WAren6 Unified Database", &["db"])
        .blocking_pick_file();
    Ok(file.map(|f| f.into_path().unwrap().to_string_lossy().into_owned()))
}

/// Also supports picking the containing folder (for backward compat).
/// If a folder is picked, we look for `unified_whatsapp.db` inside it.
#[tauri::command]
fn pick_folder(app: tauri::AppHandle) -> Result<Option<String>, String> {
    let folder = app.dialog().file().blocking_pick_folder();
    Ok(folder.map(|f| f.into_path().unwrap().to_string_lossy().into_owned()))
}

#[tauri::command]
fn set_db_path(path: String, app: tauri::AppHandle, state: State<AppState>) -> Result<(), String> {
    let db_hash = sha256_file(&path)?;
    let conn = Connection::open_with_flags(
        &path,
        OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_NO_MUTEX,
    )
    .map_err(|e| format!("Failed to open DB read-only: {e}"))?;
    let _ = conn.execute_batch(
        "
        PRAGMA query_only=ON;
        PRAGMA cache_size=-32000;
        PRAGMA temp_store=MEMORY;
        PRAGMA mmap_size=268435456;
    ",
    );
    let cache = build_search_cache(&app, &path, &db_hash, &conn)?;
    {
        let mut conn_lock = state.db_conn.lock().unwrap();
        *conn_lock = Some(conn);
    }
    {
        let mut cache_lock = state.cache_conn.lock().unwrap();
        *cache_lock = Some(cache);
    }
    {
        let mut hash_lock = state.db_sha256.lock().unwrap();
        *hash_lock = Some(db_hash);
    }
    {
        let mut path_lock = state.db_path.lock().unwrap();
        *path_lock = Some(path);
    }
    Ok(())
}

#[tauri::command]
fn get_db_path(state: State<AppState>) -> Result<Option<String>, String> {
    Ok(state.db_path.lock().unwrap().clone())
}

/// Validate the database has the unified schema and return extraction info.
#[tauri::command]
fn validate_db(state: State<AppState>) -> Result<ExtractionInfo, String> {
    with_db(&state, |conn| {
        // Check the key table exists
        conn.query_row(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='messages'",
            [],
            |_| Ok(()),
        )
        .optional()
        .map_err(|e| e.to_string())?
        .ok_or(
            "This does not appear to be a unified_whatsapp.db file (messages table missing)."
                .to_string(),
        )?;

        let mut info = ExtractionInfo {
            extraction_time: None,
            self_phone: None,
            total_messages: None,
            messages_sent: None,
            messages_received: None,
            total_contacts: None,
            resolved_contacts: None,
            total_chats: None,
        };

        let mut stmt = conn
            .prepare(
                "SELECT key, value FROM extraction_metadata WHERE key IN (
                'extraction_time','self_phone','total_messages',
                'messages_sent','messages_received','total_contacts',
                'resolved_contacts','total_chats'
            )",
            )
            .map_err(|e| e.to_string())?;

        let rows = stmt
            .query_map([], |r| Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?)))
            .map_err(|e| e.to_string())?;

        for row in rows.flatten() {
            match row.0.as_str() {
                "extraction_time" => info.extraction_time = Some(row.1),
                "self_phone" => info.self_phone = Some(row.1),
                "total_messages" => info.total_messages = Some(row.1),
                "messages_sent" => info.messages_sent = Some(row.1),
                "messages_received" => info.messages_received = Some(row.1),
                "total_contacts" => info.total_contacts = Some(row.1),
                "resolved_contacts" => info.resolved_contacts = Some(row.1),
                "total_chats" => info.total_chats = Some(row.1),
                _ => {}
            }
        }

        Ok(info)
    })
}

#[tauri::command]
fn get_chats(state: State<AppState>) -> Result<Vec<Chat>, String> {
    with_db(&state, query_chats)
}

fn query_chats(conn: &Connection) -> Result<Vec<Chat>, String> {
    // last_msg returns a meaningful media label instead of NULL when the most
    // recent message has no text (sticker/ptt/image/etc.).
    let visible_messages = visible_messages_subquery(conn)?;
    let sql = format!("
        SELECT
            c.chat_jid,
            COALESCE(
                NULLIF(g.subject, ''),
                NULLIF(c.chat_name, ''),
                cnt_lid.contact_name, cnt_phone.contact_name, cnt_num.contact_name,
                cnt_lid.push_name, cnt_phone.push_name, cnt_num.push_name,
                cnt_lid.short_name, cnt_phone.short_name, cnt_num.short_name
            ) AS chat_name,
            c.chat_phone,
            c.is_group,
            COALESCE(c.is_newsletter, 0),
            MAX(m.timestamp)       AS last_ts,
            (SELECT
                CASE
                    WHEN text IS NOT NULL AND TRIM(text) != '' THEN text
                    WHEN msg_type IN ('image','album') THEN '[Image]'
                    WHEN msg_type IN ('video','ptv')   THEN '[Video]'
                    WHEN msg_type = 'ptt'              THEN '[Voice message]'
                    WHEN msg_type = 'audio'            THEN '[Audio]'
                    WHEN msg_type = 'sticker'          THEN '[Sticker]'
                    WHEN msg_type = 'document'         THEN '[Document]'
                    ELSE NULL
                END
             FROM {visible_messages} lm WHERE lm.chat_jid = c.chat_jid
             AND msg_type NOT IN (
                 'call_log','e2e_notification','notification_template',
                 'ciphertext','protocol','revoked','gp2','broadcast'
             )
             ORDER BY timestamp DESC LIMIT 1) AS last_msg,
            COUNT(m.rowid)         AS msg_count,
            SUM(CASE WHEN m.from_me = 1 THEN 1 ELSE 0 END) AS sent,
            SUM(CASE WHEN m.from_me = 0 THEN 1 ELSE 0 END) AS recv,
            COALESCE(c.unread_count, 0)
        FROM chats c
        LEFT JOIN groups g ON g.group_jid = c.chat_jid
        LEFT JOIN {visible_messages} m ON c.chat_jid = m.chat_jid
        LEFT JOIN contacts cnt_lid ON cnt_lid.lid = c.chat_jid
        LEFT JOIN contacts cnt_phone ON cnt_phone.phone_jid = c.chat_jid
        LEFT JOIN contacts cnt_num ON cnt_num.phone_number = c.chat_phone AND c.chat_phone IS NOT NULL
        GROUP BY c.chat_jid
        ORDER BY last_ts DESC NULLS LAST
    ");
    let mut stmt = conn.prepare(&sql).map_err(|e| e.to_string())?;

    let chats = stmt
        .query_map([], |r| {
            Ok(Chat {
                chat_jid: r.get(0)?,
                chat_name: r.get(1)?,
                chat_phone: r.get(2)?,
                is_group: r.get::<_, i64>(3).unwrap_or(0) != 0,
                is_newsletter: r.get::<_, i64>(4).unwrap_or(0) != 0,
                last_msg_ts: r.get::<_, i64>(5).unwrap_or(0),
                last_msg: r.get(6)?,
                message_count: r.get(7).unwrap_or(0),
                sent_count: r.get(8).unwrap_or(0),
                recv_count: r.get(9).unwrap_or(0),
                unread_count: r.get(10).unwrap_or(0),
            })
        })
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();

    Ok(chats)
}

#[tauri::command]
fn get_messages(chat_jid: String, state: State<AppState>) -> Result<Vec<Message>, String> {
    with_db(&state, |conn| {
        let sql = message_select_sql_owned(conn)?
            + "
            WHERE m.chat_jid = ?
            ORDER BY m.timestamp ASC, m.rowid ASC
        ";
        let mut stmt = conn.prepare(&sql).map_err(|e| e.to_string())?;

        let msgs = stmt
            .query_map([chat_jid], |r| message_from_row(r))
            .map_err(|e| e.to_string())?
            .filter_map(|r| r.ok())
            .collect();

        Ok(msgs)
    })
}

#[tauri::command]
fn get_contact_info(
    chat_jid: String,
    state: State<AppState>,
) -> Result<Option<ContactInfo>, String> {
    with_db(&state, |conn| {
        let result = conn
            .query_row(
                "SELECT lid, phone_number, phone_jid, contact_name, short_name, push_name, is_self
             FROM contacts WHERE lid = ? LIMIT 1",
                [&chat_jid],
                |r| {
                    Ok(ContactInfo {
                        lid: r.get(0)?,
                        phone_number: r.get(1)?,
                        phone_jid: r.get(2)?,
                        contact_name: r.get(3)?,
                        short_name: r.get(4)?,
                        push_name: r.get(5)?,
                        is_self: r.get::<_, i64>(6).unwrap_or(0) != 0,
                    })
                },
            )
            .optional()
            .map_err(|e| e.to_string())?;

        // Fallback: try matching by phone_jid if direct lid failed
        if result.is_some() {
            return Ok(result);
        }

        let fallback = conn
            .query_row(
                "SELECT lid, phone_number, phone_jid, contact_name, short_name, push_name, is_self
             FROM contacts WHERE phone_jid = ? OR phone_number = ? LIMIT 1",
                [&chat_jid, &chat_jid],
                |r| {
                    Ok(ContactInfo {
                        lid: r.get(0)?,
                        phone_number: r.get(1)?,
                        phone_jid: r.get(2)?,
                        contact_name: r.get(3)?,
                        short_name: r.get(4)?,
                        push_name: r.get(5)?,
                        is_self: r.get::<_, i64>(6).unwrap_or(0) != 0,
                    })
                },
            )
            .optional()
            .map_err(|e| e.to_string())?;

        Ok(fallback)
    })
}

#[tauri::command]
fn get_group_participants(
    group_jid: String,
    state: State<AppState>,
) -> Result<Vec<GroupParticipant>, String> {
    with_db(&state, |conn| {
        // Resolve participant names from the contacts table when the group_participants
        // table doesn't have one. Sort: admins first, then saved contacts (those with a
        // real contact_name in the contacts table), then unsaved contacts.
        let mut stmt = conn.prepare("
            SELECT
                gp.group_jid,
                gp.participant_lid,
                COALESCE(gp.participant_phone, cnt_lid.phone_number, cnt_phone.phone_number) AS participant_phone,
                COALESCE(
                    gp.participant_name,
                    cnt_lid.contact_name, cnt_phone.contact_name,
                    cnt_lid.push_name,    cnt_phone.push_name,
                    cnt_lid.short_name,   cnt_phone.short_name
                ) AS participant_name,
                MAX(gp.is_admin) as is_admin,
                -- is_saved: 1 if the contacts table has a non-null contact_name for this person
                CASE WHEN COALESCE(cnt_lid.contact_name, cnt_phone.contact_name) IS NOT NULL THEN 1 ELSE 0 END AS is_saved
            FROM group_participants gp
            LEFT JOIN contacts cnt_lid   ON cnt_lid.lid        = gp.participant_lid
            LEFT JOIN contacts cnt_phone ON cnt_phone.phone_jid = gp.participant_lid
            WHERE gp.group_jid = ?
            GROUP BY COALESCE(gp.participant_phone, gp.participant_lid)
            ORDER BY
                is_admin DESC,
                is_saved DESC,
                participant_name ASC NULLS LAST
        ").map_err(|e| e.to_string())?;

        let participants = stmt
            .query_map([&group_jid], |r| {
                Ok(GroupParticipant {
                    group_jid: r.get(0)?,
                    participant_lid: r.get(1)?,
                    participant_phone: r.get(2)?,
                    participant_name: r.get(3)?,
                    is_admin: r.get::<_, i64>(4).unwrap_or(0) != 0,
                })
            })
            .map_err(|e| e.to_string())?
            .filter_map(|r| r.ok())
            .collect();

        Ok(participants)
    })
}

#[tauri::command]
fn get_group_info(
    group_jid: String,
    state: State<AppState>,
) -> Result<Option<serde_json::Value>, String> {
    with_db(&state, |conn| {
        let result = conn.query_row(
            "SELECT group_jid, subject, description, owner_lid, owner_phone, creation_time, participant_count
             FROM groups WHERE group_jid = ? LIMIT 1",
            [&group_jid],
            |r| {
                Ok(serde_json::json!({
                    "group_jid": r.get::<_, Option<String>>(0).unwrap_or(None),
                    "subject": r.get::<_, Option<String>>(1).unwrap_or(None),
                    "description": r.get::<_, Option<String>>(2).unwrap_or(None),
                    "owner_lid": r.get::<_, Option<String>>(3).unwrap_or(None),
                    "owner_phone": r.get::<_, Option<String>>(4).unwrap_or(None),
                    "creation_time": r.get::<_, Option<i64>>(5).unwrap_or(None),
                    "participant_count": r.get::<_, Option<i64>>(6).unwrap_or(None),
                }))
            },
        ).optional().map_err(|e| e.to_string())?;

        Ok(result)
    })
}

#[tauri::command]
fn get_contact_picture(
    _chat_jid: String,
    _state: State<AppState>,
) -> Result<Option<String>, String> {
    // The unified DB contacts table does NOT store picture blobs.
    // Pictures could come from contacts.dec.db ChatPictures table if present.
    // For now return None — the UI will show initials fallback.
    Ok(None)
}

/// Resolve a participant LID/JID to a human-readable name and phone number.
/// Used by the frontend to resolve quoted_participant in reply bubbles and
/// group message senders when the contact data isn't already loaded.
#[derive(Serialize, Clone)]
pub struct ResolvedParticipant {
    pub jid: String,
    pub name: Option<String>,
    pub phone: Option<String>,
}

#[derive(Serialize, Clone)]
pub struct ResolvedParticipantBatchItem {
    pub input_jid: String,
    pub resolved: Option<ResolvedParticipant>,
}

fn table_exists(conn: &Connection, table_name: &str) -> Result<bool, String> {
    let exists: i64 = conn
        .query_row(
            "SELECT COUNT(1) FROM sqlite_master WHERE type = 'table' AND name = ?1",
            [table_name],
            |r| r.get(0),
        )
        .map_err(|e| e.to_string())?;
    Ok(exists > 0)
}

fn resolve_participant_name_from_conn(
    conn: &Connection,
    jid: &str,
) -> Result<Option<ResolvedParticipant>, String> {
    let raw = jid
        .split('@')
        .next()
        .unwrap_or(jid)
        .trim_start_matches('+')
        .to_string();
    let phone_jid = if raw.chars().all(|c| c.is_ascii_digit()) {
        format!("{raw}@s.whatsapp.net")
    } else {
        raw.clone()
    };

    // Prefer saved contact names. If no saved name exists, the UI should
    // show the phone number instead of a LID/raw JID.
    let result = conn
        .query_row(
            "SELECT
            COALESCE(NULLIF(contact_name, ''), NULLIF(short_name, '')) AS name,
            COALESCE(NULLIF(phone_number, ''), NULLIF(?2, '')) AS phone
         FROM contacts
         WHERE lid IN (?1, ?2)
            OR phone_jid IN (?1, ?2, ?3)
            OR phone_number IN (?1, ?2)
         LIMIT 1",
            rusqlite::params![jid, raw.as_str(), phone_jid.as_str()],
            |r| {
                Ok(ResolvedParticipant {
                    jid: jid.to_string(),
                    name: r.get(0)?,
                    phone: r.get(1)?,
                })
            },
        )
        .optional()
        .map_err(|e| e.to_string())?;

    if result.is_some() {
        return Ok(result);
    }

    if table_exists(conn, "group_participants")? {
        let fallback = conn
            .query_row(
                "SELECT participant_name, participant_phone
             FROM group_participants
             WHERE participant_lid IN (?1, ?2, ?3)
                OR participant_phone IN (?1, ?2)
             LIMIT 1",
                rusqlite::params![jid, raw.as_str(), phone_jid.as_str()],
                |r| {
                    Ok(ResolvedParticipant {
                        jid: jid.to_string(),
                        name: r.get(0)?,
                        phone: r.get(1)?,
                    })
                },
            )
            .optional()
            .map_err(|e| e.to_string())?;

        if fallback.is_some() {
            return Ok(fallback);
        }
    }

    if table_exists(conn, "messages")? {
        let sender_fallback = conn
            .query_row(
                "SELECT
                NULLIF(sender_name, '') AS name,
                NULLIF(sender_phone, '') AS phone
             FROM messages
             WHERE sender_jid IN (?1, ?2, ?3)
               AND (NULLIF(sender_phone, '') IS NOT NULL OR NULLIF(sender_name, '') IS NOT NULL)
             ORDER BY
                CASE WHEN NULLIF(sender_phone, '') IS NOT NULL THEN 0 ELSE 1 END,
                timestamp DESC
             LIMIT 1",
                rusqlite::params![jid, raw.as_str(), phone_jid.as_str()],
                |r| {
                    Ok(ResolvedParticipant {
                        jid: jid.to_string(),
                        name: r.get(0)?,
                        phone: r.get(1)?,
                    })
                },
            )
            .optional()
            .map_err(|e| e.to_string())?;

        if sender_fallback.is_some() {
            return Ok(sender_fallback);
        }
    }

    Ok(None)
}

#[tauri::command]
fn resolve_participant_name(
    jid: String,
    state: State<AppState>,
) -> Result<Option<ResolvedParticipant>, String> {
    with_db(&state, |conn| {
        resolve_participant_name_from_conn(conn, &jid)
    })
}

#[tauri::command]
fn resolve_participant_names(
    jids: Vec<String>,
    state: State<AppState>,
) -> Result<Vec<ResolvedParticipantBatchItem>, String> {
    with_db(&state, |conn| {
        let mut results = Vec::with_capacity(jids.len());
        let mut seen = HashSet::new();
        for jid in jids {
            let jid = jid.trim().to_string();
            if jid.is_empty() || !seen.insert(jid.clone()) {
                continue;
            }
            results.push(ResolvedParticipantBatchItem {
                input_jid: jid.clone(),
                resolved: resolve_participant_name_from_conn(conn, &jid)?,
            });
        }
        Ok(results)
    })
}

#[tauri::command]
fn search_messages(query: String, state: State<AppState>) -> Result<Vec<SearchResult>, String> {
    with_db(&state, |conn| {
        let query = query.trim().to_string();
        if query.is_empty() {
            return Ok(Vec::new());
        }

        let fts_query = build_fts_query(&query);
        let select_sql = message_select_sql_owned(conn)?;
        if let Some(cache_query) = fts_query.clone() {
            let rowids = {
                let cache_guard = state.cache_conn.lock().unwrap();
                if let Some(cache) = cache_guard.as_ref() {
                    let mut stmt = cache
                        .prepare("SELECT source_rowid FROM messages_fts WHERE messages_fts MATCH ? LIMIT 200")
                        .map_err(|e| e.to_string())?;
                    let rows = stmt
                        .query_map([cache_query], |r| r.get::<_, i64>(0))
                        .map_err(|e| e.to_string())?
                        .filter_map(|r| r.ok())
                        .collect::<Vec<_>>();
                    rows
                } else {
                    Vec::new()
                }
            };

            if !rowids.is_empty() {
                let placeholders = std::iter::repeat("?")
                    .take(rowids.len())
                    .collect::<Vec<_>>()
                    .join(",");
                let sql = format!(
                    "{}
                    LEFT JOIN chats c ON m.chat_jid = c.chat_jid
                    WHERE m.rowid IN ({placeholders})
                    ORDER BY m.timestamp DESC
                    LIMIT 200
                ",
                    select_sql
                );
                let params: Vec<&dyn rusqlite::types::ToSql> = rowids
                    .iter()
                    .map(|id| id as &dyn rusqlite::types::ToSql)
                    .collect();
                let mut stmt = conn.prepare(&sql).map_err(|e| e.to_string())?;
                let results = stmt
                    .query_map(params.as_slice(), |r| {
                        Ok(SearchResult {
                            msg: message_from_row(r)?,
                            chat_name: r.get(30)?,
                        })
                    })
                    .map_err(|e| e.to_string())?
                    .filter_map(|r| r.ok())
                    .collect();
                return Ok(results);
            }

            return Ok(Vec::new());
        }

        // Try FTS5 first for fast search, fall back to LIKE
        let raw_fts_available = false;
        let fts_available = raw_fts_available && fts_query.is_some();

        let sql = if fts_available {
            format!(
                "{}
            LEFT JOIN chats c ON m.chat_jid = c.chat_jid
            WHERE m.rowid IN (
                SELECT source_rowid FROM messages_fts WHERE messages_fts MATCH ?
            )
            ORDER BY m.timestamp DESC
            LIMIT 200
            ",
                select_sql.clone()
            )
        } else {
            format!(
                "{}
            LEFT JOIN chats c ON m.chat_jid = c.chat_jid
            WHERE m.text LIKE ?
            ORDER BY m.timestamp DESC
            LIMIT 200
            ",
                select_sql.clone()
            )
        };

        // FTS5 uses token-prefix MATCH syntax for indexed multi-word search.
        let search_param = if fts_available {
            fts_query.clone().unwrap_or_default()
        } else {
            format!("%{}%", query)
        };

        let mut stmt = conn.prepare(&sql).map_err(|e| e.to_string())?;

        let results: Result<Vec<SearchResult>, String> = stmt
            .query_map([search_param.clone()], |r| {
                Ok(SearchResult {
                    msg: message_from_row(r)?,
                    chat_name: r.get(30)?,
                })
            })
            .map_err(|e| e.to_string())?
            .filter_map(|r| r.ok())
            .collect::<Vec<_>>()
            .into_iter()
            .map(Ok)
            .collect();

        // Return indexed FTS results directly. Falling back on empty results makes
        // normal no-match searches scan huge message tables with LIKE.
        match results {
            Ok(r) => Ok(r),
            _ if fts_available => {
                // Fallback to LIKE search
                let pattern = format!("%{}%", query);
                let fallback_sql = format!(
                    "{}
                    LEFT JOIN chats c ON m.chat_jid = c.chat_jid
                    WHERE m.text LIKE ?
                    ORDER BY m.timestamp DESC
                    LIMIT 200
                ",
                    select_sql
                );
                let mut stmt2 = conn.prepare(&fallback_sql).map_err(|e| e.to_string())?;

                let fallback_results = stmt2
                    .query_map([pattern], |r| {
                        Ok(SearchResult {
                            msg: message_from_row(r)?,
                            chat_name: r.get(30)?,
                        })
                    })
                    .map_err(|e| e.to_string())?
                    .filter_map(|r| r.ok())
                    .collect();

                Ok(fallback_results)
            }
            other => other,
        }
    })
}

#[tauri::command]
fn get_message_receipts(
    msg_key: String,
    state: State<AppState>,
) -> Result<Vec<MessageReceipt>, String> {
    with_db(&state, |conn| {
        query_message_receipts_for_visible_key(conn, &msg_key)
    })
}

fn message_receipt_key_filter_sql(conn: &Connection) -> Result<String, String> {
    let can_fold_protocol_receipts = table_exists(conn, "messages")?
        && [
            "msg_key",
            "chat_jid",
            "from_me",
            "timestamp",
            "text",
            "msg_type",
        ]
        .iter()
        .map(|column| table_column_exists(conn, "messages", column))
        .collect::<Result<Vec<_>, _>>()?
        .into_iter()
        .all(|exists| exists);

    if !can_fold_protocol_receipts {
        return Ok("SELECT ?1 AS msg_key".to_string());
    }

    Ok("
        WITH target AS (
            SELECT msg_key, chat_jid, from_me, timestamp, text
            FROM messages
            WHERE msg_key = ?1
            LIMIT 1
        )
        SELECT msg_key FROM target
        UNION
        SELECT echo.msg_key
        FROM messages echo
        JOIN target t ON 1 = 1
        WHERE echo.msg_key IS NOT NULL
          AND echo.msg_key <> t.msg_key
          AND COALESCE(echo.msg_type, '') = 'protocol'
          AND NULLIF(echo.text, '') IS NOT NULL
          AND NULLIF(t.text, '') IS NOT NULL
          AND echo.chat_jid = t.chat_jid
          AND COALESCE(echo.text, '') = COALESCE(t.text, '')
          AND ABS(COALESCE(echo.timestamp, 0) - COALESCE(t.timestamp, 0)) <= 300
          AND (
              t.from_me IS NULL
              OR echo.from_me IS NULL
              OR COALESCE(echo.from_me, -1) = COALESCE(t.from_me, -1)
          )
    "
    .to_string())
}

fn query_message_receipts_for_visible_key(
    conn: &Connection,
    msg_key: &str,
) -> Result<Vec<MessageReceipt>, String> {
    if !table_exists(conn, "message_receipts")? {
        return Ok(Vec::new());
    }

    let key_filter = message_receipt_key_filter_sql(conn)?;
    let sql = format!(
        "
        WITH receipt_keys AS (
            {key_filter}
        )
        SELECT ?1 AS visible_msg_key,
               receiver_jid,
               receiver_phone,
               receiver_name,
               MAX(delivery_time) AS delivery_time,
               MAX(read_time) AS read_time,
               MAX(played_time) AS played_time
        FROM message_receipts
        WHERE msg_key IN (SELECT msg_key FROM receipt_keys)
        GROUP BY
            COALESCE(receiver_jid, ''),
            COALESCE(receiver_phone, ''),
            COALESCE(receiver_name, '')
        ORDER BY
            COALESCE(MAX(read_time), MAX(delivery_time), MAX(played_time), 0) DESC,
            COALESCE(receiver_name, receiver_phone, receiver_jid, '')
    "
    );

    let mut stmt = conn.prepare(&sql).map_err(|e| e.to_string())?;
    let receipts = stmt
        .query_map([msg_key], |r| {
            Ok(MessageReceipt {
                msg_key: r.get(0)?,
                receiver_jid: r.get(1)?,
                receiver_phone: r.get(2)?,
                receiver_name: r.get(3)?,
                delivery_time: r.get(4)?,
                read_time: r.get(5)?,
                played_time: r.get(6)?,
            })
        })
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();

    Ok(receipts)
}

fn query_message_mentions_for_keys(
    conn: &Connection,
    msg_keys: &[String],
) -> Result<Vec<MessageMention>, String> {
    if msg_keys.is_empty() || !table_exists(conn, "message_mentions")? {
        return Ok(Vec::new());
    }
    let mut results = Vec::new();
    for chunk in msg_keys.chunks(500) {
        let placeholders = std::iter::repeat("?")
            .take(chunk.len())
            .collect::<Vec<_>>()
            .join(",");
        let sql = format!(
            "SELECT msg_key, chat_jid, mention_index, kind, target_jid, target_phone,
                    target_name, display_text, source, confidence
             FROM message_mentions
             WHERE msg_key IN ({})
             ORDER BY msg_key, mention_index",
            placeholders
        );
        let params: Vec<&dyn rusqlite::types::ToSql> = chunk
            .iter()
            .map(|k| k as &dyn rusqlite::types::ToSql)
            .collect();
        let mut stmt = conn.prepare(&sql).map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map(params.as_slice(), |r| {
                Ok(MessageMention {
                    msg_key: r.get(0)?,
                    chat_jid: r.get(1)?,
                    mention_index: r.get::<_, Option<i64>>(2)?.unwrap_or(0),
                    kind: r
                        .get::<_, Option<String>>(3)?
                        .unwrap_or_else(|| "unknown".to_string()),
                    target_jid: r.get(4)?,
                    target_phone: r.get(5)?,
                    target_name: r.get(6)?,
                    display_text: r.get(7)?,
                    source: r.get(8)?,
                    confidence: r.get(9)?,
                })
            })
            .map_err(|e| e.to_string())?;
        for row in rows.flatten() {
            results.push(row);
        }
    }
    Ok(results)
}

#[tauri::command]
fn get_message_mentions_for_messages(
    msg_keys: Vec<String>,
    state: State<AppState>,
) -> Result<Vec<MessageMention>, String> {
    with_db(&state, |conn| {
        query_message_mentions_for_keys(conn, &msg_keys)
    })
}

fn query_message_edit_history_for_key(
    conn: &Connection,
    msg_key: &str,
) -> Result<MessageEditHistory, String> {
    let has_edit_columns = [
        "is_edited",
        "edited_at",
        "edit_count",
        "edit_history_status",
    ]
    .iter()
    .map(|column| table_column_exists(conn, "messages", column))
    .collect::<Result<Vec<_>, _>>()?
    .into_iter()
    .all(|exists| exists);
    let target_select = if has_edit_columns {
        "COALESCE(is_edited, 0), edited_at, COALESCE(edit_count, 0), edit_history_status, chat_jid, msg_id"
    } else {
        "0, NULL, 0, NULL, chat_jid, msg_id"
    };
    let target_sql = format!(
        "SELECT {target_select} FROM messages WHERE msg_key = ?1 ORDER BY rowid ASC LIMIT 1"
    );
    let target = conn
        .query_row(&target_sql, [msg_key], |r| {
            Ok((
                r.get::<_, i64>(0).unwrap_or(0) != 0,
                r.get::<_, Option<i64>>(1)?,
                r.get::<_, i64>(2).unwrap_or(0),
                r.get::<_, Option<String>>(3)?,
                r.get::<_, String>(4)?,
                r.get::<_, Option<String>>(5)?,
            ))
        })
        .optional()
        .map_err(|e| e.to_string())?;

    let (is_edited, edited_at, edit_count, history_status, chat_jid, msg_id) =
        target.unwrap_or((false, None, 0, None, String::new(), None));

    let edits = if table_exists(conn, "message_edits")? {
        let mut stmt = conn.prepare(
            "
            SELECT target_msg_key, target_chat_jid, target_msg_id, edit_event_msg_key,
                   COALESCE(edit_index, 0), edited_at, editor_jid, editor_phone,
                   editor_name, previous_text, new_text, source, confidence
            FROM message_edits
            WHERE target_msg_key = ?1
            ORDER BY COALESCE(edit_index, 0), COALESCE(edited_at, 0), COALESCE(edit_event_msg_key, '')
            ",
        ).map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map([msg_key], |r| {
                Ok(MessageEdit {
                    target_msg_key: r.get(0)?,
                    target_chat_jid: r.get(1)?,
                    target_msg_id: r.get(2)?,
                    edit_event_msg_key: r.get(3)?,
                    edit_index: r.get::<_, i64>(4).unwrap_or(0),
                    edited_at: r.get(5)?,
                    editor_jid: r.get(6)?,
                    editor_phone: r.get(7)?,
                    editor_name: r.get(8)?,
                    previous_text: r.get(9)?,
                    new_text: r.get(10)?,
                    source: r.get(11)?,
                    confidence: r.get(12)?,
                })
            })
            .map_err(|e| e.to_string())?
            .filter_map(|r| r.ok())
            .collect();
        rows
    } else {
        Vec::new()
    };

    let quote_snapshots = if let Some(target_msg_id) = msg_id.as_deref() {
        let mut stmt = conn
            .prepare(
                "
            SELECT rowid, msg_key, timestamp, quoted_msg_body, quoted_msg_type
            FROM messages
            WHERE chat_jid = ?1
              AND quoted_stanza_id = ?2
              AND quoted_msg_body IS NOT NULL
              AND TRIM(quoted_msg_body) <> ''
            ORDER BY timestamp ASC, rowid ASC
            LIMIT 200
            ",
            )
            .map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map((&chat_jid, target_msg_id), |r| {
                Ok(QuoteSnapshot {
                    rowid: r.get(0)?,
                    msg_key: r.get(1)?,
                    timestamp: r.get(2)?,
                    quoted_msg_body: r.get(3)?,
                    quoted_msg_type: r.get(4)?,
                })
            })
            .map_err(|e| e.to_string())?
            .filter_map(|r| r.ok())
            .collect();
        rows
    } else {
        Vec::new()
    };

    Ok(MessageEditHistory {
        msg_key: msg_key.to_string(),
        history_status,
        is_edited,
        edited_at,
        edit_count,
        edits,
        quote_snapshots,
    })
}

#[tauri::command]
fn get_message_edit_history(
    msg_key: String,
    state: State<AppState>,
) -> Result<MessageEditHistory, String> {
    with_db(&state, |conn| {
        query_message_edit_history_for_key(conn, &msg_key)
    })
}

fn query_message_reactions_for_keys(
    conn: &Connection,
    msg_keys: &[String],
) -> Result<Vec<MessageReaction>, String> {
    if msg_keys.is_empty() || !table_exists(conn, "reactions")? {
        return Ok(Vec::new());
    }
    let mut results = Vec::new();
    for chunk in msg_keys.chunks(500) {
        let placeholders = std::iter::repeat("?")
            .take(chunk.len())
            .collect::<Vec<_>>()
            .join(",");
        let sql = format!(
            "SELECT r.parent_msg_key, r.sender_jid, r.sender_phone, r.sender_name, r.reaction_text, r.timestamp
             FROM reactions r
             WHERE r.parent_msg_key IN ({})
               AND NULLIF(r.reaction_text, '') IS NOT NULL
               AND NOT EXISTS (
                    SELECT 1
                    FROM reactions newer
                    WHERE newer.parent_msg_key = r.parent_msg_key
                      AND COALESCE(newer.sender_jid, newer.sender_phone, newer.sender_name, '') =
                          COALESCE(r.sender_jid, r.sender_phone, r.sender_name, '')
                      AND (
                            COALESCE(newer.timestamp, 0) > COALESCE(r.timestamp, 0)
                         OR (
                            COALESCE(newer.timestamp, 0) = COALESCE(r.timestamp, 0)
                            AND newer.rowid > r.rowid
                         )
                      )
               )
             ORDER BY r.parent_msg_key, r.timestamp ASC",
            placeholders
        );
        let params: Vec<&dyn rusqlite::types::ToSql> = chunk
            .iter()
            .map(|k| k as &dyn rusqlite::types::ToSql)
            .collect();
        let mut stmt = conn.prepare(&sql).map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map(params.as_slice(), |r| {
                Ok(MessageReaction {
                    parent_msg_key: r.get(0)?,
                    sender_jid: r.get(1)?,
                    sender_phone: r.get(2)?,
                    sender_name: r.get(3)?,
                    reaction_text: r.get(4)?,
                    timestamp: r.get(5)?,
                })
            })
            .map_err(|e| e.to_string())?;
        for row in rows.flatten() {
            results.push(row);
        }
    }
    Ok(results)
}

#[tauri::command]
fn get_reactions_for_messages(
    msg_keys: Vec<String>,
    state: State<AppState>,
) -> Result<Vec<MessageReaction>, String> {
    with_db(&state, |conn| {
        query_message_reactions_for_keys(conn, &msg_keys)
    })
}

/// Batch-query receipt statuses for a list of sent message keys.
/// Returns a per-key status: "read", "delivered", or "sent".
#[tauri::command]
fn get_message_statuses(
    msg_keys: Vec<String>,
    state: State<AppState>,
) -> Result<Vec<MessageStatus>, String> {
    with_db(&state, |conn| {
        query_message_statuses_for_keys(conn, &msg_keys)
    })
}

fn query_message_statuses_for_keys(
    conn: &Connection,
    msg_keys: &[String],
) -> Result<Vec<MessageStatus>, String> {
    if msg_keys.is_empty() || !table_exists(conn, "message_receipts")? {
        return Ok(Vec::new());
    }

    let keys = msg_keys
        .iter()
        .map(|key| key.trim().to_string())
        .filter(|key| !key.is_empty())
        .collect::<HashSet<_>>()
        .into_iter()
        .collect::<Vec<_>>();
    if keys.is_empty() {
        return Ok(Vec::new());
    }

    let placeholders = std::iter::repeat("?")
        .take(keys.len())
        .collect::<Vec<_>>()
        .join(",");
    let params: Vec<&dyn rusqlite::types::ToSql> = keys
        .iter()
        .map(|key| key as &dyn rusqlite::types::ToSql)
        .collect();

    let can_fold_protocol_receipts = table_exists(conn, "messages")?
        && [
            "msg_key",
            "chat_jid",
            "from_me",
            "timestamp",
            "text",
            "msg_type",
        ]
        .iter()
        .map(|column| table_column_exists(conn, "messages", column))
        .collect::<Result<Vec<_>, _>>()?
        .into_iter()
        .all(|exists| exists);

    let sql = if can_fold_protocol_receipts {
        format!(
            "
            WITH target AS (
                SELECT msg_key AS input_key, msg_key, chat_jid, from_me, timestamp, text
                FROM messages
                WHERE msg_key IN ({placeholders})
            ),
            receipt_keys AS (
                SELECT input_key, msg_key FROM target
                UNION
                SELECT t.input_key, echo.msg_key
                FROM messages echo
                JOIN target t ON 1 = 1
                WHERE echo.msg_key IS NOT NULL
                  AND echo.msg_key <> t.msg_key
                  AND COALESCE(echo.msg_type, '') = 'protocol'
                  AND NULLIF(echo.text, '') IS NOT NULL
                  AND NULLIF(t.text, '') IS NOT NULL
                  AND echo.chat_jid = t.chat_jid
                  AND COALESCE(echo.text, '') = COALESCE(t.text, '')
                  AND ABS(COALESCE(echo.timestamp, 0) - COALESCE(t.timestamp, 0)) <= 300
                  AND (
                      t.from_me IS NULL
                      OR echo.from_me IS NULL
                      OR COALESCE(echo.from_me, -1) = COALESCE(t.from_me, -1)
                  )
            )
            SELECT rk.input_key,
                   MAX(CASE WHEN mr.read_time IS NOT NULL OR mr.played_time IS NOT NULL THEN 1 ELSE 0 END) AS has_read,
                   MAX(CASE WHEN mr.delivery_time IS NOT NULL THEN 1 ELSE 0 END) AS has_delivery
            FROM receipt_keys rk
            JOIN message_receipts mr ON mr.msg_key = rk.msg_key
            GROUP BY rk.input_key
            ",
            placeholders = placeholders,
        )
    } else {
        format!(
            "
            SELECT msg_key AS input_key,
                   MAX(CASE WHEN read_time IS NOT NULL OR played_time IS NOT NULL THEN 1 ELSE 0 END) AS has_read,
                   MAX(CASE WHEN delivery_time IS NOT NULL THEN 1 ELSE 0 END) AS has_delivery
            FROM message_receipts
            WHERE msg_key IN ({placeholders})
            GROUP BY msg_key
            ",
            placeholders = placeholders,
        )
    };

    let mut stmt = conn.prepare(&sql).map_err(|e| e.to_string())?;
    let statuses = stmt
        .query_map(params.as_slice(), |r| {
            let has_read = r.get::<_, i64>(1).unwrap_or(0) > 0;
            let has_delivery = r.get::<_, i64>(2).unwrap_or(0) > 0;
            Ok(MessageStatus {
                msg_key: r.get(0)?,
                status: if has_read {
                    "read"
                } else if has_delivery {
                    "delivered"
                } else {
                    "sent"
                }
                .to_string(),
            })
        })
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();

    Ok(statuses)
}

#[tauri::command]
fn search_contacts(
    query: String,
    state: State<AppState>,
) -> Result<Vec<ContactSearchResult>, String> {
    with_db(&state, |conn| {
        let pattern = format!("%{}%", query);

        let mut stmt = conn
            .prepare(
                "
            SELECT DISTINCT
                c.chat_jid,
                COALESCE(c.chat_name, cnt_lid.contact_name, cnt_phone.contact_name,
                         cnt_lid.push_name, cnt_phone.push_name,
                         cnt_lid.short_name, cnt_phone.short_name,
                         c.chat_phone, c.chat_jid) AS display_name,
                COALESCE(c.chat_phone, cnt_lid.phone_number, cnt_phone.phone_number) AS phone,
                c.is_group
            FROM chats c
            LEFT JOIN contacts cnt_lid ON cnt_lid.lid = c.chat_jid
            LEFT JOIN contacts cnt_phone ON cnt_phone.phone_jid = c.chat_jid
            WHERE c.chat_name LIKE ?1
               OR c.chat_phone LIKE ?1
               OR cnt_lid.contact_name LIKE ?1
               OR cnt_lid.push_name LIKE ?1
               OR cnt_lid.short_name LIKE ?1
               OR cnt_lid.phone_number LIKE ?1
               OR cnt_phone.contact_name LIKE ?1
               OR cnt_phone.push_name LIKE ?1
               OR cnt_phone.phone_number LIKE ?1
            ORDER BY c.is_group ASC, display_name ASC
            LIMIT 50
        ",
            )
            .map_err(|e| e.to_string())?;

        let results = stmt
            .query_map([&pattern], |r| {
                Ok(ContactSearchResult {
                    chat_jid: r.get(0)?,
                    display_name: r.get(1)?,
                    phone: r.get(2)?,
                    is_group: r.get::<_, i64>(3).unwrap_or(0) != 0,
                })
            })
            .map_err(|e| e.to_string())?
            .filter_map(|r| r.ok())
            .collect();

        Ok(results)
    })
}

fn query_contact_items(
    conn: &Connection,
    filter: Option<&str>,
    query: Option<&str>,
    limit: i64,
    offset: i64,
) -> Result<Vec<ContactItem>, String> {
    let filter_clause = match filter.unwrap_or("all") {
        "saved" => "AND is_group = 0 AND (NULLIF(contact_name, '') IS NOT NULL OR NULLIF(short_name, '') IS NOT NULL)",
        "unsaved" => "AND is_group = 0 AND NULLIF(contact_name, '') IS NULL AND NULLIF(short_name, '') IS NULL",
        "groups" => "AND 1 = 0",
        "chats" => "AND is_group = 0 AND message_count > 0",
        "business" => "AND is_group = 0 AND is_business = 1",
        _ => "AND is_group = 0",
    };
    let needle = query.unwrap_or("").trim().to_string();
    let pattern = format!("%{}%", needle);
    let limit = limit.clamp(1, 20000);
    let offset = offset.max(0);
    let media_sql = media_message_count_sql();
    let visible_messages = visible_messages_subquery(conn)?;

    let sql = format!(
        "
        WITH chat_stats AS (
            SELECT
                chat_jid,
                COUNT(rowid) AS message_count,
                SUM(CASE WHEN from_me = 1 THEN 1 ELSE 0 END) AS sent_count,
                SUM(CASE WHEN from_me = 0 THEN 1 ELSE 0 END) AS recv_count,
                SUM(CASE WHEN {media_sql} THEN 1 ELSE 0 END) AS media_count,
                SUM(CASE WHEN COALESCE(msg_type, '') = 'call_log'
                          OR COALESCE(body_status, '') = 'call_event'
                          OR call_outcome IS NOT NULL
                          OR call_duration IS NOT NULL THEN 1 ELSE 0 END) AS call_count,
                MAX(timestamp) AS last_activity
            FROM {visible_messages}
            GROUP BY chat_jid
        ),
        people_raw AS (
            SELECT
                COALESCE(NULLIF(ct.lid, ''), NULLIF(ct.phone_jid, ''), NULLIF(ct.phone_number, '')) AS jid,
                ct.lid,
                ct.phone_jid,
                ct.phone_number,
                COALESCE(
                    NULLIF(ct.contact_name, ''),
                    NULLIF(ct.short_name, ''),
                    NULLIF(ct.push_name, ''),
                    NULLIF(ch.chat_name, ''),
                    NULLIF(ct.phone_number, ''),
                    NULLIF(ct.lid, ''),
                    NULLIF(ct.phone_jid, '')
                ) AS display_name,
                ct.contact_name,
                ct.short_name,
                ct.push_name,
                COALESCE(ct.is_business, 0) AS is_business,
                COALESCE(ct.is_self, 0) AS is_self,
                0 AS is_group,
                ch.chat_jid,
                ch.chat_name,
                COALESCE(cs.last_activity, ch.last_activity, 0) AS last_activity,
                COALESCE(cs.message_count, 0) AS message_count,
                COALESCE(cs.sent_count, 0) AS sent_count,
                COALESCE(cs.recv_count, 0) AS recv_count,
                COALESCE(cs.media_count, 0) AS media_count,
                COALESCE(cs.call_count, 0) AS call_count
            FROM contacts ct
            LEFT JOIN chats ch ON ch.chat_jid = ct.lid
                OR ch.chat_jid = ct.phone_jid
                OR (ct.phone_number IS NOT NULL AND ch.chat_phone = ct.phone_number)
            LEFT JOIN chat_stats cs ON cs.chat_jid = ch.chat_jid

            UNION ALL

            SELECT
                ch.chat_jid AS jid,
                NULL AS lid,
                NULL AS phone_jid,
                ch.chat_phone AS phone_number,
                COALESCE(NULLIF(ch.chat_name, ''), ch.chat_jid) AS display_name,
                ch.chat_name AS contact_name,
                NULL AS short_name,
                NULL AS push_name,
                0 AS is_business,
                0 AS is_self,
                1 AS is_group,
                ch.chat_jid,
                ch.chat_name,
                COALESCE(cs.last_activity, ch.last_activity, 0) AS last_activity,
                COALESCE(cs.message_count, 0) AS message_count,
                COALESCE(cs.sent_count, 0) AS sent_count,
                COALESCE(cs.recv_count, 0) AS recv_count,
                COALESCE(cs.media_count, 0) AS media_count,
                COALESCE(cs.call_count, 0) AS call_count
            FROM chats ch
            LEFT JOIN chat_stats cs ON cs.chat_jid = ch.chat_jid
            WHERE COALESCE(ch.is_group, 0) = 1
        ),
        people AS (
            SELECT
                jid, lid, phone_jid, phone_number, display_name, contact_name,
                short_name, push_name, is_business, is_self, is_group, chat_jid,
                chat_name, last_activity, message_count, sent_count, recv_count,
                media_count, call_count
            FROM (
                SELECT
                    people_raw.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY
                            CASE
                                WHEN is_group = 1 THEN 'group:' || COALESCE(chat_jid, jid)
                                WHEN NULLIF(phone_number, '') IS NOT NULL THEN 'phone:' || phone_number
                                WHEN NULLIF(phone_jid, '') IS NOT NULL THEN 'phone:' ||
                                    CASE
                                        WHEN instr(phone_jid, '@') > 0 THEN substr(phone_jid, 1, instr(phone_jid, '@') - 1)
                                        ELSE phone_jid
                                    END
                                WHEN COALESCE(NULLIF(lid, ''), NULLIF(jid, ''), NULLIF(chat_jid, '')) LIKE '%@c.us' THEN 'phone:' ||
                                    substr(
                                        COALESCE(NULLIF(lid, ''), NULLIF(jid, ''), NULLIF(chat_jid, '')),
                                        1,
                                        instr(COALESCE(NULLIF(lid, ''), NULLIF(jid, ''), NULLIF(chat_jid, '')), '@') - 1
                                    )
                                WHEN COALESCE(NULLIF(lid, ''), NULLIF(jid, ''), NULLIF(chat_jid, '')) LIKE '%@s.whatsapp.net' THEN 'phone:' ||
                                    substr(
                                        COALESCE(NULLIF(lid, ''), NULLIF(jid, ''), NULLIF(chat_jid, '')),
                                        1,
                                        instr(COALESCE(NULLIF(lid, ''), NULLIF(jid, ''), NULLIF(chat_jid, '')), '@') - 1
                                    )
                                ELSE 'jid:' || COALESCE(NULLIF(lid, ''), NULLIF(jid, ''), NULLIF(chat_jid, ''), NULLIF(display_name, ''))
                            END
                        ORDER BY
                            CASE WHEN message_count > 0 THEN 0 ELSE 1 END,
                            CASE WHEN chat_jid IS NOT NULL THEN 0 ELSE 1 END,
                            CASE WHEN COALESCE(NULLIF(lid, ''), NULLIF(jid, '')) LIKE '%@lid' THEN 0 ELSE 1 END,
                            CASE WHEN NULLIF(phone_jid, '') IS NOT NULL THEN 0 ELSE 1 END,
                            CASE WHEN NULLIF(contact_name, '') IS NOT NULL OR NULLIF(short_name, '') IS NOT NULL THEN 0 ELSE 1 END,
                            last_activity DESC,
                            display_name COLLATE NOCASE ASC,
                            jid COLLATE NOCASE ASC
                    ) AS person_rank
                FROM people_raw
            )
            WHERE person_rank = 1
        )
        SELECT
            jid, lid, phone_jid, phone_number, display_name, contact_name,
            short_name, push_name, is_business, is_self, is_group, chat_jid,
            chat_name, last_activity, message_count, sent_count, recv_count,
            media_count, call_count
        FROM people
        WHERE jid IS NOT NULL
          {filter_clause}
          AND (
              ?1 = ''
              OR COALESCE(display_name, '') LIKE ?2
              OR COALESCE(phone_number, '') LIKE ?2
              OR COALESCE(phone_jid, '') LIKE ?2
              OR COALESCE(lid, '') LIKE ?2
              OR COALESCE(chat_jid, '') LIKE ?2
              OR COALESCE(push_name, '') LIKE ?2
          )
        ORDER BY
            CASE
                WHEN TRIM(COALESCE(display_name, '')) GLOB '[A-Za-z]*' THEN 0
                WHEN TRIM(COALESCE(display_name, '')) GLOB '+[0-9]*'
                  OR TRIM(COALESCE(display_name, '')) GLOB '[0-9]*' THEN 2
                ELSE 1
            END,
            display_name COLLATE NOCASE ASC,
            CASE WHEN message_count > 0 THEN 0 ELSE 1 END,
            last_activity DESC
        LIMIT ?3 OFFSET ?4
        ",
        visible_messages = visible_messages,
    );

    let mut stmt = conn.prepare(&sql).map_err(|e| e.to_string())?;
    let rows = stmt
        .query_map(rusqlite::params![needle, pattern, limit, offset], |r| {
            Ok(ContactItem {
                jid: r.get(0)?,
                lid: r.get(1)?,
                phone_jid: r.get(2)?,
                phone_number: r.get(3)?,
                display_name: r.get(4)?,
                contact_name: r.get(5)?,
                short_name: r.get(6)?,
                push_name: r.get(7)?,
                is_business: r.get::<_, i64>(8).unwrap_or(0) != 0,
                is_self: r.get::<_, i64>(9).unwrap_or(0) != 0,
                is_group: r.get::<_, i64>(10).unwrap_or(0) != 0,
                chat_jid: r.get(11)?,
                chat_name: r.get(12)?,
                last_activity: r.get::<_, i64>(13).unwrap_or(0),
                message_count: r.get(14).unwrap_or(0),
                sent_count: r.get(15).unwrap_or(0),
                recv_count: r.get(16).unwrap_or(0),
                media_count: r.get(17).unwrap_or(0),
                call_count: r.get(18).unwrap_or(0),
            })
        })
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();

    Ok(rows)
}

fn query_contact_summary(conn: &Connection) -> Result<ContactSummary, String> {
    let contacts = query_contact_items(conn, Some("all"), None, 20_000, 0)?;
    let mut summary = ContactSummary {
        total: 0,
        saved: 0,
        unsaved: 0,
        groups: 0,
        with_chats: 0,
        businesses: 0,
    };

    for contact in contacts {
        summary.total += 1;
        if contact.is_group {
            summary.groups += 1;
        } else {
            let saved = contact
                .contact_name
                .as_deref()
                .is_some_and(|v| !v.trim().is_empty())
                || contact
                    .short_name
                    .as_deref()
                    .is_some_and(|v| !v.trim().is_empty());
            if saved {
                summary.saved += 1;
            } else {
                summary.unsaved += 1;
            }
        }
        if contact.message_count > 0 {
            summary.with_chats += 1;
        }
        if contact.is_business {
            summary.businesses += 1;
        }
    }

    Ok(summary)
}

fn query_call_summary(conn: &Connection) -> Result<CallSummary, String> {
    let visible_messages = visible_messages_subquery(conn)?;
    let sql = format!(
        "SELECT call_outcome, call_duration, from_me, is_video_call FROM {visible_messages} m WHERE {}",
        call_message_where_sql(),
        visible_messages = visible_messages,
    );
    let mut stmt = conn.prepare(&sql).map_err(|e| e.to_string())?;
    let rows = stmt
        .query_map([], |r| {
            Ok((
                r.get::<_, Option<String>>(0)?,
                r.get::<_, Option<i64>>(1)?,
                r.get::<_, Option<i64>>(2)?,
                r.get::<_, i64>(3).unwrap_or(0) != 0,
            ))
        })
        .map_err(|e| e.to_string())?;

    let mut summary = CallSummary {
        total: 0,
        missed: 0,
        answered: 0,
        declined: 0,
        incoming: 0,
        outgoing: 0,
        voice: 0,
        video: 0,
    };

    for row in rows.flatten() {
        summary.total += 1;
        match call_outcome_tone(row.0.as_deref(), row.1) {
            "missed" => summary.missed += 1,
            "declined" => summary.declined += 1,
            "answered" => summary.answered += 1,
            _ => {}
        }
        match row.2 {
            Some(1) => summary.outgoing += 1,
            Some(0) => summary.incoming += 1,
            _ => {}
        }
        if row.3 {
            summary.video += 1;
        } else {
            summary.voice += 1;
        }
    }

    Ok(summary)
}

fn query_call_items(
    conn: &Connection,
    filter: Option<&str>,
    query: Option<&str>,
    limit: i64,
    offset: i64,
) -> Result<Vec<CallItem>, String> {
    let filter_clause = match filter.unwrap_or("all") {
        "missed" => "AND (LOWER(COALESCE(m.call_outcome, '')) LIKE '%missed%' OR m.call_outcome IN ('2','missed_call'))",
        "answered" => "AND (COALESCE(m.call_duration, 0) > 0 OR LOWER(COALESCE(m.call_outcome, '')) IN ('accepted','answered','completed') OR m.call_outcome = '1')",
        "incoming" => "AND m.from_me = 0",
        "outgoing" => "AND m.from_me = 1",
        "voice" => "AND COALESCE(m.is_video_call, 0) = 0",
        "video" => "AND COALESCE(m.is_video_call, 0) != 0",
        _ => "",
    };
    let needle = query.unwrap_or("").trim().to_string();
    let pattern = format!("%{}%", needle);
    let limit = limit.clamp(1, 10000);
    let offset = offset.max(0);
    let visible_messages = visible_messages_subquery(conn)?;
    let sql = format!(
        "
        SELECT
            m.rowid,
            m.msg_key,
            m.chat_jid,
            COALESCE(
                NULLIF(c.chat_name, ''),
                NULLIF(m.chat_name, ''),
                NULLIF(cnt_lid.contact_name, ''),
                NULLIF(cnt_phone.contact_name, ''),
                NULLIF(cnt_lid.push_name, ''),
                NULLIF(cnt_phone.push_name, ''),
                NULLIF(cnt_lid.short_name, ''),
                NULLIF(cnt_phone.short_name, '')
            ) AS chat_name,
            COALESCE(m.chat_phone, c.chat_phone, cnt_lid.phone_number, cnt_phone.phone_number, m.sender_phone) AS phone,
            m.from_me,
            m.timestamp,
            m.call_duration,
            m.call_outcome,
            m.is_video_call,
            m.msg_type,
            COALESCE(m.sender_name, cnt_lid.contact_name, cnt_phone.contact_name, cnt_lid.push_name, cnt_phone.push_name) AS sender_name,
            COALESCE(m.sender_phone, cnt_lid.phone_number, cnt_phone.phone_number) AS sender_phone
        FROM {visible_messages} m
        LEFT JOIN chats c ON c.chat_jid = m.chat_jid
        LEFT JOIN contacts cnt_lid ON cnt_lid.lid = m.chat_jid
        LEFT JOIN contacts cnt_phone ON cnt_phone.phone_jid = m.chat_jid
        WHERE {}
          {}
          AND (
              ?1 = ''
              OR COALESCE(c.chat_name, m.chat_name, '') LIKE ?2
              OR COALESCE(m.sender_name, '') LIKE ?2
              OR COALESCE(m.sender_phone, '') LIKE ?2
              OR COALESCE(c.chat_phone, '') LIKE ?2
              OR COALESCE(cnt_lid.phone_number, '') LIKE ?2
              OR COALESCE(cnt_phone.phone_number, '') LIKE ?2
              OR COALESCE(m.call_outcome, '') LIKE ?2
          )
        ORDER BY m.timestamp DESC, m.rowid DESC
        LIMIT ?3 OFFSET ?4
        ",
        call_message_where_sql(),
        filter_clause,
        visible_messages = visible_messages,
    );

    let mut stmt = conn.prepare(&sql).map_err(|e| e.to_string())?;
    let rows = stmt
        .query_map(rusqlite::params![needle, pattern, limit, offset], |r| {
            Ok(CallItem {
                rowid: r.get(0)?,
                msg_key: r.get(1)?,
                chat_jid: r.get(2)?,
                chat_name: r.get(3)?,
                phone: r.get(4)?,
                from_me: r.get(5)?,
                timestamp: r.get::<_, i64>(6).unwrap_or(0),
                call_duration: r.get(7)?,
                call_outcome: r.get(8)?,
                is_video_call: r.get::<_, i64>(9).unwrap_or(0) != 0,
                msg_type: r.get(10)?,
                sender_name: r.get(11)?,
                sender_phone: r.get(12)?,
            })
        })
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();

    Ok(rows)
}

#[tauri::command]
fn get_contact_summary(state: State<AppState>) -> Result<ContactSummary, String> {
    with_db(&state, |conn| query_contact_summary(conn))
}

#[tauri::command]
fn get_contact_items(
    filter: Option<String>,
    query: Option<String>,
    limit: Option<i64>,
    offset: Option<i64>,
    state: State<AppState>,
) -> Result<Vec<ContactItem>, String> {
    with_db(&state, |conn| {
        query_contact_items(
            conn,
            filter.as_deref(),
            query.as_deref(),
            limit.unwrap_or(10_000),
            offset.unwrap_or(0),
        )
    })
}

#[tauri::command]
fn get_call_summary(state: State<AppState>) -> Result<CallSummary, String> {
    with_db(&state, |conn| query_call_summary(conn))
}

#[tauri::command]
fn get_call_items(
    filter: Option<String>,
    query: Option<String>,
    limit: Option<i64>,
    offset: Option<i64>,
    state: State<AppState>,
) -> Result<Vec<CallItem>, String> {
    with_db(&state, |conn| {
        query_call_items(
            conn,
            filter.as_deref(),
            query.as_deref(),
            limit.unwrap_or(10_000),
            offset.unwrap_or(0),
        )
    })
}

fn query_media_summary(conn: &Connection) -> Result<MediaSummary, String> {
    let visible_messages = visible_messages_subquery(conn)?;
    let sql = format!(
        "SELECT msg_type, media_mime_type, media_status FROM {visible_messages} m WHERE {}",
        media_message_where_sql(),
        visible_messages = visible_messages,
    );
    let mut stmt = conn.prepare(&sql).map_err(|e| e.to_string())?;
    let rows = stmt
        .query_map([], |r| {
            Ok((
                r.get::<_, Option<String>>(0)?,
                r.get::<_, Option<String>>(1)?,
                r.get::<_, Option<String>>(2)?,
            ))
        })
        .map_err(|e| e.to_string())?;

    let mut summary = MediaSummary {
        total: 0,
        available: 0,
        missing: 0,
        photos: 0,
        videos: 0,
        audio: 0,
        documents: 0,
        stickers: 0,
    };

    for row in rows.flatten() {
        summary.total += 1;
        let kind = media_kind_for(row.0.as_deref(), row.1.as_deref());
        match kind {
            "image" => summary.photos += 1,
            "video" => summary.videos += 1,
            "audio" => summary.audio += 1,
            "document" => summary.documents += 1,
            "sticker" => summary.stickers += 1,
            _ => {}
        }
        match row.2.as_deref() {
            Some("local_present") => summary.available += 1,
            Some("missing_local_file") => summary.missing += 1,
            _ => {}
        }
    }

    Ok(summary)
}

fn query_media_items(
    conn: &Connection,
    filter: Option<&str>,
    query: Option<&str>,
    limit: i64,
    offset: i64,
) -> Result<Vec<MediaItem>, String> {
    let status_broadcast_sql = "
        (
            LOWER(COALESCE(m.chat_jid, '')) LIKE 'status@broadcast%'
            OR LOWER(COALESCE(c.chat_name, m.chat_name, '')) LIKE 'status@broadcast%'
        )
    ";
    let filter_clause = match filter.unwrap_or("all") {
        "photos" => {
            "AND (m.msg_type IN ('image','album','gif') OR m.media_mime_type LIKE 'image/%')"
                .to_string()
        }
        "videos" => {
            "AND (m.msg_type IN ('video','ptv') OR m.media_mime_type LIKE 'video/%')".to_string()
        }
        "audio" => {
            "AND (m.msg_type IN ('audio','ptt') OR m.media_mime_type LIKE 'audio/%')".to_string()
        }
        "documents" => {
            "AND (m.msg_type = 'document' OR m.media_mime_type LIKE 'application/%')".to_string()
        }
        "stickers" => "AND m.msg_type = 'sticker'".to_string(),
        "missing" => "AND m.media_status = 'missing_local_file'".to_string(),
        "status" => format!("AND {status_broadcast_sql}"),
        _ => String::new(),
    };
    let needle = query.unwrap_or("").trim().to_string();
    let pattern = format!("%{}%", needle);
    let limit = limit.clamp(1, 10000);
    let offset = offset.max(0);
    let visible_messages = visible_messages_subquery(conn)?;
    let sql = format!(
        "
            SELECT
                m.rowid,
                m.msg_key,
                m.chat_jid,
                COALESCE(c.chat_name, m.chat_name) AS chat_name,
                m.from_me,
                m.sender_name,
                m.timestamp,
                m.text,
                m.msg_type,
                m.media_mime_type,
                m.media_filename,
                m.media_size,
                m.media_case_path,
                m.media_sha256,
                m.media_status
            FROM {visible_messages} m
            LEFT JOIN chats c ON c.chat_jid = m.chat_jid
            WHERE {}
              {}
              AND (
                  ?1 = ''
                  OR COALESCE(m.media_filename, '') LIKE ?2
                  OR COALESCE(c.chat_name, m.chat_name, '') LIKE ?2
                  OR COALESCE(m.sender_name, '') LIKE ?2
                  OR COALESCE(m.media_mime_type, '') LIKE ?2
                  OR COALESCE(m.text, '') LIKE ?2
              )
            ORDER BY
                CASE WHEN {status_broadcast_sql} THEN 1 ELSE 0 END,
                CASE WHEN COALESCE(m.media_status, '') = 'missing_local_file' THEN 1 ELSE 0 END,
                m.timestamp DESC,
                m.rowid DESC
            LIMIT ?3 OFFSET ?4
            ",
        media_message_where_sql(),
        filter_clause,
        status_broadcast_sql = status_broadcast_sql,
        visible_messages = visible_messages,
    );

    let mut stmt = conn.prepare(&sql).map_err(|e| e.to_string())?;
    let rows = stmt
        .query_map(rusqlite::params![needle, pattern, limit, offset], |r| {
            let msg_type: Option<String> = r.get(8)?;
            let media_mime_type: Option<String> = r.get(9)?;
            Ok(MediaItem {
                rowid: r.get(0)?,
                msg_key: r.get(1)?,
                chat_jid: r.get(2)?,
                chat_name: r.get(3)?,
                from_me: r.get(4)?,
                sender_name: r.get(5)?,
                timestamp: r.get::<_, i64>(6).unwrap_or(0),
                text: r.get(7)?,
                media_kind: media_kind_for(msg_type.as_deref(), media_mime_type.as_deref())
                    .to_string(),
                msg_type,
                media_mime_type,
                media_filename: r.get(10)?,
                media_size: r.get(11)?,
                media_case_path: r.get(12).ok(),
                media_sha256: r.get(13).ok(),
                media_status: r.get(14).ok(),
            })
        })
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();

    Ok(rows)
}

#[tauri::command]
fn get_media_summary(state: State<AppState>) -> Result<MediaSummary, String> {
    with_db(&state, |conn| query_media_summary(conn))
}

#[tauri::command]
fn get_media_items(
    filter: Option<String>,
    query: Option<String>,
    limit: Option<i64>,
    offset: Option<i64>,
    state: State<AppState>,
) -> Result<Vec<MediaItem>, String> {
    with_db(&state, |conn| {
        query_media_items(
            conn,
            filter.as_deref(),
            query.as_deref(),
            limit.unwrap_or(5000),
            offset.unwrap_or(0),
        )
    })
}

#[tauri::command]
fn reveal_media_file(path: String, state: State<AppState>) -> Result<(), String> {
    let media_path = resolve_case_media_path(&state, &path)?;
    #[cfg(target_os = "windows")]
    {
        Command::new("explorer.exe")
            .arg(format!("/select,{}", media_path.display()))
            .spawn()
            .map_err(|e| format!("Failed to reveal media file: {e}"))?;
    }
    #[cfg(not(target_os = "windows"))]
    {
        let parent = media_path
            .parent()
            .ok_or_else(|| "Media file has no containing folder.".to_string())?;
        Command::new("xdg-open")
            .arg(parent)
            .spawn()
            .map_err(|e| format!("Failed to reveal media file: {e}"))?;
    }
    Ok(())
}

fn visible_order_cache_ready(cache: Option<&Connection>) -> Result<bool, String> {
    let Some(cache) = cache else {
        return Ok(false);
    };
    if !table_exists(cache, "visible_message_order")? {
        return Ok(false);
    }
    let count: i64 = cache
        .query_row("SELECT COUNT(*) FROM visible_message_order", [], |r| {
            r.get(0)
        })
        .unwrap_or(0);
    Ok(count > 0)
}

fn query_messages_by_rowids(conn: &Connection, rowids: &[i64]) -> Result<Vec<Message>, String> {
    if rowids.is_empty() {
        return Ok(Vec::new());
    }
    let placeholders = std::iter::repeat("?")
        .take(rowids.len())
        .collect::<Vec<_>>()
        .join(",");
    let sql = format!(
        "{} WHERE m.rowid IN ({}) ORDER BY m.timestamp ASC, m.rowid ASC",
        message_select_sql_base(conn)?,
        placeholders
    );
    let params: Vec<&dyn rusqlite::types::ToSql> = rowids
        .iter()
        .map(|id| id as &dyn rusqlite::types::ToSql)
        .collect();
    let mut stmt = conn.prepare(&sql).map_err(|e| e.to_string())?;
    let msgs = stmt
        .query_map(params.as_slice(), |r| message_from_row(r))
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();
    Ok(msgs)
}

fn cached_cursor_timestamp(cache: &Connection, chat_jid: &str, rowid: i64) -> Result<i64, String> {
    cache
        .query_row(
            "SELECT timestamp FROM visible_message_order WHERE chat_jid = ?1 AND rowid = ?2 LIMIT 1",
            rusqlite::params![chat_jid, rowid],
            |r| r.get::<_, i64>(0),
        )
        .optional()
        .map_err(|e| e.to_string())?
        .ok_or_else(|| format!("Cursor message rowid {rowid} was not found in this chat."))
}

fn cached_paginated_rowids(
    cache: &Connection,
    chat_jid: &str,
    limit: i64,
    before_rowid: Option<i64>,
) -> Result<Vec<i64>, String> {
    let limit = limit.clamp(1, 500);
    let mut rowids = if let Some(br) = before_rowid {
        let cursor_ts = cached_cursor_timestamp(cache, chat_jid, br)?;
        let mut stmt = cache
            .prepare(
                "
                SELECT rowid
                FROM visible_message_order
                WHERE chat_jid = ?1
                  AND (timestamp < ?2 OR (timestamp = ?2 AND rowid < ?3))
                ORDER BY timestamp DESC, rowid DESC
                LIMIT ?4
                ",
            )
            .map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map(rusqlite::params![chat_jid, cursor_ts, br, limit], |r| {
                r.get::<_, i64>(0)
            })
            .map_err(|e| e.to_string())?
            .filter_map(|r| r.ok())
            .collect::<Vec<_>>();
        rows
    } else {
        let mut stmt = cache
            .prepare(
                "
                SELECT rowid
                FROM visible_message_order
                WHERE chat_jid = ?1
                ORDER BY timestamp DESC, rowid DESC
                LIMIT ?2
                ",
            )
            .map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map(rusqlite::params![chat_jid, limit], |r| r.get::<_, i64>(0))
            .map_err(|e| e.to_string())?
            .filter_map(|r| r.ok())
            .collect::<Vec<_>>();
        rows
    };
    rowids.reverse();
    Ok(rowids)
}

fn cached_newer_rowids(
    cache: &Connection,
    chat_jid: &str,
    after_rowid: i64,
    limit: i64,
) -> Result<Vec<i64>, String> {
    let limit = limit.clamp(1, 500);
    let cursor_ts = cached_cursor_timestamp(cache, chat_jid, after_rowid)?;
    let mut stmt = cache
        .prepare(
            "
            SELECT rowid
            FROM visible_message_order
            WHERE chat_jid = ?1
              AND (timestamp > ?2 OR (timestamp = ?2 AND rowid > ?3))
            ORDER BY timestamp ASC, rowid ASC
            LIMIT ?4
            ",
        )
        .map_err(|e| e.to_string())?;
    let rowids = stmt
        .query_map(
            rusqlite::params![chat_jid, cursor_ts, after_rowid, limit],
            |r| r.get::<_, i64>(0),
        )
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();
    Ok(rowids)
}

// ---------------------------------------------------------------------------
// Cursor-based paginated message loading.
// before_rowid = None returns the most recent `limit` messages.
// before_rowid = Some(r) returns `limit` messages older than that row's timestamp/rowid.
// Results are returned in ascending timestamp/rowid order for the UI.
// ---------------------------------------------------------------------------
#[tauri::command]
fn get_messages_paginated(
    chat_jid: String,
    limit: i64,
    before_rowid: Option<i64>,
    state: State<AppState>,
) -> Result<Vec<Message>, String> {
    with_db_and_cache(&state, |conn, cache| {
        if visible_order_cache_ready(cache)? {
            let cache = cache.unwrap();
            let rowids = cached_paginated_rowids(cache, &chat_jid, limit, before_rowid)?;
            return query_messages_by_rowids(conn, &rowids);
        }

        // Fetch rows in DESC timestamp order then reverse. rowid is only a
        // tie-breaker; it is not chronological in unified_whatsapp.db.
        let select_sql = message_select_sql_owned(conn)?;
        let (sql, params_vec): (String, Vec<Box<dyn rusqlite::types::ToSql>>) = if let Some(br) =
            before_rowid
        {
            let cursor_ts: i64 = conn
                .query_row(
                    "SELECT timestamp FROM messages WHERE chat_jid = ? AND rowid = ?",
                    rusqlite::params![chat_jid.as_str(), br],
                    |r| r.get::<_, i64>(0),
                )
                .optional()
                .map_err(|e| e.to_string())?
                .ok_or_else(|| format!("Cursor message rowid {br} was not found in this chat."))?;

            (
                select_sql.clone()
                    + "
                WHERE m.chat_jid = ?
                  AND (
                      m.timestamp < ?
                      OR (m.timestamp = ? AND m.rowid < ?)
                  )
                ORDER BY m.timestamp DESC, m.rowid DESC
                LIMIT ?
                ",
                vec![
                    Box::new(chat_jid.clone()) as Box<dyn rusqlite::types::ToSql>,
                    Box::new(cursor_ts) as Box<dyn rusqlite::types::ToSql>,
                    Box::new(cursor_ts) as Box<dyn rusqlite::types::ToSql>,
                    Box::new(br) as Box<dyn rusqlite::types::ToSql>,
                    Box::new(limit) as Box<dyn rusqlite::types::ToSql>,
                ],
            )
        } else {
            (
                select_sql
                    + "
                WHERE m.chat_jid = ?
                ORDER BY m.timestamp DESC, m.rowid DESC
                LIMIT ?
                ",
                vec![
                    Box::new(chat_jid.clone()) as Box<dyn rusqlite::types::ToSql>,
                    Box::new(limit) as Box<dyn rusqlite::types::ToSql>,
                ],
            )
        };

        let params_slice: Vec<&dyn rusqlite::types::ToSql> =
            params_vec.iter().map(|p| p.as_ref()).collect();
        let mut stmt = conn.prepare(&sql).map_err(|e| e.to_string())?;

        let mut msgs: Vec<Message> = stmt
            .query_map(params_slice.as_slice(), |r| message_from_row(r))
            .map_err(|e| e.to_string())?
            .filter_map(|r| r.ok())
            .collect();

        // Reverse so caller always gets ascending order (oldest → newest)
        msgs.reverse();
        Ok(msgs)
    })
}

#[tauri::command]
fn get_messages_after_rowid(
    chat_jid: String,
    limit: i64,
    after_rowid: i64,
    state: State<AppState>,
) -> Result<Vec<Message>, String> {
    with_db_and_cache(&state, |conn, cache| {
        if visible_order_cache_ready(cache)? {
            let cache = cache.unwrap();
            let rowids = cached_newer_rowids(cache, &chat_jid, after_rowid, limit)?;
            return query_messages_by_rowids(conn, &rowids);
        }

        let cursor_ts: i64 = conn
            .query_row(
                "SELECT timestamp FROM messages WHERE chat_jid = ? AND rowid = ?",
                rusqlite::params![chat_jid.as_str(), after_rowid],
                |r| r.get::<_, i64>(0),
            )
            .optional()
            .map_err(|e| e.to_string())?
            .ok_or_else(|| {
                format!("Cursor message rowid {after_rowid} was not found in this chat.")
            })?;

        let sql = message_select_sql_owned(conn)?
            + "
            WHERE m.chat_jid = ?
              AND (
                  m.timestamp > ?
                  OR (m.timestamp = ? AND m.rowid > ?)
              )
            ORDER BY m.timestamp ASC, m.rowid ASC
            LIMIT ?
        ";

        let mut stmt = conn.prepare(&sql).map_err(|e| e.to_string())?;
        let msgs = stmt
            .query_map(
                rusqlite::params![chat_jid.as_str(), cursor_ts, cursor_ts, after_rowid, limit],
                |r| message_from_row(r),
            )
            .map_err(|e| e.to_string())?
            .filter_map(|r| r.ok())
            .collect();

        Ok(msgs)
    })
}

#[tauri::command]
fn get_messages_around_rowid(
    chat_jid: String,
    rowid: i64,
    before: i64,
    after: i64,
    state: State<AppState>,
) -> Result<MessageWindow, String> {
    with_db_and_cache(&state, |conn, cache| {
        if visible_order_cache_ready(cache)? {
            let cache = cache.unwrap();
            let target_ts = cached_cursor_timestamp(cache, &chat_jid, rowid)?;
            let older_limit = before.max(0) + 1;
            let newer_limit = after.max(0) + 1;

            let mut older_stmt = cache
                .prepare(
                    "
                SELECT rowid
                FROM visible_message_order
                WHERE chat_jid = ?1
                  AND (timestamp < ?2 OR (timestamp = ?2 AND rowid < ?3))
                ORDER BY timestamp DESC, rowid DESC
                LIMIT ?4
                ",
                )
                .map_err(|e| e.to_string())?;
            let mut older = older_stmt
                .query_map(
                    rusqlite::params![chat_jid.as_str(), target_ts, rowid, older_limit],
                    |r| r.get::<_, i64>(0),
                )
                .map_err(|e| e.to_string())?
                .filter_map(|r| r.ok())
                .collect::<Vec<_>>();
            let has_older = (older.len() as i64) > before.max(0);
            if has_older {
                older.truncate(before.max(0) as usize);
            }
            older.reverse();

            let mut newer_stmt = cache
                .prepare(
                    "
                SELECT rowid
                FROM visible_message_order
                WHERE chat_jid = ?1
                  AND (timestamp > ?2 OR (timestamp = ?2 AND rowid > ?3))
                ORDER BY timestamp ASC, rowid ASC
                LIMIT ?4
                ",
                )
                .map_err(|e| e.to_string())?;
            let mut newer = newer_stmt
                .query_map(
                    rusqlite::params![chat_jid.as_str(), target_ts, rowid, newer_limit],
                    |r| r.get::<_, i64>(0),
                )
                .map_err(|e| e.to_string())?
                .filter_map(|r| r.ok())
                .collect::<Vec<_>>();
            let has_newer = (newer.len() as i64) > after.max(0);
            if has_newer {
                newer.truncate(after.max(0) as usize);
            }

            let mut rowids = older;
            rowids.push(rowid);
            rowids.extend(newer);
            let messages = query_messages_by_rowids(conn, &rowids)?;

            return Ok(MessageWindow {
                messages,
                target_found: true,
                has_older,
                has_newer,
            });
        }

        let target_ts: i64 = conn
            .query_row(
                "SELECT timestamp FROM messages WHERE chat_jid = ? AND rowid = ?",
                rusqlite::params![chat_jid.as_str(), rowid],
                |r| r.get::<_, i64>(0),
            )
            .optional()
            .map_err(|e| e.to_string())?
            .ok_or_else(|| format!("Target message rowid {rowid} was not found in this chat."))?;

        let target_sql =
            message_select_sql_owned(conn)? + " WHERE m.chat_jid = ? AND m.rowid = ? LIMIT 1";
        let target = conn
            .query_row(
                &target_sql,
                rusqlite::params![chat_jid.as_str(), rowid],
                |r| message_from_row(r),
            )
            .optional()
            .map_err(|e| e.to_string())?;

        let older_sql = message_select_sql_owned(conn)?
            + "
            WHERE m.chat_jid = ?
              AND (
                  m.timestamp < ?
                  OR (m.timestamp = ? AND m.rowid < ?)
              )
            ORDER BY m.timestamp DESC, m.rowid DESC
            LIMIT ?
        ";
        let newer_sql = message_select_sql_owned(conn)?
            + "
            WHERE m.chat_jid = ?
              AND (
                  m.timestamp > ?
                  OR (m.timestamp = ? AND m.rowid > ?)
              )
            ORDER BY m.timestamp ASC, m.rowid ASC
            LIMIT ?
        ";

        let older_limit = before.max(0) + 1;
        let newer_limit = after.max(0) + 1;

        let mut older_stmt = conn.prepare(&older_sql).map_err(|e| e.to_string())?;
        let mut older: Vec<Message> = older_stmt
            .query_map(
                rusqlite::params![chat_jid.as_str(), target_ts, target_ts, rowid, older_limit],
                |r| message_from_row(r),
            )
            .map_err(|e| e.to_string())?
            .filter_map(|r| r.ok())
            .collect();
        let has_older = (older.len() as i64) > before.max(0);
        if has_older {
            older.truncate(before.max(0) as usize);
        }
        older.reverse();

        let mut newer_stmt = conn.prepare(&newer_sql).map_err(|e| e.to_string())?;
        let mut newer: Vec<Message> = newer_stmt
            .query_map(
                rusqlite::params![chat_jid.as_str(), target_ts, target_ts, rowid, newer_limit],
                |r| message_from_row(r),
            )
            .map_err(|e| e.to_string())?
            .filter_map(|r| r.ok())
            .collect();
        let has_newer = (newer.len() as i64) > after.max(0);
        if has_newer {
            newer.truncate(after.max(0) as usize);
        }

        let mut messages = older;
        if let Some(target_msg) = target {
            messages.push(target_msg);
        }
        messages.extend(newer);

        Ok(MessageWindow {
            messages,
            target_found: true,
            has_older,
            has_newer,
        })
    })
}

#[tauri::command]
fn get_messages_by_stanza_ids(
    chat_jid: String,
    stanza_ids: Vec<String>,
    state: State<AppState>,
) -> Result<Vec<Message>, String> {
    with_db_and_cache(&state, |conn, cache| {
        if visible_order_cache_ready(cache)? {
            let cache = cache.unwrap();
            let mut same_chat_stmt = cache
                .prepare(
                    "SELECT rowid FROM visible_message_order
                     WHERE chat_jid = ?1 AND msg_id = ?2
                     ORDER BY timestamp ASC, rowid ASC
                     LIMIT 1",
                )
                .map_err(|e| e.to_string())?;
            let mut global_stmt = cache
                .prepare(
                    "SELECT rowid FROM visible_message_order
                     WHERE msg_id = ?1
                     ORDER BY timestamp ASC, rowid ASC
                     LIMIT 2",
                )
                .map_err(|e| e.to_string())?;
            let mut rowids = Vec::new();
            let mut seen_rowids = HashSet::new();

            for stanza_id in stanza_ids {
                let stanza_id = stanza_id.trim().to_string();
                if stanza_id.is_empty() {
                    continue;
                }

                let same_chat = same_chat_stmt
                    .query_row(
                        rusqlite::params![chat_jid.as_str(), stanza_id.as_str()],
                        |r| r.get::<_, i64>(0),
                    )
                    .optional()
                    .map_err(|e| e.to_string())?;

                let rowid = if same_chat.is_some() {
                    same_chat
                } else {
                    let rows = global_stmt
                        .query_map(rusqlite::params![stanza_id.as_str()], |r| {
                            r.get::<_, i64>(0)
                        })
                        .map_err(|e| e.to_string())?
                        .filter_map(|r| r.ok())
                        .collect::<Vec<_>>();
                    if rows.len() == 1 {
                        rows.into_iter().next()
                    } else {
                        None
                    }
                };

                if let Some(rowid) = rowid {
                    if seen_rowids.insert(rowid) {
                        rowids.push(rowid);
                    }
                }
            }

            return query_messages_by_rowids(conn, &rowids);
        }

        let select_sql = message_select_sql_owned(conn)?;

        let mut same_chat_stmt = conn
            .prepare(&(select_sql.clone() + " WHERE m.chat_jid = ? AND m.msg_id = ? ORDER BY m.timestamp ASC, m.rowid ASC LIMIT 1"))
            .map_err(|e| e.to_string())?;
        let mut global_stmt = conn
            .prepare(
                &(select_sql + " WHERE m.msg_id = ? ORDER BY m.timestamp ASC, m.rowid ASC LIMIT 2"),
            )
            .map_err(|e| e.to_string())?;

        let mut results = Vec::new();
        let mut seen_rowids = HashSet::new();

        for stanza_id in stanza_ids {
            let stanza_id = stanza_id.trim().to_string();
            if stanza_id.is_empty() {
                continue;
            }

            let same_chat = same_chat_stmt
                .query_row(
                    rusqlite::params![chat_jid.as_str(), stanza_id.as_str()],
                    |r| message_from_row(r),
                )
                .optional()
                .map_err(|e| e.to_string())?;

            let msg = if same_chat.is_some() {
                same_chat
            } else {
                let rows = global_stmt
                    .query_map(rusqlite::params![stanza_id.as_str()], |r| {
                        message_from_row(r)
                    })
                    .map_err(|e| e.to_string())?
                    .filter_map(|r| r.ok())
                    .collect::<Vec<_>>();
                if rows.len() == 1 {
                    rows.into_iter().next()
                } else {
                    None
                }
            };

            if let Some(msg) = msg {
                if seen_rowids.insert(msg.rowid) {
                    results.push(msg);
                }
            }
        }

        Ok(results)
    })
}

// ---------------------------------------------------------------------------
// Entry Point
// ---------------------------------------------------------------------------

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(AppState {
            db_path: Mutex::new(None),
            db_conn: Mutex::new(None),
            cache_conn: Mutex::new(None),
            db_sha256: Mutex::new(None),
        })
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .invoke_handler(tauri::generate_handler![
            get_app_info,
            get_install_type,
            install_installed_update,
            install_portable_update,
            pick_db_file,
            pick_folder,
            set_db_path,
            get_db_path,
            validate_db,
            get_chats,
            get_messages,
            get_messages_paginated,
            get_messages_after_rowid,
            get_messages_around_rowid,
            get_messages_by_stanza_ids,
            get_contact_info,
            get_contact_picture,
            resolve_participant_name,
            resolve_participant_names,
            search_messages,
            search_contacts,
            get_contact_summary,
            get_contact_items,
            get_call_summary,
            get_call_items,
            get_media_summary,
            get_media_items,
            reveal_media_file,
            get_group_participants,
            get_group_info,
            get_message_receipts,
            get_message_statuses,
            get_message_mentions_for_messages,
            get_message_edit_history,
            get_reactions_for_messages,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    fn temp_db_path(name: &str) -> PathBuf {
        let thread_name = std::thread::current()
            .name()
            .unwrap_or("test")
            .replace(|ch: char| !ch.is_ascii_alphanumeric(), "_");
        std::env::temp_dir().join(format!(
            "waren6-reader-{name}-{}-{}.sqlite",
            std::process::id(),
            thread_name
        ))
    }

    fn create_large_unified_db(path: &PathBuf) {
        let _ = fs::remove_file(path);
        let conn = Connection::open(path).expect("create test unified db");
        conn.execute_batch("CREATE TABLE messages(text TEXT);")
            .expect("create messages table");
        let tx = conn
            .unchecked_transaction()
            .expect("start insert transaction");
        {
            let mut stmt = tx
                .prepare("INSERT INTO messages(text) VALUES (?)")
                .expect("prepare insert");
            let payload = "x".repeat(512);
            for i in 0..15_000 {
                stmt.execute([format!("synthetic message {i} {payload}")])
                    .expect("insert message");
            }
        }
        tx.commit().expect("commit test messages");
        assert!(fs::metadata(path).expect("test db metadata").len() > 8 * 1024 * 1024);
    }

    fn create_media_unified_db(path: &PathBuf) {
        let _ = fs::remove_file(path);
        let conn = Connection::open(path).expect("create media test db");
        conn.execute_batch(
            "
            CREATE TABLE chats(chat_jid TEXT PRIMARY KEY, chat_name TEXT);
            CREATE TABLE messages(
                rowid INTEGER PRIMARY KEY,
                msg_key TEXT,
                chat_jid TEXT,
                chat_name TEXT,
                from_me INTEGER,
                sender_name TEXT,
                timestamp INTEGER,
                text TEXT,
                msg_type TEXT,
                media_mime_type TEXT,
                media_filename TEXT,
                media_size INTEGER,
                media_case_path TEXT,
                media_sha256 TEXT,
                media_status TEXT,
                body_status TEXT,
                source TEXT,
                source_recovery TEXT
            );
            INSERT INTO chats(chat_jid, chat_name) VALUES ('school@g.us', 'School Group');
            INSERT INTO messages(rowid, msg_key, chat_jid, timestamp, text, msg_type, media_mime_type, media_filename, media_size, media_status, body_status)
            VALUES
                (1, 'm1', 'school@g.us', 1778311974, 'biology notes', 'document', 'application/pdf', 'Result XII.pdf', 128, 'missing_local_file', 'media_only'),
                (2, 'm2', 'school@g.us', 1778312000, NULL, 'image', 'image/jpeg', 'photo.jpg', 256, 'local_present', 'media_only');
            ",
        )
        .expect("seed media db");
    }

    fn create_people_unified_db(path: &PathBuf) {
        let _ = fs::remove_file(path);
        let conn = Connection::open(path).expect("create people test db");
        conn.execute_batch(
            "
            CREATE TABLE contacts(
                lid TEXT PRIMARY KEY,
                phone_jid TEXT,
                phone_number TEXT,
                contact_name TEXT,
                short_name TEXT,
                push_name TEXT,
                is_business INTEGER DEFAULT 0,
                is_self INTEGER DEFAULT 0
            );
            CREATE TABLE chats(
                chat_jid TEXT PRIMARY KEY,
                chat_name TEXT,
                chat_phone TEXT,
                is_group INTEGER DEFAULT 0,
                is_newsletter INTEGER DEFAULT 0,
                unread_count INTEGER DEFAULT 0,
                last_activity INTEGER
            );
            CREATE TABLE messages(
                rowid INTEGER PRIMARY KEY,
                msg_key TEXT,
                chat_jid TEXT,
                chat_name TEXT,
                chat_phone TEXT,
                sender_jid TEXT,
                sender_phone TEXT,
                sender_name TEXT,
                from_me INTEGER,
                timestamp INTEGER,
                text TEXT,
                is_group INTEGER DEFAULT 0,
                msg_type TEXT,
                call_duration INTEGER,
                call_outcome TEXT,
                is_video_call INTEGER DEFAULT 0,
                media_mime_type TEXT,
                media_filename TEXT,
                media_size INTEGER,
                media_status TEXT,
                body_status TEXT,
                source TEXT,
                source_recovery TEXT
            );
            INSERT INTO contacts(lid, phone_jid, phone_number, contact_name, short_name, push_name, is_business)
            VALUES
                ('111@lid', '15550101234@c.us', '15550101234', 'Example Contact', 'Example', 'Example Push', 0),
                ('222@lid', '15550101003@c.us', '15550101003', NULL, NULL, NULL, 1);
            INSERT INTO chats(chat_jid, chat_name, chat_phone, is_group, last_activity)
            VALUES
                ('111@lid', NULL, '15550101234', 0, 1778311974),
                ('school@g.us', 'School Group', NULL, 1, 1778312000);
            INSERT INTO messages(rowid, msg_key, chat_jid, chat_name, sender_name, sender_phone, from_me, timestamp, text, msg_type, call_duration, call_outcome, is_video_call, media_filename, media_status, body_status)
            VALUES
                (1, 'm1', '111@lid', 'Example Contact', 'Example Contact', '15550101234', 1, 1778311974, 'hello', 'chat', NULL, NULL, 0, NULL, NULL, 'text_present'),
                (2, 'm2', '111@lid', 'Example Contact', 'Example Contact', '15550101234', 0, 1778311980, NULL, 'call_log', NULL, 'Missed', 0, NULL, NULL, 'call_event'),
                (3, 'm3', '111@lid', 'Example Contact', 'Example Contact', '15550101234', 1, 1778312000, NULL, 'call_log', 127, 'Completed', 1, NULL, NULL, 'call_event'),
                (4, 'm4', 'school@g.us', 'School Group', NULL, NULL, 0, 1778312100, NULL, 'image', NULL, NULL, 0, 'photo.jpg', 'local_present', 'media_only');
            ",
        )
        .expect("seed people db");
    }

    fn create_paging_unified_db(path: &PathBuf) {
        let _ = fs::remove_file(path);
        let conn = Connection::open(path).expect("create paging test db");
        conn.execute_batch(
            "
            CREATE TABLE messages(
                rowid INTEGER PRIMARY KEY,
                msg_key TEXT,
                msg_id TEXT,
                chat_jid TEXT,
                from_me INTEGER,
                timestamp INTEGER,
                text TEXT,
                msg_type TEXT,
                source TEXT,
                source_recovery TEXT
            );
            INSERT INTO messages(rowid, msg_key, msg_id, chat_jid, from_me, timestamp, text, msg_type, source, source_recovery)
            VALUES
                (1, 'true_12345@c.us_A', 'A', '12345@c.us', 1, 1770000000, 'same text', 'chat', 'runtime_store8', 'runtime_store8_only'),
                (2, NULL, '2', '12345@c.us', 1, 1770000000, 'same text', 'chat', 'genericStorage', 'sqlite_recovered_row'),
                (3, 'true_12345@c.us_B', 'B', '12345@c.us', 1, 1770000060, 'newer text', 'chat', 'indexeddb', NULL),
                (4, 'false_67890@c.us_C', 'C', '67890@c.us', 0, 1770000120, 'other chat', 'chat', 'indexeddb', NULL);
            ",
        )
        .expect("seed paging db");
    }

    #[test]
    fn detects_reader_install_type_from_path_markers() {
        assert_eq!(
            install_type_from_path_markers(
                &PathBuf::from(r"C:\Program Files\WAren6 Reader\WAren6 Reader.exe"),
                false,
            ),
            "installed",
        );
        assert_eq!(
            install_type_from_path_markers(
                &PathBuf::from(r"D:\Apps\WAren6 Reader\WAren6 Reader.exe"),
                true,
            ),
            "installed",
        );
        assert_eq!(
            install_type_from_path_markers(
                &PathBuf::from(r"C:\Cases\WAren6-Reader-Portable-v1.7.0.exe"),
                false,
            ),
            "portable",
        );
    }

    #[test]
    fn portable_update_safety_rejects_non_exe_or_unwritable_paths() {
        let safe = portable_update_safety_for_path(
            &PathBuf::from(r"C:\Cases\WAren6-Reader-Portable-v1.7.0.exe"),
            true,
        );
        assert!(safe.safe);
        assert_eq!(safe.reason, None);

        let wrong_extension =
            portable_update_safety_for_path(&PathBuf::from(r"C:\Cases\WAren6-Reader.txt"), true);
        assert!(!wrong_extension.safe);
        assert_eq!(
            wrong_extension.reason.as_deref(),
            Some("current executable is not an .exe file")
        );

        let blocked = portable_update_safety_for_path(
            &PathBuf::from(r"C:\Cases\WAren6-Reader-Portable-v1.7.0.exe"),
            false,
        );
        assert!(!blocked.safe);
        assert_eq!(
            blocked.reason.as_deref(),
            Some("current folder is not writable")
        );
    }

    #[test]
    fn app_metadata_reports_version_identifier_and_path_safety() {
        let info = app_info_for_exe_path(
            &PathBuf::from(r"C:\Cases\WAren6-Reader-Portable-v1.7.0.exe"),
            true,
        );

        assert_eq!(info.version, "1.7.0");
        assert_eq!(info.app_identifier, "com.mayukxt.waren6.reader");
        assert_eq!(info.install_type, "portable");
        assert!(info.exe_path_is_safe);
    }

    #[test]
    fn opens_large_unified_db_read_only() {
        let path = temp_db_path("readonly");
        create_large_unified_db(&path);
        let path_str = path.to_string_lossy();
        let conn = Connection::open_with_flags(
            path_str.as_ref(),
            OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_NO_MUTEX,
        )
        .expect("open unified db read-only");
        conn.execute_batch("PRAGMA query_only=ON;")
            .expect("set query_only");
        let count: i64 = conn
            .query_row("SELECT COUNT(*) FROM messages", [], |r| r.get(0))
            .expect("count messages");
        assert!(count > 0);
        let _ = fs::remove_file(path);
    }

    #[test]
    fn builds_search_cache_for_large_unified_db() {
        let path = temp_db_path("cache-source");
        create_large_unified_db(&path);
        let path_str = path.to_string_lossy();
        let source_hash = sha256_file(path_str.as_ref()).expect("hash unified db");
        let conn = Connection::open_with_flags(
            path_str.as_ref(),
            OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_NO_MUTEX,
        )
        .expect("open unified db read-only");
        conn.execute_batch("PRAGMA query_only=ON;")
            .expect("set query_only");

        let cache_path =
            std::env::temp_dir().join(format!("waren6-reader-cache-test-{source_hash}.sqlite"));
        let _ = fs::remove_file(&cache_path);
        let _ = fs::remove_file(cache_path.with_extension("sqlite-shm"));
        let _ = fs::remove_file(cache_path.with_extension("sqlite-wal"));

        let cache = build_search_cache_at_path(
            cache_path.to_string_lossy().into_owned(),
            path_str.as_ref(),
            &source_hash,
            &conn,
        )
        .expect("build search cache");
        let cache_count: i64 = cache
            .query_row("SELECT COUNT(*) FROM messages_fts", [], |r| r.get(0))
            .expect("count cached messages");
        assert!(cache_count > 0);
        drop(cache);
        let _ = fs::remove_file(path);
        let _ = fs::remove_file(cache_path);
    }

    #[test]
    fn search_cache_builds_indexed_visible_message_order() {
        let path = temp_db_path("visible-order-source");
        create_paging_unified_db(&path);
        let path_str = path.to_string_lossy();
        let source_hash = sha256_file(path_str.as_ref()).expect("hash paging db");
        let conn = Connection::open_with_flags(
            path_str.as_ref(),
            OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_NO_MUTEX,
        )
        .expect("open paging db read-only");
        conn.execute_batch("PRAGMA query_only=ON;")
            .expect("set query_only");

        let cache_path = std::env::temp_dir().join(format!(
            "waren6-reader-visible-order-test-{source_hash}.sqlite"
        ));
        let _ = fs::remove_file(&cache_path);
        let _ = fs::remove_file(cache_path.with_extension("sqlite-shm"));
        let _ = fs::remove_file(cache_path.with_extension("sqlite-wal"));

        let cache = build_search_cache_at_path(
            cache_path.to_string_lossy().into_owned(),
            path_str.as_ref(),
            &source_hash,
            &conn,
        )
        .expect("build search cache");
        let count: i64 = cache
            .query_row("SELECT COUNT(*) FROM visible_message_order", [], |r| {
                r.get(0)
            })
            .expect("count visible order rows");
        let indexes = cache
            .prepare("PRAGMA index_list(visible_message_order)")
            .expect("prepare index list")
            .query_map([], |r| r.get::<_, String>(1))
            .expect("query index list")
            .filter_map(|r| r.ok())
            .collect::<Vec<_>>();

        assert_eq!(count, 3);
        assert!(indexes
            .iter()
            .any(|name| name == "idx_visible_message_order_chat_ts"));

        drop(cache);
        let _ = fs::remove_file(path);
        let _ = fs::remove_file(cache_path);
    }

    #[test]
    fn search_cache_rebuilds_legacy_cache_without_visible_order() {
        let path = temp_db_path("visible-order-legacy-source");
        create_paging_unified_db(&path);
        let path_str = path.to_string_lossy();
        let source_hash = sha256_file(path_str.as_ref()).expect("hash paging db");
        let conn = Connection::open_with_flags(
            path_str.as_ref(),
            OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_NO_MUTEX,
        )
        .expect("open paging db read-only");
        conn.execute_batch("PRAGMA query_only=ON;")
            .expect("set query_only");

        let cache_path = std::env::temp_dir().join(format!(
            "waren6-reader-legacy-visible-order-test-{source_hash}.sqlite"
        ));
        let _ = fs::remove_file(&cache_path);
        let legacy = Connection::open(cache_path.as_path()).expect("open legacy cache");
        legacy
            .execute_batch(
                "
            CREATE TABLE cache_metadata(key TEXT PRIMARY KEY, value TEXT);
            CREATE VIRTUAL TABLE messages_fts USING fts5(source_rowid UNINDEXED, text);
            INSERT INTO cache_metadata(key, value) VALUES ('source_sha256', 'HASH_PLACEHOLDER');
            INSERT INTO cache_metadata(key, value) VALUES ('source_path', 'PATH_PLACEHOLDER');
            ",
            )
            .expect("seed legacy cache");
        legacy
            .execute(
                "UPDATE cache_metadata SET value = ?1 WHERE key = 'source_sha256'",
                [source_hash.as_str()],
            )
            .expect("set hash");
        legacy
            .execute(
                "UPDATE cache_metadata SET value = ?1 WHERE key = 'source_path'",
                [path_str.as_ref()],
            )
            .expect("set path");
        drop(legacy);

        let cache = build_search_cache_at_path(
            cache_path.to_string_lossy().into_owned(),
            path_str.as_ref(),
            &source_hash,
            &conn,
        )
        .expect("rebuild legacy search cache");
        let count: i64 = cache
            .query_row("SELECT COUNT(*) FROM visible_message_order", [], |r| {
                r.get(0)
            })
            .expect("count visible order rows");

        assert_eq!(count, 3);

        drop(cache);
        let _ = fs::remove_file(path);
        let _ = fs::remove_file(cache_path);
    }

    #[test]
    fn media_kind_prefers_whatsapp_type_then_mime_family() {
        assert_eq!(
            media_kind_for(Some("sticker"), Some("image/webp")),
            "sticker"
        );
        assert_eq!(
            media_kind_for(Some("interactive"), Some("image/jpeg")),
            "image"
        );
        assert_eq!(media_kind_for(None, Some("application/pdf")), "document");
        assert_eq!(media_kind_for(Some("ptt"), None), "audio");
    }

    #[test]
    fn media_query_filters_searches_and_summarizes_items() {
        let path = temp_db_path("media");
        create_media_unified_db(&path);
        let conn = Connection::open(path.as_path()).expect("open media db");

        let summary = query_media_summary(&conn).expect("media summary");
        assert_eq!(summary.total, 2);
        assert_eq!(summary.available, 1);
        assert_eq!(summary.missing, 1);
        assert_eq!(summary.photos, 1);
        assert_eq!(summary.documents, 1);

        let rows =
            query_media_items(&conn, Some("missing"), Some("biology"), 20, 0).expect("media rows");
        assert_eq!(rows.len(), 1);
        assert_eq!(rows[0].media_filename.as_deref(), Some("Result XII.pdf"));
        assert_eq!(rows[0].chat_name.as_deref(), Some("School Group"));
        assert_eq!(rows[0].media_kind, "document");

        drop(conn);
        let _ = fs::remove_file(path);
    }

    #[test]
    fn media_query_prioritizes_available_chat_media_before_missing_and_status_media() {
        let path = temp_db_path("media-priority");
        create_media_unified_db(&path);
        let conn = Connection::open(path.as_path()).expect("open media priority db");
        conn.execute_batch(
            "
            INSERT INTO chats(chat_jid, chat_name) VALUES
                ('12345@c.us', 'Direct Chat'),
                ('status@broadcast', 'status@broadcast_AC');
            INSERT INTO messages(rowid, msg_key, chat_jid, timestamp, text, msg_type, media_mime_type, media_filename, media_size, media_status, body_status)
            VALUES
                (3, 'm3', '12345@c.us', 1778312300, NULL, 'image', 'image/jpeg', 'chat-missing.jpg', 300, 'missing_local_file', 'media_only'),
                (4, 'm4', '12345@c.us', 1778312100, NULL, 'image', 'image/jpeg', 'chat-available.jpg', 400, 'local_present', 'media_only'),
                (5, 'm5', 'status@broadcast', 1778312500, NULL, 'image', 'image/jpeg', 'status-available.jpg', 500, 'local_present', 'media_only'),
                (6, 'm6', 'status@broadcast', 1778312600, NULL, 'image', 'image/jpeg', 'status-missing.jpg', 600, 'missing_local_file', 'media_only');
            ",
        )
        .expect("seed media priority db");

        let rows = query_media_items(&conn, Some("all"), Some(".jpg"), 20, 0).expect("media rows");
        let filenames: Vec<&str> = rows
            .iter()
            .filter_map(|item| item.media_filename.as_deref())
            .collect();

        assert_eq!(
            filenames,
            vec![
                "chat-available.jpg",
                "photo.jpg",
                "chat-missing.jpg",
                "status-available.jpg",
                "status-missing.jpg",
            ]
        );

        let status_rows = query_media_items(&conn, Some("status"), Some(".jpg"), 20, 0)
            .expect("status media rows");
        let status_filenames: Vec<&str> = status_rows
            .iter()
            .filter_map(|item| item.media_filename.as_deref())
            .collect();

        assert_eq!(
            status_filenames,
            vec!["status-available.jpg", "status-missing.jpg"]
        );

        drop(conn);
        let _ = fs::remove_file(path);
    }

    #[test]
    fn contact_query_summarizes_saved_unsaved_people_and_chat_activity() {
        let path = temp_db_path("people-contacts");
        create_people_unified_db(&path);
        let conn = Connection::open(path.as_path()).expect("open people db");

        let summary = query_contact_summary(&conn).expect("contact summary");
        assert_eq!(summary.total, 2);
        assert_eq!(summary.saved, 1);
        assert_eq!(summary.unsaved, 1);
        assert_eq!(summary.groups, 0);
        assert_eq!(summary.with_chats, 1);

        let contacts =
            query_contact_items(&conn, Some("all"), Some("example"), 50, 0).expect("contact rows");
        assert_eq!(contacts.len(), 1);
        assert_eq!(contacts[0].display_name.as_deref(), Some("Example Contact"));
        assert_eq!(contacts[0].message_count, 3);
        assert_eq!(contacts[0].call_count, 2);

        let groups =
            query_contact_items(&conn, Some("groups"), None, 50, 0).expect("group contact rows");
        assert_eq!(groups.len(), 0);

        drop(conn);
        let _ = fs::remove_file(path);
    }

    #[test]
    fn contact_query_deduplicates_lid_and_phone_rows_for_same_saved_person() {
        let path = temp_db_path("people-contact-dedupe");
        create_people_unified_db(&path);
        let conn = Connection::open(path.as_path()).expect("open people dedupe db");
        conn.execute_batch(
            "
            INSERT INTO contacts(lid, phone_jid, phone_number, contact_name, short_name, push_name, is_business)
            VALUES
                ('333@lid', '15550101004@c.us', '15550101004', 'Saved Contact', NULL, NULL, 0),
                ('15550101004@c.us', NULL, '15550101004', 'Saved Contact', NULL, NULL, 0);
            INSERT INTO chats(chat_jid, chat_phone, is_group, last_activity)
            VALUES ('333@lid', '15550101004', 0, 1778312400);
            INSERT INTO messages(rowid, msg_key, chat_jid, chat_name, sender_name, sender_phone, from_me, timestamp, text, msg_type, body_status)
            VALUES (5, 'm5', '333@lid', 'Saved Contact', 'Saved Contact', '15550101004', 0, 1778312400, 'hello', 'chat', 'text_present');
            ",
        )
        .expect("seed duplicate contact rows");

        let contacts =
            query_contact_items(&conn, Some("all"), Some("Saved"), 50, 0).expect("contact rows");

        assert_eq!(contacts.len(), 1);
        assert_eq!(contacts[0].display_name.as_deref(), Some("Saved Contact"));
        assert_eq!(contacts[0].phone_number.as_deref(), Some("15550101004"));
        assert_eq!(contacts[0].chat_jid.as_deref(), Some("333@lid"));
        assert_eq!(contacts[0].message_count, 1);

        drop(conn);
        let _ = fs::remove_file(path);
    }

    #[test]
    fn contact_query_sorts_named_latin_contacts_before_other_scripts_and_numbers() {
        let path = temp_db_path("people-contact-sort");
        create_people_unified_db(&path);
        let conn = Connection::open(path.as_path()).expect("open people sort db");
        conn.execute_batch(
            "
            INSERT INTO contacts(lid, phone_jid, phone_number, contact_name, short_name, push_name, is_business)
            VALUES
                ('333@lid', '15550101001@c.us', '15550101001', NULL, NULL, NULL, 0),
                ('444@lid', '15550101006@c.us', '15550101006', 'Alice Example', NULL, NULL, 0),
                ('555@lid', '15550101007@c.us', '15550101007', 'नमूना', NULL, NULL, 0);
            INSERT INTO chats(chat_jid, chat_phone, is_group, last_activity)
            VALUES ('333@lid', '15550101001', 0, 1778312200);
            INSERT INTO messages(rowid, msg_key, chat_jid, chat_name, sender_name, sender_phone, from_me, timestamp, text, msg_type, body_status)
            VALUES (5, 'm5', '333@lid', NULL, NULL, '15550101001', 0, 1778312200, 'active number', 'chat', 'text_present');
            ",
        )
        .expect("seed contact sort db");

        let rows =
            query_contact_items(&conn, Some("all"), None, 50, 0).expect("sorted contact rows");
        let names: Vec<&str> = rows
            .iter()
            .filter_map(|contact| contact.display_name.as_deref())
            .collect();

        assert_eq!(
            names,
            vec![
                "Alice Example",
                "Example Contact",
                "नमूना",
                "15550101001",
                "15550101003",
            ]
        );

        drop(conn);
        let _ = fs::remove_file(path);
    }

    #[test]
    fn participant_resolution_uses_sender_phone_for_unsaved_lid_mentions() {
        let path = temp_db_path("participant-phone-fallback");
        create_people_unified_db(&path);
        let conn = Connection::open(path.as_path()).expect("open people fallback db");
        conn.execute_batch(
            "
            INSERT INTO messages(rowid, msg_key, chat_jid, chat_name, sender_jid, sender_phone, from_me, timestamp, text, is_group, msg_type, body_status)
            VALUES (6, 'm6', 'school@g.us', 'School Group', '999@lid', '15550109999', 0, 1778312600, 'unsaved member', 1, 'chat', 'text_present');
            ",
        )
        .expect("seed unsaved participant message");

        let resolved = resolve_participant_name_from_conn(&conn, "999@lid")
            .expect("resolve participant")
            .expect("participant should resolve from message sender phone");

        assert_eq!(resolved.name, None);
        assert_eq!(resolved.phone.as_deref(), Some("15550109999"));

        drop(conn);
        let _ = fs::remove_file(path);
    }

    #[test]
    fn message_mentions_query_handles_batches_and_missing_table() {
        let path = temp_db_path("message-mentions");
        create_people_unified_db(&path);
        let conn = Connection::open(path.as_path()).expect("open mention db");
        conn.execute_batch(
            "
            CREATE TABLE message_mentions(
                msg_key TEXT,
                chat_jid TEXT,
                mention_index INTEGER,
                kind TEXT,
                target_jid TEXT,
                target_phone TEXT,
                target_name TEXT,
                display_text TEXT,
                source TEXT,
                confidence TEXT
            );
            INSERT INTO message_mentions(msg_key, chat_jid, mention_index, kind, target_jid, target_phone, target_name, display_text, source, confidence)
            VALUES
                ('m1', 'school@g.us', 0, 'participant', '111@lid', '15550101234', 'Example Contact', '~Example Contact', 'store8', 'high'),
                ('m1', 'school@g.us', 1, 'all', NULL, NULL, NULL, '@all', 'store8', 'high');
            ",
        )
        .expect("seed mentions");

        let rows =
            query_message_mentions_for_keys(&conn, &["m1".to_string(), "missing".to_string()])
                .expect("query mentions");
        assert_eq!(rows.len(), 2);
        assert_eq!(rows[0].kind, "participant");
        assert_eq!(rows[0].target_jid.as_deref(), Some("111@lid"));
        assert_eq!(rows[1].kind, "all");

        let missing_path = temp_db_path("message-mentions-missing");
        create_people_unified_db(&missing_path);
        let missing_conn = Connection::open(missing_path.as_path()).expect("open no mention db");
        let empty = query_message_mentions_for_keys(&missing_conn, &["m1".to_string()])
            .expect("missing mention table should be non-fatal");
        assert!(empty.is_empty());

        drop(conn);
        drop(missing_conn);
        let _ = fs::remove_file(path);
        let _ = fs::remove_file(missing_path);
    }

    #[test]
    fn message_reactions_query_handles_batches_and_missing_table() {
        let path = temp_db_path("message-reactions");
        create_people_unified_db(&path);
        let conn = Connection::open(path.as_path()).expect("open reaction db");
        conn.execute_batch(
            "
            CREATE TABLE reactions(
                parent_msg_key TEXT,
                sender_jid TEXT,
                sender_phone TEXT,
                sender_name TEXT,
                reaction_text TEXT,
                timestamp INTEGER
            );
            INSERT INTO reactions(parent_msg_key, sender_jid, sender_phone, sender_name, reaction_text, timestamp)
            VALUES
                ('m1', '111@lid', '15550101234', 'Example Contact', '👍', 1778312999),
                ('m1', '111@lid', '15550101234', 'Example Contact', '✅', 1778313999),
                ('m1', '222@lid', '15550104321', 'Removed Contact', '😮', 1778314000),
                ('m1', '222@lid', '15550104321', 'Removed Contact', NULL, 1778315000),
                ('m2', '333@lid', '15550109999', 'Other Message', '😂', 1778316000);
            ",
        )
        .expect("seed reactions");

        let rows =
            query_message_reactions_for_keys(&conn, &["m1".to_string()]).expect("query reactions");
        assert_eq!(rows.len(), 1);
        assert_eq!(rows[0].parent_msg_key, "m1");
        assert_eq!(rows[0].reaction_text.as_deref(), Some("✅"));
        assert_eq!(rows[0].sender_jid.as_deref(), Some("111@lid"));

        drop(conn);
        let _ = fs::remove_file(path);
    }

    #[test]
    fn portable_update_helper_args_include_log_file_once() {
        let args = portable_update_helper_args(
            &PathBuf::from(r"C:\Temp\helper.ps1"),
            123,
            &PathBuf::from(r"C:\Apps\WAren6.exe"),
            &PathBuf::from(r"C:\Temp\new.exe"),
            &PathBuf::from(r"C:\Temp\old.bak"),
            &PathBuf::from(r"C:\Temp\portable-update.log"),
        );

        let log_file_count = args.iter().filter(|arg| arg.as_str() == "-LogFile").count();
        assert_eq!(log_file_count, 1);
        assert_eq!(
            args.last().map(String::as_str),
            Some(r"C:\Temp\portable-update.log")
        );
    }

    #[test]
    fn chat_query_uses_group_subject_for_missing_chat_name() {
        let path = temp_db_path("group-subject-chat");
        let _ = fs::remove_file(&path);
        let conn = Connection::open(path.as_path()).expect("open group subject db");
        conn.execute_batch(
            "
            CREATE TABLE chats(
                chat_jid TEXT PRIMARY KEY,
                chat_name TEXT,
                chat_phone TEXT,
                is_group INTEGER DEFAULT 0,
                is_newsletter INTEGER DEFAULT 0,
                unread_count INTEGER DEFAULT 0,
                last_activity INTEGER
            );
            CREATE TABLE groups(
                group_jid TEXT PRIMARY KEY,
                subject TEXT,
                description TEXT,
                owner_lid TEXT,
                owner_phone TEXT,
                creation_time INTEGER,
                participant_count INTEGER DEFAULT 0
            );
            CREATE TABLE contacts(
                lid TEXT PRIMARY KEY,
                phone_jid TEXT,
                phone_number TEXT,
                contact_name TEXT,
                short_name TEXT,
                push_name TEXT
            );
            CREATE TABLE messages(
                rowid INTEGER PRIMARY KEY,
                msg_key TEXT,
                chat_jid TEXT,
                from_me INTEGER,
                timestamp INTEGER,
                text TEXT,
                is_group INTEGER DEFAULT 0,
                msg_type TEXT,
                source TEXT,
                source_recovery TEXT
            );
            INSERT INTO chats(chat_jid, chat_name, is_group, is_newsletter, last_activity)
            VALUES ('fixturegroup@g.us', 'Old Group Name', 1, 0, 1778494158);
            INSERT INTO groups(group_jid, subject, participant_count)
            VALUES ('fixturegroup@g.us', 'Example Study Group', 6);
            INSERT INTO messages(rowid, msg_key, chat_jid, from_me, timestamp, text, is_group, msg_type)
            VALUES (1, 'm1', 'fixturegroup@g.us', 0, 1778494158, 'Thanks...', 1, 'chat');
            ",
        )
        .expect("seed group subject db");

        let chats = query_chats(&conn).expect("chat rows");
        assert_eq!(chats.len(), 1);
        assert_eq!(chats[0].chat_name.as_deref(), Some("Example Study Group"));
        assert!(chats[0].is_group);

        drop(conn);
        let _ = fs::remove_file(path);
    }

    #[test]
    fn message_queries_hide_legacy_runtime_generic_duplicates() {
        let path = temp_db_path("legacy-duplicate-filter");
        let _ = fs::remove_file(&path);
        let conn = Connection::open(path.as_path()).expect("open duplicate filter db");
        conn.execute_batch(
            "
            CREATE TABLE contacts(
                lid TEXT PRIMARY KEY,
                phone_jid TEXT,
                phone_number TEXT,
                contact_name TEXT,
                short_name TEXT,
                push_name TEXT
            );
            CREATE TABLE chats(
                chat_jid TEXT PRIMARY KEY,
                chat_name TEXT,
                chat_phone TEXT,
                is_group INTEGER DEFAULT 0,
                is_newsletter INTEGER DEFAULT 0,
                unread_count INTEGER DEFAULT 0,
                last_activity INTEGER
            );
            CREATE TABLE groups(
                group_jid TEXT PRIMARY KEY,
                subject TEXT,
                participant_count INTEGER DEFAULT 0
            );
            CREATE TABLE messages(
                rowid INTEGER PRIMARY KEY,
                msg_key TEXT,
                msg_id TEXT,
                chat_jid TEXT,
                chat_name TEXT,
                chat_phone TEXT,
                sender_jid TEXT,
                sender_phone TEXT,
                sender_name TEXT,
                from_me INTEGER,
                timestamp INTEGER,
                text TEXT,
                is_group INTEGER DEFAULT 0,
                msg_type TEXT,
                quoted_stanza_id TEXT,
                quoted_participant TEXT,
                quoted_msg_body TEXT,
                quoted_msg_type TEXT,
                call_duration INTEGER,
                call_outcome TEXT,
                is_video_call INTEGER DEFAULT 0,
                media_mime_type TEXT,
                media_filename TEXT,
                media_size INTEGER,
                media_case_path TEXT,
                media_sha256 TEXT,
                media_status TEXT,
                body_status TEXT,
                source TEXT,
                source_recovery TEXT
            );
            CREATE TABLE message_receipts(
                msg_key TEXT,
                receiver_jid TEXT,
                receiver_phone TEXT,
                receiver_name TEXT,
                delivery_time INTEGER,
                read_time INTEGER,
                played_time INTEGER
            );
            INSERT INTO chats(chat_jid, chat_name, chat_phone, is_group, last_activity)
            VALUES ('12345@c.us', NULL, '12345', 0, 1770000000);
            INSERT INTO messages(rowid, msg_key, msg_id, chat_jid, from_me, timestamp, text, is_group, msg_type, source, source_recovery, body_status, media_mime_type, media_filename, media_status)
            VALUES
                (1, 'true_12345@c.us_A', 'A', '12345@c.us', 1, 1770000000, 'same text', 0, 'chat', 'runtime_store8', 'runtime_store8_only', 'runtime_store8_decoded', 'image/jpeg', 'same.jpg', 'local_present'),
                (2, NULL, '7', '12345@c.us', 1, 1770000000, 'same text', 0, 'chat', 'genericStorage', 'sqlite_recovered_row', 'genericStorage_text', 'image/jpeg', 'same.jpg', 'local_present'),
                (3, 'true_12345@c.us_B', 'B', '12345@c.us', 1, 1770000000, 'same text', 0, 'chat', 'genericStorage', 'sqlite_recovered_row', 'genericStorage_text', 'image/jpeg', 'same.jpg', 'local_present'),
                (4, NULL, '8', '12345@c.us', NULL, 1770000000, 'same text', 0, 'chat', 'genericStorage', 'sqlite_recovered_row', 'genericStorage_text', 'image/jpeg', 'same.jpg', 'local_present'),
                (5, 'true_12345@c.us_P', 'P', '12345@c.us', 1, 1770000010, 'same text', 0, 'protocol', 'indexeddb', 'store8_runtime_decoded', 'runtime_store8_decoded', NULL, NULL, NULL),
                (6, 'true_12345@c.us_U', 'U', '12345@c.us', 1, 1770000300, 'https://youtube.com/shorts/abc123', 0, 'chat', 'runtime_store8', 'runtime_store8_only', 'runtime_store8_decoded', NULL, NULL, NULL),
                (7, NULL, '9', '12345@c.us', 1, 1770000300, 'youtube.com https://youtube.com/shorts/abc123 https://youtube.com/shorts/abc123', 0, 'chat', 'genericStorage', 'sqlite_recovered_row', 'genericStorage_text', NULL, NULL, NULL);
            INSERT INTO message_receipts(msg_key, receiver_jid, receiver_phone, receiver_name, delivery_time, read_time, played_time)
            VALUES
                ('true_12345@c.us_A', '12345@lid', '12345', 'Receiver', 1770000001, NULL, NULL),
                ('true_12345@c.us_P', '12345@lid', '12345', 'Receiver', 1770000011, 1770000020, NULL);
            ",
        )
        .expect("seed duplicate filter db");

        let sql = message_select_sql_owned(&conn).expect("visible message select sql")
            + "
            WHERE m.chat_jid = ?
            ORDER BY m.timestamp ASC, m.rowid ASC
        ";
        let rows = {
            let mut stmt = conn.prepare(&sql).expect("prepare visible messages");
            stmt.query_map(["12345@c.us"], |r| message_from_row(r))
                .expect("query visible messages")
                .filter_map(|r| r.ok())
                .collect::<Vec<_>>()
        };
        let chats = query_chats(&conn).expect("query chats");
        let media_summary = query_media_summary(&conn).expect("query media summary");
        let media_items =
            query_media_items(&conn, Some("all"), None, 20, 0).expect("query media rows");
        let receipts = query_message_receipts_for_visible_key(&conn, "true_12345@c.us_A")
            .expect("query folded receipts");
        let statuses = query_message_statuses_for_keys(&conn, &["true_12345@c.us_A".to_string()])
            .expect("query folded status");

        assert_eq!(rows.len(), 2);
        assert_eq!(rows[0].rowid, 1);
        assert_eq!(rows[1].rowid, 6);
        assert_eq!(chats[0].message_count, 2);
        assert_eq!(chats[0].sent_count, 2);
        assert_eq!(media_summary.total, 1);
        assert_eq!(media_items.len(), 1);
        assert_eq!(media_items[0].rowid, 1);
        assert_eq!(receipts.len(), 1);
        assert_eq!(receipts[0].msg_key, "true_12345@c.us_A");
        assert_eq!(receipts[0].read_time, Some(1770000020));
        assert_eq!(statuses.len(), 1);
        assert_eq!(statuses[0].status, "read");

        drop(conn);
        let _ = fs::remove_file(path);
    }

    #[test]
    fn message_edit_history_query_hides_protocol_rows_and_returns_snapshots() {
        let path = temp_db_path("message-edit-history");
        let _ = fs::remove_file(&path);
        let conn = Connection::open(path.as_path()).expect("open edit history db");
        conn.execute_batch(
            "
            CREATE TABLE contacts(
                lid TEXT PRIMARY KEY,
                phone_jid TEXT,
                phone_number TEXT,
                contact_name TEXT,
                short_name TEXT,
                push_name TEXT
            );
            CREATE TABLE messages(
                rowid INTEGER PRIMARY KEY,
                msg_key TEXT,
                msg_id TEXT,
                chat_jid TEXT,
                chat_name TEXT,
                chat_phone TEXT,
                sender_jid TEXT,
                sender_phone TEXT,
                sender_name TEXT,
                from_me INTEGER,
                timestamp INTEGER,
                text TEXT,
                is_group INTEGER DEFAULT 0,
                msg_type TEXT,
                quoted_stanza_id TEXT,
                quoted_participant TEXT,
                quoted_msg_body TEXT,
                quoted_msg_type TEXT,
                call_duration INTEGER,
                call_outcome TEXT,
                is_video_call INTEGER DEFAULT 0,
                media_mime_type TEXT,
                media_filename TEXT,
                media_size INTEGER,
                media_case_path TEXT,
                media_sha256 TEXT,
                media_status TEXT,
                body_status TEXT,
                source TEXT,
                source_recovery TEXT,
                is_edited INTEGER DEFAULT 0,
                edited_at INTEGER,
                edit_count INTEGER DEFAULT 0,
                edit_history_status TEXT
            );
            CREATE TABLE message_edits(
                target_msg_key TEXT,
                target_chat_jid TEXT,
                target_msg_id TEXT,
                edit_event_msg_key TEXT,
                edit_index INTEGER,
                edited_at INTEGER,
                editor_jid TEXT,
                editor_phone TEXT,
                editor_name TEXT,
                previous_text TEXT,
                new_text TEXT,
                source TEXT,
                confidence TEXT,
                provenance_sha256 TEXT
            );
            INSERT INTO messages(rowid, msg_key, msg_id, chat_jid, from_me, timestamp, text, is_group, msg_type, body_status, is_edited, edited_at, edit_count, edit_history_status)
            VALUES
                (1, 'true_12345@c.us_TARGET', 'TARGET', '12345@c.us', 1, 1770000000, 'current text', 0, 'chat', 'text_present', 1, 1770000100, 1, 'event_history'),
                (2, 'true_12345@c.us_EDIT', 'EDIT', '12345@c.us', 1, 1770000100, 'current text', 0, 'protocol', 'text_present', 0, NULL, 0, NULL),
                (3, 'false_12345@c.us_REPLY', 'REPLY', '12345@c.us', 0, 1770000200, 'reply', 0, 'chat', 'text_present', 0, NULL, 0, NULL);
            UPDATE messages
            SET quoted_stanza_id = 'TARGET', quoted_msg_body = 'captured quote'
            WHERE rowid = 3;
            INSERT INTO message_edits(target_msg_key, target_chat_jid, target_msg_id, edit_event_msg_key, edit_index, edited_at, editor_jid, editor_phone, editor_name, previous_text, new_text, source, confidence, provenance_sha256)
            VALUES ('true_12345@c.us_TARGET', '12345@c.us', 'TARGET', 'true_12345@c.us_EDIT', 1, 1770000100, '12345@c.us', '12345', 'You', NULL, 'current text', 'store8', 'high', 'abc');
            ",
        )
        .expect("seed edit history db");

        let sql = message_select_sql_owned(&conn).expect("visible message select sql")
            + "
            WHERE m.chat_jid = ?
            ORDER BY m.rowid ASC
        ";
        let rows = {
            let mut stmt = conn.prepare(&sql).expect("prepare visible edit messages");
            stmt.query_map(["12345@c.us"], |r| message_from_row(r))
                .expect("query visible edit messages")
                .filter_map(|r| r.ok())
                .collect::<Vec<_>>()
        };
        let history = query_message_edit_history_for_key(&conn, "true_12345@c.us_TARGET")
            .expect("query edit history");

        assert_eq!(rows.iter().map(|m| m.rowid).collect::<Vec<_>>(), vec![1, 3]);
        assert!(rows[0].is_edited);
        assert_eq!(rows[0].edit_count, 1);
        assert_eq!(history.edits.len(), 1);
        assert_eq!(
            history.edits[0].edit_event_msg_key.as_deref(),
            Some("true_12345@c.us_EDIT")
        );
        assert_eq!(history.quote_snapshots.len(), 1);
        assert_eq!(
            history.quote_snapshots[0].quoted_msg_body.as_deref(),
            Some("captured quote")
        );

        drop(conn);
        let _ = fs::remove_file(path);
    }

    #[test]
    fn call_query_filters_missed_video_and_searches_contact_names() {
        let path = temp_db_path("people-calls");
        create_people_unified_db(&path);
        let conn = Connection::open(path.as_path()).expect("open people db");

        let summary = query_call_summary(&conn).expect("call summary");
        assert_eq!(summary.total, 2);
        assert_eq!(summary.missed, 1);
        assert_eq!(summary.answered, 1);
        assert_eq!(summary.video, 1);
        assert_eq!(summary.voice, 1);

        let missed =
            query_call_items(&conn, Some("missed"), Some("example"), 50, 0).expect("missed calls");
        assert_eq!(missed.len(), 1);
        assert_eq!(missed[0].call_outcome.as_deref(), Some("Missed"));

        let video = query_call_items(&conn, Some("video"), None, 50, 0).expect("video calls");
        assert_eq!(video.len(), 1);
        assert!(video[0].is_video_call);
        assert_eq!(video[0].chat_name.as_deref(), Some("Example Contact"));

        drop(conn);
        let _ = fs::remove_file(path);
    }
}
