#!/usr/bin/env python3
"""
waren6.py - WhatsApp Desktop Unified Database Extractor

Extracts data from WhatsApp Desktop WebView2's IndexedDB (LevelDB) and
decrypted SQLite databases, resolves LID-to-phone mappings, and produces
a single self-contained SQLite database readable by any tool.

Requirements:
    pip install git+https://github.com/cclgroupltd/ccl_chromium_reader.git

Usage:
    python waren6.py --idb-path <path_to_EBWebView_Default> \
                         --decrypted-dir <path_to_WAren6_output> \
                        --output <path_to_unified.db>
"""

import argparse
import base64
import binascii
import concurrent.futures
import csv
import datetime
import functools
import hashlib
import hmac
import html
import json
import mimetypes
import os
import pathlib
import platform
import re
import shutil
import sqlite3
import struct
import sys
import tempfile
import time
import traceback
from collections import Counter
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from waren6_unify_case import cleanup_prepared_unify_case, prepare_unify_case

# Force UTF-8 output on Windows to avoid cp1252 encoding issues
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

ccl_chromium_indexeddb = None
ccl_chromium_localstorage = None


def require_ccl_reader():
    """Load ccl_chromium_reader only for commands that actually need IndexedDB."""
    global ccl_chromium_indexeddb, ccl_chromium_localstorage
    if ccl_chromium_indexeddb and ccl_chromium_localstorage:
        return
    try:
        from ccl_chromium_reader import ccl_chromium_indexeddb as _indexeddb
        from ccl_chromium_reader import ccl_chromium_localstorage as _localstorage
    except ImportError:
        print("ERROR: ccl_chromium_reader not installed.")
        print("Run on an online prep PC, then copy wheels to the field kit:")
        print("  pip download --dest wheels git+https://github.com/cclgroupltd/ccl_chromium_reader.git")
        print("Or install from an offline wheel folder:")
        print("  python -m pip install --no-index --find-links wheels ccl_chromium_reader")
        sys.exit(1)
    ccl_chromium_indexeddb = _indexeddb
    ccl_chromium_localstorage = _localstorage


EXTRACTION_EVENTS = {
    "warnings": [],
    "skipped_records": [],
    "collisions": [],
}
PROGRESS_ENABLED = True
VERBOSE_CONSOLE = False


def log_detail(message):
    if VERBOSE_CONSOLE:
        print(message)


# ─────────────────────────────────────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────────────────────────────────────

UNIFIED_SCHEMA = """
-- Metadata about the extraction itself (chain-of-custody)
CREATE TABLE IF NOT EXISTS extraction_metadata (
    key         TEXT PRIMARY KEY,
    value       TEXT
);

-- Resolved contact directory (LID-to-phone + name)
CREATE TABLE IF NOT EXISTS contacts (
    lid             TEXT,
    phone_jid       TEXT,
    phone_number    TEXT,
    contact_name    TEXT,
    short_name      TEXT,
    push_name       TEXT,
    is_business     INTEGER DEFAULT 0,
    is_self         INTEGER DEFAULT 0,
    confidence      TEXT DEFAULT 'high',
    PRIMARY KEY (lid)
);
CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts(phone_number);
CREATE INDEX IF NOT EXISTS idx_contacts_phone_jid ON contacts(phone_jid);

-- Chat/conversation directory
CREATE TABLE IF NOT EXISTS chats (
    chat_jid        TEXT PRIMARY KEY,
    chat_name       TEXT,
    chat_phone      TEXT,
    is_group        INTEGER DEFAULT 0,
    is_newsletter   INTEGER DEFAULT 0,
    unread_count    INTEGER DEFAULT 0,
    last_activity   INTEGER,
    mute_expiration INTEGER DEFAULT 0,
    is_read_only    INTEGER DEFAULT 0
);

-- Group metadata (only for group chats)
CREATE TABLE IF NOT EXISTS groups (
    group_jid       TEXT PRIMARY KEY,
    subject         TEXT,
    description     TEXT,
    owner_lid       TEXT,
    owner_phone     TEXT,
    creation_time   INTEGER,
    participant_count INTEGER DEFAULT 0,
    FOREIGN KEY (group_jid) REFERENCES chats(chat_jid)
);

-- Main message table — fully self-contained, no joins needed for basic use
CREATE TABLE IF NOT EXISTS messages (
    rowid               INTEGER PRIMARY KEY AUTOINCREMENT,
    msg_key             TEXT,
    msg_id              TEXT,
    chat_jid            TEXT,
    chat_name           TEXT,
    chat_phone          TEXT,
    sender_jid          TEXT,
    sender_phone        TEXT,
    sender_name         TEXT,
    from_me             INTEGER,
    timestamp           INTEGER,
    text                TEXT,
    is_group            INTEGER DEFAULT 0,
    -- Message type (chat/image/video/sticker/ptt/document/call_log/etc.)
    msg_type            TEXT,
    -- Reply / quote context
    quoted_stanza_id    TEXT,
    quoted_participant  TEXT,
    quoted_msg_body     TEXT,
    quoted_msg_type     TEXT,
    -- Call log fields
    call_duration       INTEGER,
    call_outcome        TEXT,
    is_video_call       INTEGER DEFAULT 0,
    -- Media metadata
    media_mime_type     TEXT,
    media_filename      TEXT,
    media_size          INTEGER,
    -- Source provenance for forensic audit/replay
    source              TEXT,
    source_id           TEXT,
    source_chat_id      TEXT,
    source_recovery     TEXT,
    store8_decrypted_text TEXT,
    store8_decryption_status TEXT,
    text_conflict_status TEXT,
    body_status         TEXT,
    media_case_path     TEXT,
    media_sha256        TEXT,
    media_status        TEXT,
    is_edited           INTEGER DEFAULT 0,
    edited_at           INTEGER,
    edit_count          INTEGER DEFAULT 0,
    edit_history_status TEXT,
    FOREIGN KEY (chat_jid) REFERENCES chats(chat_jid)
);
CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_jid);
CREATE INDEX IF NOT EXISTS idx_messages_chat_ts ON messages(chat_jid, timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_msg_key ON messages(msg_key);
CREATE INDEX IF NOT EXISTS idx_messages_msgid_ts ON messages(msg_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_chat_msgid_ts ON messages(chat_jid, msg_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_jid);
CREATE INDEX IF NOT EXISTS idx_messages_type ON messages(msg_type);
CREATE INDEX IF NOT EXISTS idx_messages_body_status ON messages(body_status);
CREATE INDEX IF NOT EXISTS idx_messages_edit ON messages(is_edited, edited_at);

-- Local media files copied into the case. These are evidence objects, not UI
-- cache entries; every local file gets a hash and a case-relative path.
CREATE TABLE IF NOT EXISTS media_assets (
    asset_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    msg_key             TEXT,
    chat_jid            TEXT,
    original_path       TEXT,
    case_relative_path  TEXT,
    filename            TEXT,
    mime_type           TEXT,
    size                INTEGER,
    sha256              TEXT,
    acquisition_method  TEXT,
    status              TEXT,
    FOREIGN KEY (msg_key) REFERENCES messages(msg_key)
);
CREATE INDEX IF NOT EXISTS idx_media_assets_msg_key ON media_assets(msg_key);
CREATE INDEX IF NOT EXISTS idx_media_assets_filename ON media_assets(filename);

-- Delivery/read receipts for sent messages
CREATE TABLE IF NOT EXISTS message_receipts (
    msg_key             TEXT,
    receiver_jid        TEXT,
    receiver_phone      TEXT,
    receiver_name       TEXT,
    delivery_time       INTEGER,
    read_time           INTEGER,
    played_time         INTEGER,
    PRIMARY KEY (msg_key, receiver_jid),
    FOREIGN KEY (msg_key) REFERENCES messages(msg_key)
);

-- Reactions on messages
CREATE TABLE IF NOT EXISTS reactions (
    parent_msg_key      TEXT,
    sender_jid          TEXT,
    sender_phone        TEXT,
    sender_name         TEXT,
    reaction_text       TEXT,
    timestamp           INTEGER,
    FOREIGN KEY (parent_msg_key) REFERENCES messages(msg_key)
);
CREATE INDEX IF NOT EXISTS idx_reactions_parent_sender_ts ON reactions(parent_msg_key, sender_jid, sender_phone, sender_name, timestamp);

-- Mention metadata preserved from Store 8/runtime rows when WhatsApp exposes
-- it. The Reader uses this instead of guessing raw @ text whenever possible.
CREATE TABLE IF NOT EXISTS message_mentions (
    msg_key             TEXT,
    chat_jid            TEXT,
    mention_index       INTEGER,
    kind                TEXT,
    target_jid          TEXT,
    target_phone        TEXT,
    target_name         TEXT,
    display_text        TEXT,
    source              TEXT,
    confidence          TEXT,
    PRIMARY KEY (msg_key, mention_index),
    FOREIGN KEY (msg_key) REFERENCES messages(msg_key)
);
CREATE INDEX IF NOT EXISTS idx_message_mentions_msg_key ON message_mentions(msg_key);

-- Edit evidence. WhatsApp normally only exposes an "Edited" label, but Store 8
-- can preserve explicit protocol rows and quote snapshots. Keep this as
-- evidence, not as invented history.
CREATE TABLE IF NOT EXISTS message_edits (
    target_msg_key      TEXT,
    target_chat_jid     TEXT,
    target_msg_id       TEXT,
    edit_event_msg_key  TEXT,
    edit_index          INTEGER,
    edited_at           INTEGER,
    editor_jid          TEXT,
    editor_phone        TEXT,
    editor_name         TEXT,
    previous_text       TEXT,
    new_text            TEXT,
    source              TEXT,
    confidence          TEXT,
    provenance_sha256   TEXT,
    PRIMARY KEY (target_msg_key, edit_index),
    FOREIGN KEY (target_msg_key) REFERENCES messages(msg_key)
);
CREATE INDEX IF NOT EXISTS idx_message_edits_target ON message_edits(target_msg_key);
CREATE INDEX IF NOT EXISTS idx_message_edits_event ON message_edits(edit_event_msg_key);

-- Group participants
CREATE TABLE IF NOT EXISTS group_participants (
    group_jid       TEXT,
    participant_lid TEXT,
    participant_phone TEXT,
    participant_name TEXT,
    is_admin        INTEGER DEFAULT 0,
    is_super_admin  INTEGER DEFAULT 0,
    FOREIGN KEY (group_jid) REFERENCES groups(group_jid)
);
CREATE INDEX IF NOT EXISTS idx_group_participants_group ON group_participants(group_jid);

-- Summary view (auto-generated convenience)
CREATE VIEW IF NOT EXISTS chat_summary AS
SELECT
    c.chat_jid,
    c.chat_name,
    c.is_group,
    c.is_newsletter,
    COUNT(m.rowid) AS message_count,
    SUM(CASE WHEN m.from_me = 1 THEN 1 ELSE 0 END) AS sent_count,
    SUM(CASE WHEN m.from_me = 0 THEN 1 ELSE 0 END) AS received_count,
    MIN(m.timestamp) AS first_message,
    MAX(m.timestamp) AS last_message
FROM chats c
LEFT JOIN messages m ON c.chat_jid = m.chat_jid
GROUP BY c.chat_jid
ORDER BY last_message DESC;
"""


def split_unified_schema(schema):
    """Return (tables_and_views, indexes) so bulk loads can defer index work."""
    table_statements = []
    index_statements = []
    statement_lines = []
    index_re = re.compile(r"^\s*(?:--[^\n]*\n\s*)*CREATE\s+INDEX\b", re.IGNORECASE)

    for line in schema.splitlines():
        statement_lines.append(line)
        statement = "\n".join(statement_lines).strip()
        if not statement or not sqlite3.complete_statement(statement):
            continue
        if index_re.match(statement):
            index_statements.append(statement)
        else:
            table_statements.append(statement)
        statement_lines = []

    trailing = "\n".join(statement_lines).strip()
    if trailing:
        table_statements.append(trailing)

    return "\n".join(table_statements) + "\n", "\n".join(index_statements) + "\n"


UNIFIED_TABLE_SCHEMA, UNIFIED_INDEX_SCHEMA = split_unified_schema(UNIFIED_SCHEMA)


def create_unified_indexes(conn):
    """Create query indexes after bulk inserts to avoid per-row index churn.

    Wraps all 18 CREATE INDEX statements in one BEGIN/COMMIT so the pager
    cache stays warm across statements — journal_mode=MEMORY is already
    the writer default, so this is a cache-locality win, not an fsync win.
    Temporarily raises PRAGMA cache_size to 256 MiB for the index build,
    then restores the caller's 128 MiB default. Safe: the bump only lives
    for this call and only touches page-cache size, not durability.
    """
    prior_cache_size = None
    try:
        row = conn.execute("PRAGMA cache_size").fetchone()
        if row is not None:
            prior_cache_size = row[0]
    except sqlite3.Error:
        prior_cache_size = None
    try:
        conn.execute("PRAGMA cache_size=-262144")  # 256 MiB, temporary
    except sqlite3.Error:
        pass
    in_txn_before = getattr(conn, "in_transaction", False)
    try:
        # executescript issues its own COMMIT before running, so any pending
        # writes from the caller are flushed first. Then we open one fresh
        # transaction around every CREATE INDEX statement.
        conn.executescript("BEGIN;\n" + UNIFIED_INDEX_SCHEMA + "\nCOMMIT;\n")
    finally:
        if prior_cache_size is not None:
            try:
                conn.execute(f"PRAGMA cache_size={int(prior_cache_size)}")
            except sqlite3.Error:
                pass
        # If caller was mid-transaction before we entered, restore that
        # state by opening a fresh implicit transaction on next write.
        # sqlite3 handles this automatically on the next execute().
        _ = in_txn_before  # kept for readability; no explicit action needed


def configure_unified_output_connection(conn):
    """Tune the generated unified DB connection for large one-pass builds."""
    conn.execute("PRAGMA journal_mode=MEMORY")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-131072")
    conn.execute("PRAGMA mmap_size=268435456")
    conn.execute("PRAGMA locking_mode=EXCLUSIVE")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

JID_SUFFIXES = ('@lid', '@g.us', '@c.us', '@s.whatsapp.net', '@newsletter')


def find_first_jid_suffix(value: str):
    """Return (suffix_start, suffix_end) for the earliest WhatsApp JID suffix."""
    if not value:
        return None, None
    best = None
    for suffix in JID_SUFFIXES:
        idx = value.find(suffix)
        if idx != -1 and (best is None or idx < best[0]):
            best = (idx, idx + len(suffix))
    return best if best else (None, None)


@functools.lru_cache(maxsize=16384)
def _normalize_chat_id_cached(chat_id: str):
    """Normalize string chat ids after callers coerce raw values safely."""
    if not chat_id:
        return None, None, None

    suffix_start, suffix_end = find_first_jid_suffix(chat_id)
    if suffix_end is None:
        return chat_id, None, None

    chat_jid = chat_id[:suffix_end]
    remainder = chat_id[suffix_end:].lstrip('_')
    stanza_id = remainder or None
    sender_jid = None

    if remainder:
        sender_start_idx, _ = find_first_jid_suffix(remainder)
        if sender_start_idx is not None:
            underscore = remainder.rfind('_', 0, sender_start_idx)
            if underscore != -1:
                stanza_id = remainder[:underscore] or None
                sender_jid = remainder[underscore + 1:] or None

    return chat_jid, stanza_id, sender_jid


def normalize_chat_id(chat_id: str):
    """Normalize genericStorage composite chat ids to (chat_jid, stanza, sender)."""
    return _normalize_chat_id_cached(safe_str(chat_id) or "")


def parse_msg_key(msg_key: str):
    """Parse a WhatsApp msgKey like 'true_chatJid_stanzaId' or
    'true_groupJid_stanzaId_senderJid' into components."""
    if not msg_key or '_' not in msg_key:
        return None, None, None, None

    parts = msg_key.split('_', 2)  # Split into at most 3: direction, jid+rest
    if len(parts) < 2:
        return None, None, None, None

    direction = parts[0]
    from_me = 1 if direction == 'true' else 0

    remainder = parts[1] if len(parts) == 2 else parts[1] + '_' + parts[2]

    chat_jid, stanza_and_sender, normalized_sender = normalize_chat_id(remainder)

    if not chat_jid:
        return from_me, None, None, None

    # For group messages: stanzaId_senderJid
    sender_jid = normalized_sender
    stanza_id = stanza_and_sender

    if stanza_and_sender and not sender_jid:
        for suffix in JID_SUFFIXES:
            idx = stanza_and_sender.find(suffix)
            if idx != -1:
                # Everything before the sender JID start is the stanza ID
                # Find the _ before the sender JID
                sender_start = stanza_and_sender.rfind('_', 0, idx)
                if sender_start != -1:
                    stanza_id = stanza_and_sender[:sender_start]
                    sender_jid = stanza_and_sender[sender_start + 1:]
                break

    return from_me, chat_jid, stanza_id, sender_jid


def extract_phone(jid: str) -> str:
    """Extract phone number from a JID like '15550101234@c.us' or
    '15550101234@s.whatsapp.net'."""
    if not jid:
        return None
    if '@c.us' in jid:
        return jid.split('@')[0]
    if '@s.whatsapp.net' in jid:
        return jid.split('@')[0]
    return None


def safe_int(val):
    """Convert a timestamp value to integer, handling None and float."""
    if val is None or val == '<Undefined>':
        return None
    try:
        v = int(float(val))
        return v if v > 0 else None
    except (ValueError, TypeError):
        return None


def safe_str(val):
    """Clean string value."""
    if val is None or str(val) == '<Undefined>':
        return None
    if isinstance(val, dict) and '_serialized' in val:
        val = val['_serialized']
    elif isinstance(val, dict):
        return None

    s = str(val).strip()
    return s if s else None


URL_IDENTITY_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def message_identity_text(text):
    """Normalize text only enough to match the same row across evidence stores."""
    value = safe_str(text) or ''
    urls = URL_IDENTITY_RE.findall(value)
    if urls:
        return urls[0].rstrip(").,;]")
    return value


def record_warning(message, **context):
    item = {"message": message, **context}
    EXTRACTION_EVENTS["warnings"].append(item)


def record_skipped_record(store_name, reason, **context):
    item = {"store": store_name, "reason": reason, **context}
    EXTRACTION_EVENTS["skipped_records"].append(item)


def record_collision(kind, attempted, inserted, **context):
    ignored = max(0, int(attempted or 0) - int(inserted or 0))
    if ignored:
        EXTRACTION_EVENTS["collisions"].append({
            "kind": kind,
            "attempted": int(attempted),
            "inserted": int(inserted),
            "ignored": ignored,
            **context,
        })


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(value):
    return hashlib.sha256(bytes(value)).hexdigest()


def _coerce_bytes(value):
    """Best-effort conversion for WebView2/CCL decoded binary values."""
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, memoryview):
        return value.tobytes()
    key_data = getattr(value, "key_data", None)
    if key_data is not None:
        return _coerce_bytes(key_data)
    if isinstance(value, dict):
        for key in ("_data", "data", "key_data", "buffer", "bytes"):
            if key in value:
                coerced = _coerce_bytes(value.get(key))
                if coerced is not None:
                    return coerced
        return None
    if isinstance(value, (list, tuple)):
        try:
            return bytes(int(x) & 0xff for x in value)
        except Exception:
            return None
    if isinstance(value, str):
        text = value.strip()
        if (
            len(text) >= 2
            and text[0] == text[-1]
            and text[0] in ("'", '"')
        ):
            text = text[1:-1].strip()
        compact = re.sub(r"\s+", "", text)
        if compact and len(compact) % 2 == 0 and re.fullmatch(r"[0-9A-Fa-f]+", compact):
            try:
                return bytes.fromhex(compact)
            except ValueError:
                pass
        if compact:
            try:
                decoded = base64.b64decode(compact, validate=True)
                if decoded:
                    return decoded
            except (binascii.Error, ValueError):
                pass
        return text.encode("utf-8", "replace")
    return None


def _public_artifact_entry(name, source, value, role, kind="local"):
    raw = _coerce_bytes(value)
    return {
        "name": str(name),
        "source": str(source),
        "role": role,
        "kind": kind,
        "length": len(raw) if raw is not None else 0,
        "sha256": sha256_bytes(raw) if raw is not None else None,
    }


def _candidate(name, source, value, role, kind="local"):
    raw = _coerce_bytes(value)
    if not raw:
        return None, None
    return (
        {"name": str(name), "source": str(source), "role": role, "kind": kind, "value": raw},
        _public_artifact_entry(name, source, raw, role, kind=kind),
    )


@dataclass
class Store8CryptoContext:
    ikm_candidates: list = field(default_factory=list)
    salt_candidates: list = field(default_factory=list)
    info_candidates: list = field(default_factory=list)
    artifact_inventory: dict = field(default_factory=dict)


# ─── Store 8 opaque decryption caches ────────────────────────────────────────
# Bounded memoization for HKDF derivations and AES algorithm objects on the
# Store 8 opaque hot path (`decrypt_store8_opaque_record`). Across ~5k opaque
# records × 4 ikm × 3 salt × 3 info = ~180k trial derivations, only ~10-40
# unique (ikm, salt, info, length) triples typically fire — plain dict is the
# fastest safe cache. FIFO eviction at cap keeps memory bounded even under
# pathological per-message salt rotation. See docs/kb/perf/Bottlenecks.md.
_HKDF_CACHE_CAP = 4096
_HKDF_CACHE: "dict[tuple, bytes]" = {}
_AES_ALG_CACHE_CAP = 512
_AES_ALG_CACHE: "dict[bytes, object]" = {}


def _hkdf_sha256_uncached(ikm: bytes, salt: bytes, info: bytes, length: int) -> bytes:
    """Pure HKDF-SHA256 derivation; assumes bytes inputs already normalized."""
    hash_len = hashlib.sha256().digest_size
    if length > 255 * hash_len:
        raise ValueError("HKDF output length is too large")
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    okm = b""
    block = b""
    counter = 1
    while len(okm) < length:
        block = hmac.new(prk, block + info + bytes([counter]), hashlib.sha256).digest()
        okm += block
        counter += 1
    return okm[:length]


def hkdf_sha256(ikm, salt, info=b"", length=16):
    """RFC 5869 HKDF-SHA256 with bounded memoization on (ikm, salt, info, length)."""
    ikm = _coerce_bytes(ikm) or b""
    salt = _coerce_bytes(salt) or bytes(hashlib.sha256().digest_size)
    info = _coerce_bytes(info) or b""
    if length <= 0:
        return b""
    key = (ikm, salt, info, length)
    hit = _HKDF_CACHE.get(key)
    if hit is not None:
        return hit
    derived = _hkdf_sha256_uncached(ikm, salt, info, length)
    if len(_HKDF_CACHE) >= _HKDF_CACHE_CAP:
        # FIFO eviction: drop oldest insertion. Preserves dict ordering
        # semantics (Python 3.7+) without pulling in OrderedDict.
        try:
            _HKDF_CACHE.pop(next(iter(_HKDF_CACHE)))
        except StopIteration:
            pass
    _HKDF_CACHE[key] = derived
    return derived


def _get_cached_aes_algorithm(key: bytes):
    """Reuse `cryptography` algorithms.AES(key) objects; the algorithm object
    is safe to share across independent CBC decryptor instances."""
    try:
        from cryptography.hazmat.primitives.ciphers import algorithms
    except ImportError:
        return None
    cached = _AES_ALG_CACHE.get(key)
    if cached is not None:
        return cached
    alg = algorithms.AES(key)
    if len(_AES_ALG_CACHE) >= _AES_ALG_CACHE_CAP:
        try:
            _AES_ALG_CACHE.pop(next(iter(_AES_ALG_CACHE)))
        except StopIteration:
            pass
    _AES_ALG_CACHE[key] = alg
    return alg


def reset_store8_opaque_caches():
    """Test/diagnostic hook: clear HKDF + AES-algorithm caches."""
    _HKDF_CACHE.clear()
    _AES_ALG_CACHE.clear()


def _aes_backend_decrypt(ciphertext, key, iv):
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, modes
        alg = _get_cached_aes_algorithm(key)
        if alg is None:
            from cryptography.hazmat.primitives.ciphers import algorithms
            alg = algorithms.AES(key)
        decryptor = Cipher(alg, modes.CBC(iv)).decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    except ImportError:
        try:
            from Crypto.Cipher import AES
            return AES.new(key, AES.MODE_CBC, iv).decrypt(ciphertext)
        except ImportError as exc:
            raise RuntimeError("No AES-CBC backend available; install cryptography or pycryptodome in the offline kit") from exc


def aes_128_cbc_pkcs7_decrypt(ciphertext, key, iv):
    ciphertext = _coerce_bytes(ciphertext)
    key = _coerce_bytes(key)
    iv = _coerce_bytes(iv)
    if not ciphertext or len(ciphertext) % 16 != 0:
        raise ValueError("AES-CBC ciphertext length must be a positive multiple of 16")
    if not key or len(key) != 16:
        raise ValueError("AES-128-CBC key must be exactly 16 bytes")
    if not iv or len(iv) != 16:
        raise ValueError("AES-CBC IV must be exactly 16 bytes")
    padded = _aes_backend_decrypt(ciphertext, key, iv)
    pad_len = padded[-1]
    if pad_len < 1 or pad_len > 16:
        raise ValueError("Invalid PKCS#7 padding")
    if padded[-pad_len:] != bytes([pad_len]) * pad_len:
        raise ValueError("Invalid PKCS#7 padding bytes")
    return padded[:-pad_len]


def _find_first_text_field(obj):
    if isinstance(obj, dict):
        for key in ("body", "caption", "text", "message", "title", "description"):
            val = obj.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip(), key
        for val in obj.values():
            found = _find_first_text_field(val)
            if found:
                return found
    elif isinstance(obj, list):
        for val in obj:
            found = _find_first_text_field(val)
            if found:
                return found
    return None


def parse_decrypted_store8_plaintext(plaintext):
    """Extract visible message text only from recognized plaintext structures."""
    plaintext = _coerce_bytes(plaintext)
    if not plaintext:
        return None

    for encoding in ("utf-8", "utf-16-le", "utf-16-be"):
        try:
            decoded = plaintext.decode(encoding)
        except UnicodeDecodeError:
            continue
        stripped = decoded.strip("\x00\r\n\t ")
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            parsed = None
        if parsed is not None:
            found = _find_first_text_field(parsed)
            if found:
                body, field_name = found
                return {"body": body, "field": field_name, "parser": f"json/{encoding}"}
        # Strict fallback for serialized JSON-like buffers only. Do not return
        # arbitrary printable strings; wrong crypto material can decrypt to noise.
        match = re.search(r'"(?:body|caption|text)"\s*:\s*"((?:\\.|[^"\\])*)"', stripped)
        if match:
            try:
                body = json.loads(f'"{match.group(1)}"')
            except json.JSONDecodeError:
                body = match.group(1)
            if str(body).strip():
                return {"body": str(body).strip(), "field": "regex", "parser": f"json-fragment/{encoding}"}
    return None


def decrypt_store8_opaque_record(msg_rec, context):
    opaque = msg_rec.get("msgRowOpaqueData") if isinstance(msg_rec, dict) else None
    if not isinstance(opaque, dict):
        return {"status": "skipped", "reason": "no_msgRowOpaqueData"}

    scheme = safe_int(opaque.get("_scheme")) or 1
    key_id = safe_int(opaque.get("_keyId")) or safe_int(opaque.get("keyId"))
    ciphertext = _coerce_bytes(opaque.get("_data"))
    iv = _coerce_bytes(opaque.get("iv"))
    result_base = {
        "scheme": scheme,
        "key_id": key_id,
        "ciphertext_length": len(ciphertext) if ciphertext else 0,
        "iv_length": len(iv) if iv else 0,
    }

    if scheme != 1:
        return {"status": "unsupported", "blocker": "unsupported_scheme", **result_base}
    if not ciphertext or not iv:
        return {"status": "failed", "blocker": "missing_ciphertext_or_iv", **result_base}
    if not context.ikm_candidates:
        return {"status": "blocked", "blocker": "local_crypto_artifacts_missing", **result_base}
    if not context.salt_candidates:
        return {"status": "blocked", "blocker": "network_salt_missing", **result_base}

    info_candidates = context.info_candidates or [
        {"name": "empty", "source": "derived", "role": "hkdf_info", "value": b""}
    ]
    attempts = 0
    parser_failures = 0
    last_error = None
    for ikm in context.ikm_candidates:
        for salt in context.salt_candidates:
            for info in info_candidates:
                attempts += 1
                try:
                    key = hkdf_sha256(ikm["value"], salt["value"], info.get("value") or b"", 16)
                    plaintext = aes_128_cbc_pkcs7_decrypt(ciphertext, key, iv)
                    parsed = parse_decrypted_store8_plaintext(plaintext)
                    if not parsed:
                        parser_failures += 1
                        continue
                    return {
                        "status": "decrypted",
                        "body": parsed["body"],
                        "field": parsed.get("field"),
                        "parser": parsed.get("parser"),
                        "attempts": attempts,
                        "ikm": {"name": ikm.get("name"), "source": ikm.get("source")},
                        "salt": {"name": salt.get("name"), "source": salt.get("source")},
                        "info": {"name": info.get("name"), "source": info.get("source")},
                        "plaintext_sha256": sha256_bytes(plaintext),
                        **result_base,
                    }
                except Exception as exc:
                    last_error = exc.__class__.__name__

    return {
        "status": "failed",
        "blocker": "plaintext_parser_failed" if parser_failures else "decrypt_failed",
        "attempts": attempts,
        "parser_failures": parser_failures,
        "last_error": last_error,
        **result_base,
    }


def _counter_to_json_dict(counter):
    def sort_key(item):
        key, _ = item
        try:
            return (0, int(key))
        except Exception:
            return (1, str(key))
    return {str(k): v for k, v in sorted(counter.items(), key=sort_key)}


def profile_store8_crypto_data(messages, artifacts_report=None, decryption_report=None):
    profile = {
        "schema": "waren6.store8-crypto-profile.v1",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "store8_total_rows": len(messages or []),
        "store8_opaque_rows": 0,
        "store8_plain_body_rows": 0,
        "schemes": {},
        "key_ids": {},
        "iv_lengths": {},
        "ciphertext_lengths": {},
        "unsupported_schemes": [],
        "artifact_summary": {},
    }
    schemes = Counter()
    key_ids = Counter()
    iv_lengths = Counter()
    data_lengths = Counter()
    unsupported_schemes = set()

    for msg in messages or []:
        body = safe_str((msg or {}).get("body") or (msg or {}).get("caption") or (msg or {}).get("text"))
        if body:
            profile["store8_plain_body_rows"] += 1
        opaque = msg.get("msgRowOpaqueData") if isinstance(msg, dict) else None
        if not isinstance(opaque, dict):
            continue
        ciphertext = _coerce_bytes(opaque.get("_data"))
        iv = _coerce_bytes(opaque.get("iv"))
        if not ciphertext or iv is None:
            continue
        profile["store8_opaque_rows"] += 1
        scheme = safe_int(opaque.get("_scheme")) or 1
        key_id = safe_int(opaque.get("_keyId")) or safe_int(opaque.get("keyId")) or "unknown"
        schemes[scheme] += 1
        key_ids[key_id] += 1
        iv_lengths[len(iv)] += 1
        data_lengths[len(ciphertext)] += 1
        if scheme != 1:
            unsupported_schemes.add(scheme)

    profile["schemes"] = _counter_to_json_dict(schemes)
    profile["key_ids"] = _counter_to_json_dict(key_ids)
    profile["iv_lengths"] = _counter_to_json_dict(iv_lengths)
    profile["ciphertext_lengths"] = _counter_to_json_dict(data_lengths)
    profile["unsupported_schemes"] = sorted(str(x) for x in unsupported_schemes)
    if artifacts_report:
        summary = artifacts_report.get("summary", {})
        profile["artifact_summary"] = {
            key: summary.get(key, 0)
            for key in ("ikm_candidates", "salt_candidates", "info_candidates", "artifacts")
        }
    if decryption_report:
        profile["decryption_summary"] = decryption_report.get("summary", {})
    return profile


def decrypt_store8_opaque_messages(messages, context, enabled=False):
    report = {
        "schema": "waren6.store8-decryption-report.v1",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "enabled": bool(enabled),
        "summary": {
            "store8_rows": len(messages or []),
            "opaque_rows": 0,
            "attempted": 0,
            "decrypted": 0,
            "blocked": 0,
            "failed": 0,
            "unsupported": 0,
            "network_salt_missing": 0,
            "local_crypto_artifacts_missing": 0,
            "plaintext_parser_failed": 0,
            "decrypt_failed": 0,
        },
        "samples": [],
    }
    for msg in messages or []:
        if not has_msg_row_opaque_data(msg):
            continue
        report["summary"]["opaque_rows"] += 1
        if not enabled:
            continue
        report["summary"]["attempted"] += 1
        result = decrypt_store8_opaque_record(msg, context)
        safe_result = {k: v for k, v in result.items() if k != "body"}
        if result.get("body"):
            safe_result["body_sha256"] = sha256_bytes(result["body"].encode("utf-8", "replace"))
            safe_result["body_length"] = len(result["body"])
        msg["_waren6_opaque_decryption"] = result
        status = result.get("status")
        blocker = result.get("blocker")
        if status == "decrypted":
            report["summary"]["decrypted"] += 1
        elif status == "blocked":
            report["summary"]["blocked"] += 1
        elif status == "unsupported":
            report["summary"]["unsupported"] += 1
        else:
            report["summary"]["failed"] += 1
        if blocker in report["summary"]:
            report["summary"][blocker] += 1
        if len(report["samples"]) < 20:
            report["samples"].append({
                "msg_key": safe_str(msg.get("id")),
                "status": status,
                "blocker": blocker,
                "details": safe_result,
            })
    if enabled and report["summary"]["opaque_rows"] and not context.salt_candidates:
        record_warning(
            "Store 8 opaque decryption is blocked because the WebWA network salt was not found in offline artifacts.",
            count=report["summary"]["opaque_rows"],
            blocker="network_salt_missing",
        )
    return report


def _extract_salt_values_from_json(obj):
    keys = {
        "salt",
        "network_salt",
        "webwa_network_salt",
        "opaque_network_salt",
        "store8_network_salt",
    }
    found = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key) in keys:
                found.append((str(key), value))
            found.extend(_extract_salt_values_from_json(value))
    elif isinstance(obj, list):
        for value in obj:
            found.extend(_extract_salt_values_from_json(value))
    return found


def load_opaque_salt_file(path):
    path = pathlib.Path(path)
    raw_text = path.read_text(encoding="utf-8", errors="replace").strip()
    candidates = []
    artifacts = []

    parsed = None
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    salt_values = _extract_salt_values_from_json(parsed) if parsed is not None else [("network_salt", raw_text)]
    for name, value in salt_values:
        candidate, entry = _candidate(name, str(path), value, "network_salt", kind="examiner_supplied")
        if candidate:
            candidates.append(candidate)
            artifacts.append(entry)

    inventory = {
        "schema": "waren6.opaque-salt-file.v1",
        "source": str(path),
        "artifacts": artifacts,
    }
    return candidates, inventory


_SALT_TOKEN_RE = re.compile(
    rb"(?i)(?:webwa[_-]?network[_-]?salt|network[_-]?salt|opaque[_-]?network[_-]?salt|store8[_-]?network[_-]?salt|salt)"
    rb"[^A-Za-z0-9+/=]{0,48}"
    rb"([A-Fa-f0-9]{8,512}|[A-Za-z0-9+/]{8,684}={0,2})"
)


def extract_opaque_salt_candidates_from_bytes(data, source, max_candidates=200):
    """Extract named salt-looking values from bytes without exposing raw values."""
    data = bytes(data or b"")
    candidates = []
    seen = set()
    for match in _SALT_TOKEN_RE.finditer(data):
        token = match.group(1).decode("ascii", "ignore")
        candidate, public = _candidate(
            f"salt_hunter_candidate_{len(candidates) + 1}",
            source,
            token,
            "network_salt",
            kind="salt_hunter",
        )
        if not candidate:
            continue
        dedupe_key = public.get("sha256")
        if not dedupe_key or dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        public = {
            **public,
            "offset": match.start(1),
            "encoding": "hex_or_base64",
        }
        candidate["public"] = public
        candidates.append(candidate)
        if len(candidates) >= max_candidates:
            break
    return candidates


def _iter_salt_hunter_files(search_paths, max_files=2000, max_file_bytes=25 * 1024 * 1024):
    skip_dirs = {
        "reports",
        "__pycache__",
        "target",
        "node_modules",
    }
    seen = set()
    count = 0
    for raw_path in search_paths or []:
        path = pathlib.Path(raw_path)
        if not path.exists():
            continue
        if path.is_file():
            files = [path]
        else:
            files = []
            for root, dirs, filenames in os.walk(path):
                dirs[:] = [d for d in dirs if d not in skip_dirs]
                for filename in filenames:
                    files.append(pathlib.Path(root) / filename)
        for file_path in files:
            try:
                resolved = file_path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                size = resolved.stat().st_size
                if size <= 0 or size > max_file_bytes:
                    continue
            except OSError:
                continue
            yield resolved
            count += 1
            if count >= max_files:
                return


def _store8_probe_messages(messages, limit=8):
    opaque = [m for m in messages or [] if has_msg_row_opaque_data(m)]
    opaque.sort(key=lambda msg: len(_coerce_bytes((msg.get("msgRowOpaqueData") or {}).get("_data")) or b""))
    return opaque[:limit]


def hunt_store8_network_salts(
    search_paths,
    messages,
    context,
    max_files=2000,
    max_file_bytes=25 * 1024 * 1024,
    max_candidates=500,
    probe_limit=8,
    fast_mode=False,
    fast_min_validated=3,
    fast_dry_files=32,
):
    """Scan offline artifacts for salt candidates and accept only verified ones.

    fast_mode: opt-in early exit. Off by default because multi-salt cases exist
    (WA reinstall, salt rotation) and dropping later candidates loses yield.
    When on: break the outer file loop once we have `fast_min_validated`
    validated candidates AND have scanned `fast_dry_files` consecutive files
    without a new validated hit.
    """
    report = {
        "schema": "waren6.store8-salt-hunt.v1",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "search_paths": [str(p) for p in (search_paths or [])],
        "summary": {
            "files_scanned": 0,
            "candidate_values": 0,
            "unique_candidates": 0,
            "tested_candidates": 0,
            "validated_candidates": 0,
            "probe_messages": 0,
            "blocked": None,
            "fast_mode": bool(fast_mode),
            "early_exit": False,
        },
        "candidates": [],
        "validated": [],
        "warnings": [],
    }

    probes = _store8_probe_messages(messages, limit=probe_limit)
    report["summary"]["probe_messages"] = len(probes)
    if not probes:
        report["summary"]["blocked"] = "no_opaque_probe_messages"
        return report
    if not context.ikm_candidates:
        report["summary"]["blocked"] = "local_crypto_artifacts_missing"
        return report

    seen_candidates = {sha256_bytes(c["value"]) for c in context.salt_candidates if c.get("value")}
    accepted_hashes = set(seen_candidates)
    dry_files_streak = 0

    for file_path in _iter_salt_hunter_files(search_paths, max_files=max_files, max_file_bytes=max_file_bytes):
        report["summary"]["files_scanned"] += 1
        validated_before_file = report["summary"]["validated_candidates"]
        try:
            data = file_path.read_bytes()
        except OSError as exc:
            report["warnings"].append({"path": str(file_path), "error": str(exc)})
            continue
        candidates = extract_opaque_salt_candidates_from_bytes(
            data,
            str(file_path),
            max_candidates=max(1, max_candidates - report["summary"]["candidate_values"]),
        )
        report["summary"]["candidate_values"] += len(candidates)
        for candidate in candidates:
            digest = sha256_bytes(candidate["value"])
            if digest in seen_candidates:
                continue
            seen_candidates.add(digest)
            report["summary"]["unique_candidates"] += 1
            report["summary"]["tested_candidates"] += 1
            public = candidate.get("public") or _public_artifact_entry(
                candidate.get("name"),
                candidate.get("source"),
                candidate.get("value"),
                "network_salt",
                kind="salt_hunter",
            )
            if len(report["candidates"]) < 100:
                report["candidates"].append(public)

            probe_context = Store8CryptoContext(
                ikm_candidates=context.ikm_candidates,
                salt_candidates=[candidate],
                info_candidates=context.info_candidates,
            )
            for msg in probes:
                result = decrypt_store8_opaque_record(msg, probe_context)
                if result.get("status") != "decrypted":
                    continue
                if digest not in accepted_hashes:
                    context.salt_candidates.append(candidate)
                    accepted_hashes.add(digest)
                report["summary"]["validated_candidates"] += 1
                report["validated"].append({
                    **public,
                    "validated_with_msg_key": safe_str(msg.get("id")),
                    "sample_body_sha256": sha256_bytes(result["body"].encode("utf-8", "replace")),
                    "sample_body_length": len(result["body"]),
                    "attempts": result.get("attempts"),
                })
                break
            if report["summary"]["candidate_values"] >= max_candidates:
                break
        if report["summary"]["candidate_values"] >= max_candidates:
            break

        if fast_mode:
            gained = report["summary"]["validated_candidates"] - validated_before_file
            if gained > 0:
                dry_files_streak = 0
            else:
                dry_files_streak += 1
            if (report["summary"]["validated_candidates"] >= fast_min_validated
                    and dry_files_streak >= fast_dry_files):
                report["summary"]["early_exit"] = True
                report["summary"]["early_exit_reason"] = (
                    f"fast_mode: >={fast_min_validated} validated candidates and "
                    f"{dry_files_streak} consecutive files with no new hits"
                )
                break

    if not report["summary"]["validated_candidates"]:
        report["summary"]["blocked"] = "no_valid_network_salt_found"
    return report


def execute_many_counting(cursor, sql, rows, collision_kind=None):
    if isinstance(rows, (list, tuple)):
        row_count = len(rows)
        db_rows = rows
    else:
        db_rows = list(rows)
        row_count = len(db_rows)
    before = cursor.connection.total_changes
    cursor.executemany(sql, db_rows)
    inserted = cursor.connection.total_changes - before
    if collision_kind:
        record_collision(collision_kind, row_count, inserted)
    return inserted


def has_msg_row_opaque_data(msg_rec):
    opaque = msg_rec.get('msgRowOpaqueData') if isinstance(msg_rec, dict) else None
    if not isinstance(opaque, dict):
        return False
    return bool(opaque.get('_data')) and opaque.get('iv') is not None


def select_indexeddb_message_body(msg_rec):
    """Return (body, status) for a Store 8 message record."""
    body = safe_str(
        msg_rec.get('body') or
        msg_rec.get('caption') or
        msg_rec.get('text')
    )
    if body:
        return body, "plain"
    opaque_result = msg_rec.get("_waren6_opaque_decryption") if isinstance(msg_rec, dict) else None
    if isinstance(opaque_result, dict) and opaque_result.get("status") == "decrypted":
        recovered = safe_str(opaque_result.get("body"))
        if recovered:
            return recovered, "opaque_decrypted"
    if has_msg_row_opaque_data(msg_rec):
        return None, "opaque_unresolved"
    return None, "missing"


MEDIA_MESSAGE_TYPES = {
    "image", "video", "sticker", "ptt", "audio", "ptv", "document", "album", "gif",
}
CALL_MESSAGE_TYPES = {"call_log", "call", "call_log_group", "call_log_video"}
DELETED_MESSAGE_TYPES = {"revoked", "protocol"}
SYSTEM_MESSAGE_TYPES = {
    "notification", "ciphertext", "system", "groups_v4_invite", "newsletter_admin_invite",
    "poll_creation", "poll_update", "event_creation", "event_response",
    "e2e_notification", "gp2", "group_notification", "ephemeral_setting", "pin_v1",
}


def is_media_like_message(msg_type=None, media_mime_type=None, media_filename=None, media_size=None):
    msg_type = (msg_type or "").lower()
    mime = (media_mime_type or "").lower()
    return (
        msg_type in MEDIA_MESSAGE_TYPES
        or bool(media_filename)
        or bool(media_size)
        or mime.startswith(("image/", "video/", "audio/", "application/"))
    )


def classify_body_status(text=None, msg_type=None, source=None, source_recovery=None,
                         store8_status=None, media_mime_type=None,
                         media_filename=None, media_size=None):
    """Classify why a row has or does not have visible message text."""
    if text and str(text).strip():
        recovery = source_recovery or ""
        if store8_status == "runtime_store8_decoded" or "runtime" in recovery:
            return "runtime_store8_decoded"
        if store8_status == "opaque_decrypted" or "opaque_decrypted" in recovery:
            return "offline_store8_decrypted"
        if source and "genericStorage" in source:
            return "genericStorage_text"
        return "text_present"

    msg_type_l = (msg_type or "").lower()
    if msg_type_l in CALL_MESSAGE_TYPES or msg_type_l.startswith("call"):
        return "call_event"
    if msg_type_l in DELETED_MESSAGE_TYPES or "revoked" in msg_type_l or "deleted" in msg_type_l:
        return "revoked_or_deleted"
    if is_media_like_message(msg_type, media_mime_type, media_filename, media_size):
        return "media_only"
    if store8_status == "opaque_unresolved" or source_recovery == "store8_opaque_unresolved":
        return "opaque_unresolved"
    if msg_type_l in SYSTEM_MESSAGE_TYPES:
        return "system_event"
    return "missing_unexpected"


def initial_media_status(msg_type=None, media_mime_type=None, media_filename=None, media_size=None):
    if is_media_like_message(msg_type, media_mime_type, media_filename, media_size):
        return "metadata_only"
    return None


def runtime_supplement_text(record):
    """Return the best text field from a live-runtime Store 8 supplement row."""
    if not isinstance(record, dict):
        return None
    return safe_str(
        record.get("body") or
        record.get("caption") or
        record.get("text") or
        record.get("title") or
        record.get("description") or
        record.get("matched_text")
    )


def msg_key_from_value(value):
    """Normalize WhatsApp key values found as strings or protocol key objects."""
    text_value = safe_str(value)
    if text_value:
        return text_value
    if not isinstance(value, dict):
        return None

    direct = safe_str(
        value.get("_serialized")
        or value.get("serialized")
        or value.get("msg_key")
        or value.get("msgKey")
        or value.get("id")
    )
    if direct and "_" in direct:
        return direct

    remote = safe_str(
        value.get("remoteJid")
        or value.get("remote_jid")
        or value.get("chat_jid")
        or value.get("chatJid")
    )
    stanza = safe_str(
        value.get("stanzaId")
        or value.get("stanza_id")
        or value.get("id")
    )
    participant = safe_str(
        value.get("participant")
        or value.get("participantJid")
        or value.get("sender_jid")
    )
    from_me_raw = value.get("fromMe")
    if from_me_raw is None:
        from_me_raw = value.get("from_me")

    if remote and stanza:
        direction = "true" if bool(from_me_raw) else "false"
        if participant and "@g.us" in remote:
            return f"{direction}_{remote}_{stanza}_{participant}"
        return f"{direction}_{remote}_{stanza}"

    return direct


def edit_timestamp_seconds(value):
    ts = safe_int(value)
    if ts and ts > 10_000_000_000:
        return int(ts / 1000)
    return ts


def extract_edit_marker(record, msg_key):
    if not isinstance(record, dict) or not msg_key:
        return None
    edit_key = msg_key_from_value(
        record.get("latestEditMsgKey")
        or record.get("latest_edit_msg_key")
        or record.get("latestEditKey")
    )
    edited_at = edit_timestamp_seconds(
        record.get("latestEditSenderTimestampMs")
        or record.get("latest_edit_sender_timestamp_ms")
        or record.get("latestEditTimestamp")
        or record.get("latest_edit_timestamp")
    )
    if not edit_key and not edited_at:
        return None
    return {
        "target_msg_key": msg_key,
        "latest_edit_msg_key": edit_key,
        "edited_at": edited_at,
    }


def protocol_edit_target_key(record):
    if not isinstance(record, dict):
        return None
    nested = record.get("protocolMessage") or record.get("protocol_message") or {}
    target = (
        record.get("protocolMessageKey")
        or record.get("protocol_message_key")
        or record.get("editTargetMsgKey")
        or record.get("edit_target_msg_key")
    )
    if not target and isinstance(nested, dict):
        target = (
            nested.get("key")
            or nested.get("messageKey")
            or nested.get("message_key")
            or nested.get("protocolMessageKey")
        )
    return msg_key_from_value(target)


def is_message_edit_protocol(record):
    if not isinstance(record, dict):
        return False
    msg_type = (safe_str(record.get("type")) or "").lower()
    subtype = (safe_str(record.get("subtype")) or "").lower()
    edit_type = (safe_str(record.get("editMsgType") or record.get("edit_msg_type")) or "").lower()
    nested = record.get("protocolMessage") or record.get("protocol_message") or {}
    nested_type = ""
    if isinstance(nested, dict):
        nested_type = (safe_str(nested.get("type") or nested.get("subtype")) or "").lower()
    return (
        subtype == "message_edit"
        or edit_type == "message_edit"
        or nested_type == "message_edit"
        or (msg_type == "protocol" and bool(protocol_edit_target_key(record)))
    )


def extract_message_edit_event(record, event_msg_key=None, source="store8", new_text=None):
    if not is_message_edit_protocol(record):
        return None
    target_key = protocol_edit_target_key(record)
    if not target_key:
        return None
    event_key = event_msg_key or msg_key_from_value(record.get("id") or record.get("msg_key"))
    edited_at = edit_timestamp_seconds(
        record.get("latestEditSenderTimestampMs")
        or record.get("latest_edit_sender_timestamp_ms")
        or record.get("timestamp")
        or record.get("t")
    )
    body = new_text or runtime_supplement_text(record)
    if body is None:
        selected, _ = select_indexeddb_message_body(record)
        body = selected
    provenance = sha256_bytes(
        json.dumps(record, sort_keys=True, default=str).encode("utf-8", "replace")
    )
    return {
        "target_msg_key": target_key,
        "edit_event_msg_key": event_key,
        "edited_at": edited_at,
        "new_text": body,
        "source": source,
        "confidence": "high" if body else "medium",
        "provenance_sha256": provenance,
    }


def extract_quote_context(record):
    """Return normalized (stanza, participant, body, type) quote metadata."""
    if not isinstance(record, dict):
        return None, None, None, None

    quoted_stanza_id = safe_str(
        record.get("quotedStanzaID")
        or record.get("quotedStanzaId")
        or record.get("quoted_stanza_id")
        or record.get("quotedMsgId")
        or record.get("quoted_msg_id")
    )

    qp = (
        record.get("quotedParticipant")
        or record.get("quoted_participant")
        or record.get("quotedParticipantJid")
        or record.get("quoted_participant_jid")
    )
    quoted_participant = safe_str(qp)

    qm = record.get("quotedMsg") or record.get("quoted_msg")
    quoted_msg_type = safe_str(record.get("quoted_msg_type"))
    quoted_msg_body = safe_str(record.get("quoted_msg_body"))

    if isinstance(qm, dict):
        quoted_msg_type = quoted_msg_type or safe_str(qm.get("type"))
        quoted_msg_body = quoted_msg_body or safe_str(
            qm.get("body")
            or qm.get("caption")
            or qm.get("text")
            or qm.get("title")
            or qm.get("description")
        )

    return quoted_stanza_id, quoted_participant, quoted_msg_body, quoted_msg_type


MENTION_ALL_TOKENS = {"all", "@all", "everyone", "@everyone"}


def _mention_string_to_record(value):
    text = safe_str(value)
    if not text:
        return None
    lowered = text.lower()
    if lowered in MENTION_ALL_TOKENS:
        return {"kind": "all", "target_jid": None, "display_text": "@all"}
    if any(suffix in lowered for suffix in JID_SUFFIXES):
        return {"kind": "participant", "target_jid": text, "display_text": None}
    if text.startswith("@") and text[1:].isdigit():
        return {"kind": "participant", "target_jid": f"{text[1:]}@s.whatsapp.net", "display_text": text}
    return None


def _mention_dict_to_record(value):
    if not isinstance(value, dict):
        return None
    lowered_values = {
        (safe_str(value.get(key)) or "").lower()
        for key in ("kind", "type", "tag", "mentionType", "displayText", "display_text")
    }
    if lowered_values & MENTION_ALL_TOKENS:
        return {"kind": "all", "target_jid": None, "display_text": safe_str(value.get("displayText") or value.get("display_text")) or "@all"}

    target = (
        value.get("_serialized")
        or value.get("jid")
        or value.get("id")
        or value.get("target_jid")
        or value.get("participant")
        or value.get("recipient")
        or value.get("userJid")
    )
    if isinstance(target, dict):
        if target.get("_serialized"):
            target = target.get("_serialized")
        elif target.get("user") and target.get("server"):
            target = f"{target.get('user')}@{target.get('server')}"
    target = safe_str(target)
    if not target and value.get("user") and value.get("server"):
        target = f"{value.get('user')}@{value.get('server')}"
    rec = _mention_string_to_record(target)
    if not rec:
        return None
    display = safe_str(
        value.get("displayText")
        or value.get("display_text")
        or value.get("name")
        or value.get("pushName")
        or value.get("shortName")
    )
    if display:
        rec["display_text"] = display
    return rec


def _collect_mention_values(value, inside_mention_key=False):
    mentions = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_is_mention = inside_mention_key or ("mention" in str(key).lower())
            if key_is_mention:
                rec = _mention_dict_to_record(nested)
                if not rec and not isinstance(nested, (dict, list, tuple, set)):
                    rec = _mention_string_to_record(nested)
                if rec:
                    mentions.append(rec)
            mentions.extend(_collect_mention_values(nested, key_is_mention))
    elif isinstance(value, (list, tuple, set)):
        for nested in value:
            if inside_mention_key:
                rec = _mention_dict_to_record(nested) or _mention_string_to_record(nested)
                if rec:
                    mentions.append(rec)
            mentions.extend(_collect_mention_values(nested, inside_mention_key))
    elif inside_mention_key:
        rec = _mention_string_to_record(value)
        if rec:
            mentions.append(rec)
    return mentions


def extract_message_mentions(record):
    """Return normalized mention records found in Store 8/runtime metadata."""
    if not isinstance(record, dict):
        return []

    mentions = _collect_mention_values(record)
    if record.get("mention_all") or record.get("mentionedEveryone") or record.get("isMentionAll"):
        mentions.append({"kind": "all", "target_jid": None, "display_text": "@all"})

    out = []
    seen = set()
    for mention in mentions:
        kind = mention.get("kind") or "unknown"
        target_jid = safe_str(mention.get("target_jid"))
        display = safe_str(mention.get("display_text"))
        if kind == "all":
            key = ("all", display or "@all")
            normalized = {"kind": "all", "target_jid": None, "display_text": display or "@all"}
        elif target_jid:
            key = ("participant", target_jid)
            normalized = {"kind": "participant", "target_jid": target_jid, "display_text": display}
        else:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(normalized)
    return out


def load_runtime_store8_supplement(path):
    """Load JSONL produced by tools/wa_live_runtime_capture.js."""
    summary = {
        "schema": "waren6.runtime-store8-supplement.v1",
        "enabled": False,
        "path": pathlib.Path(path).name if path else None,
        "records": 0,
        "records_with_text": 0,
        "usable_records": 0,
        "duplicate_keys": 0,
        "parse_errors": 0,
        "missing_file": False,
        "warnings": [],
    }
    records_by_msg_key = {}
    if not path:
        return {"summary": summary, "records_by_msg_key": records_by_msg_key}

    path = pathlib.Path(path)
    summary["enabled"] = True
    if not path.exists():
        warning = {"message": "Runtime Store 8 supplement file not found", "path": path.name}
        summary["missing_file"] = True
        summary["warnings"].append(warning)
        record_warning(**warning)
        return {"summary": summary, "records_by_msg_key": records_by_msg_key}

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            summary["records"] += 1
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                summary["parse_errors"] += 1
                if summary["parse_errors"] <= 20:
                    summary["warnings"].append({
                        "message": "Failed to parse runtime supplement JSONL line",
                        "line": line_no,
                        "error": str(exc),
                    })
                continue

            msg_key = safe_str(record.get("msg_key") or record.get("id"))
            text = runtime_supplement_text(record)
            if text:
                summary["records_with_text"] += 1
            if not msg_key:
                continue

            if msg_key in records_by_msg_key:
                summary["duplicate_keys"] += 1
                previous_text = runtime_supplement_text(records_by_msg_key[msg_key])
                if previous_text != text and (previous_text or text):
                    record_warning(
                        "Runtime Store 8 supplement contains conflicting text for the same message key; first value kept.",
                        msg_key=msg_key,
                        previous_text_sha256=sha256_bytes((previous_text or "").encode("utf-8", "replace")),
                        new_text_sha256=sha256_bytes((text or "").encode("utf-8", "replace")),
                    )
                continue

            records_by_msg_key[msg_key] = record
            summary["usable_records"] += 1

    if summary["parse_errors"]:
        record_warning(
            "Runtime Store 8 supplement contained invalid JSONL rows.",
            path=str(path),
            parse_errors=summary["parse_errors"],
        )
    return {"summary": summary, "records_by_msg_key": records_by_msg_key}


def _webview_default_candidates(idb_path, leveldb_path):
    candidates = []
    if idb_path:
        candidates.extend([
            idb_path,
            idb_path.parent,
            idb_path.parent.parent,
        ])
    if leveldb_path:
        candidates.extend([
            leveldb_path.parent,
            leveldb_path.parent.parent,
        ])
    seen = set()
    for candidate in candidates:
        try:
            resolved = pathlib.Path(candidate).resolve()
        except Exception:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        yield resolved


def inspect_webview_crypto_artifacts(idb_path, leveldb_path, idb):
    """Record whether offline artifacts needed for opaque Store 8 rows exist."""
    context, inventory = collect_store8_crypto_artifacts(idb_path, leveldb_path, idb)
    return inventory.get("status", {})


def collect_store8_crypto_artifacts(idb_path, leveldb_path=None, idb=None, opaque_salt_file=None):
    """Collect Store 8 crypto material from copied WebView2 artifacts.

    The returned context contains raw bytes in memory only. The inventory is
    safe to write to JSON because it includes lengths and hashes, not values.
    """
    require_ccl_reader()
    idb_path = pathlib.Path(idb_path) if idb_path else None
    leveldb_path = pathlib.Path(leveldb_path) if leveldb_path else None
    inventory = {
        "schema": "waren6.opaque-crypto-artifacts.v1",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_roots": {
            "idb_path": str(idb_path) if idb_path else None,
            "leveldb_path": str(leveldb_path) if leveldb_path else None,
        },
        "artifacts": [],
        "warnings": [],
        "indexeddb_databases": [],
        "status": {
            "local_storage_leveldb_present": False,
            "web_enc_key_salt_present": False,
            "wawc_db_enc_key_count": 0,
            "webwa_message_crypto": "HKDF-derived AES-128-CBC",
            "webwa_network_salt_captured": False,
            "opaque_decryption_blocker": "missing_local_crypto_artifacts",
        },
    }
    context = Store8CryptoContext(artifact_inventory=inventory)

    def add_material(name, source, value, role, kind="local"):
        candidate, entry = _candidate(name, source, value, role, kind=kind)
        if not candidate:
            return
        if role in ("local_ikm", "wawc_key_data", "store22_key_data"):
            context.ikm_candidates.append(candidate)
        elif role == "network_salt":
            context.salt_candidates.append(candidate)
            inventory["status"]["webwa_network_salt_captured"] = True
        elif role == "hkdf_info":
            context.info_candidates.append(candidate)
        inventory["artifacts"].append(entry)

    for default_root in _webview_default_candidates(idb_path, leveldb_path):
        local_storage = default_root / "Local Storage" / "leveldb"
        if not local_storage.exists():
            continue
        inventory["status"]["local_storage_leveldb_present"] = True
        try:
            local_db = ccl_chromium_localstorage.LocalStoreDb(local_storage)
            interesting_info_keys = {
                "WANoiseInfo",
                "WANoiseInfoIv",
                "edgeRouting",
                "last-wid-md",
            }
            for rec in local_db.iter_all_records():
                if rec.storage_key != "https://web.whatsapp.com" or not rec.is_live:
                    continue
                key = str(rec.script_key)
                if key in ("WAWebEncKeySalt", "WebEncKeySalt") and rec.value:
                    inventory["status"]["web_enc_key_salt_present"] = True
                    add_material(key, str(local_storage), rec.value, "local_ikm")
                elif key in interesting_info_keys and rec.value:
                    add_material(key, str(local_storage), rec.value, "hkdf_info")
        except Exception as exc:
            warning = {"message": "Failed to inspect WebView2 Local Storage", "path": str(local_storage), "error": str(exc)}
            inventory["warnings"].append(warning)
            record_warning(**warning)
        break

    if idb is not None:
        try:
            for dbinfo in idb.global_metadata.db_ids:
                inventory["indexeddb_databases"].append({
                    "name": getattr(dbinfo, "name", None),
                    "dbid_no": getattr(dbinfo, "dbid_no", None),
                })
        except Exception as exc:
            inventory["warnings"].append({"message": "Failed to enumerate IndexedDB database IDs", "error": str(exc)})

        try:
            wawc_db_id = next((db.dbid_no for db in idb.global_metadata.db_ids if db.name == 'wawc_db_enc'), None)
            if wawc_db_id is not None:
                for rec in idb.iterate_records(wawc_db_id, 1):
                    val = rec.value
                    key = val.get('key') if isinstance(val, dict) else None
                    key_data = getattr(key, 'key_data', None)
                    if key_data:
                        inventory["status"]["wawc_db_enc_key_count"] += 1
                        add_material(
                            f"wawc_db_enc_store1_key_{inventory['status']['wawc_db_enc_key_count']}",
                            f"IndexedDB:wawc_db_enc/store/1",
                            key_data,
                            "wawc_key_data",
                        )
        except Exception as exc:
            warning = {"message": "Failed to inspect wawc_db_enc keys", "error": str(exc)}
            inventory["warnings"].append(warning)
            record_warning(**warning)

        try:
            model_db_id = next((db.dbid_no for db in idb.global_metadata.db_ids if db.name == 'model-storage'), None)
            if model_db_id is not None:
                for rec in idb.iterate_records(model_db_id, 22):
                    val = rec.value
                    if not isinstance(val, dict):
                        continue
                    for key_name in ("keyData", "key_data", "key", "data"):
                        if key_name in val:
                            add_material(
                                f"model_storage_store22_{key_name}",
                                "IndexedDB:model-storage/store/22",
                                val.get(key_name),
                                "store22_key_data",
                            )
                    add_material(
                        "model_storage_store22_record",
                        "IndexedDB:model-storage/store/22",
                        json.dumps(val, default=str, sort_keys=True),
                        "hkdf_info",
                    )
        except Exception as exc:
            warning = {"message": "Failed to inspect model-storage Store 22", "error": str(exc)}
            inventory["warnings"].append(warning)
            record_warning(**warning)

    if opaque_salt_file:
        try:
            salt_candidates, salt_inventory = load_opaque_salt_file(opaque_salt_file)
            context.salt_candidates.extend(salt_candidates)
            inventory["artifacts"].extend(salt_inventory.get("artifacts", []))
            if salt_candidates:
                inventory["status"]["webwa_network_salt_captured"] = True
        except Exception as exc:
            warning = {"message": "Failed to load opaque salt file", "path": str(opaque_salt_file), "error": str(exc)}
            inventory["warnings"].append(warning)
            record_warning(**warning)

    if context.salt_candidates:
        inventory["status"]["opaque_decryption_blocker"] = None
    elif context.ikm_candidates:
        inventory["status"]["opaque_decryption_blocker"] = "network_salt_missing"

    inventory["summary"] = {
        "artifacts": len(inventory["artifacts"]),
        "ikm_candidates": len(context.ikm_candidates),
        "salt_candidates": len(context.salt_candidates),
        "info_candidates": len(context.info_candidates),
        "warnings": len(inventory["warnings"]),
    }
    return context, inventory


# ─────────────────────────────────────────────────────────────────────────────
# IndexedDB extraction
# ─────────────────────────────────────────────────────────────────────────────

def extract_indexeddb(
    idb_path: pathlib.Path,
    opaque_salt_file=None,
    decrypt_store8_opaque=False,
    hunt_opaque_salt=False,
    opaque_artifact_paths=None,
    fast_salt_hunt=False,
):
    """Read WhatsApp IndexedDB and return extracted data dicts."""
    require_ccl_reader()
    # PS1 may pass the path ending at the IndexedDB folder OR at EBWebView_Default.
    # Try several candidate paths so both invocation styles work.
    candidates = [
        idb_path / "https_web.whatsapp.com_0.indexeddb.leveldb",          # path already IS IndexedDB/
        idb_path / "IndexedDB" / "https_web.whatsapp.com_0.indexeddb.leveldb",  # path is EBWebView_Default\
        idb_path / "Default" / "IndexedDB" / "https_web.whatsapp.com_0.indexeddb.leveldb",
    ]
    leveldb_path = next((c for c in candidates if c.exists()), None)

    if leveldb_path is None:
        tried = "\n    ".join(str(c) for c in candidates)
        print(f"WARNING: LevelDB not found. Tried:\n    {tried}")
        record_warning("IndexedDB LevelDB not found", tried=tried)
        return {}

    log_detail(f"  Opening IndexedDB: {leveldb_path}")
    blob_dir = leveldb_path.parent / "https_web.whatsapp.com_0.indexeddb.blob"
    if blob_dir.exists():
        log_detail(f"  IndexedDB blob dir: {blob_dir}")
        idb = ccl_chromium_indexeddb.IndexedDb(leveldb_path, blob_dir)
    else:
        print("  WARNING: IndexedDB blob dir not found; blob-backed records may be incomplete")
        record_warning("IndexedDB blob dir not found; blob-backed records may be incomplete", leveldb=str(leveldb_path))
        idb = ccl_chromium_indexeddb.IndexedDb(leveldb_path)

    # Find model-storage db_id
    model_db_id = None
    for dbinfo in idb.global_metadata.db_ids:
        if dbinfo.name == 'model-storage':
            model_db_id = dbinfo.dbid_no
            break

    if model_db_id is None:
        print("  WARNING: model-storage database not found in IndexedDB")
        record_warning("model-storage database not found in IndexedDB", leveldb=str(leveldb_path))
        idb.close()
        return {}

    log_detail(f"  model-storage db_id = {model_db_id}")
    data = {}
    crypto_context, crypto_inventory = collect_store8_crypto_artifacts(
        idb_path,
        leveldb_path,
        idb,
        opaque_salt_file=opaque_salt_file,
    )
    data["_store8_crypto_context"] = crypto_context
    data["_opaque_crypto_artifacts"] = crypto_inventory
    data["_webview_crypto_artifacts"] = crypto_inventory.get("status", {})

    # Store mappings: store_id -> store_name (discovered from probing)
    store_map = {
        4: 'contact',
        5: 'blocklist',
        7: 'chat',
        8: 'message',          # PRIMARY message store — has fromMe in id prefix
        9: 'message-info',
        10: 'participant',
        21: 'group-metadata',
        31: 'orphan-revoke',
        34: 'reactions',
        53: 'pinned-messages',
        55: 'newsletter-metadata',
        74: 'reporting-info',
    }

    store_counts = {}
    iterator_notes = []
    for store_id, store_name in store_map.items():
        records = []
        try:
            for rec in idb.iterate_records(model_db_id, store_id):
                try:
                    val = rec.value
                    if isinstance(val, dict):
                        records.append(val)
                except Exception:
                    record_skipped_record(store_name, "malformed_record", error=traceback.format_exc(limit=1).strip())
        except Exception as e:
            # Iterator itself crashed — keep whatever we got so far
            if records:
                iterator_notes.append(f"{store_name} iterator stopped after {len(records)} records: {e}")
                log_detail(f"  {store_name}: {len(records)} records (iterator stopped: {e})")
            else:
                iterator_notes.append(f"{store_name} iterator failed: {e}")
                log_detail(f"  {store_name}: ERROR - {e}")
            record_skipped_record(store_name, "iterator_error", error=str(e), recovered_records=len(records))
        data[store_name] = records
        if records:
            store_counts[store_name] = len(records)
            log_detail(f"  {store_name}: {len(records)} records")

    if store_counts:
        ordered_summary = ", ".join(f"{name}={count}" for name, count in store_counts.items())
        print(f"  IndexedDB stores: {ordered_summary}")
    for note in iterator_notes:
        print(f"  WARNING: {note}")

    salt_hunt_report = {
        "schema": "waren6.store8-salt-hunt.v1",
        "enabled": False,
        "summary": {"validated_candidates": 0},
    }
    if hunt_opaque_salt:
        salt_hunt_paths = list(opaque_artifact_paths or [])
        if not salt_hunt_paths:
            salt_hunt_paths = [idb_path]
        salt_hunt_report = hunt_store8_network_salts(
            salt_hunt_paths,
            data.get('message', []),
            crypto_context,
            fast_mode=bool(fast_salt_hunt),
        )
        salt_hunt_report["enabled"] = True
        if salt_hunt_report.get("summary", {}).get("validated_candidates"):
            crypto_inventory["status"]["webwa_network_salt_captured"] = True
            crypto_inventory["status"]["opaque_decryption_blocker"] = None
        crypto_inventory["summary"] = {
            "artifacts": len(crypto_inventory.get("artifacts", [])),
            "ikm_candidates": len(crypto_context.ikm_candidates),
            "salt_candidates": len(crypto_context.salt_candidates),
            "info_candidates": len(crypto_context.info_candidates),
            "warnings": len(crypto_inventory.get("warnings", [])),
        }
    data["_store8_salt_hunt_report"] = salt_hunt_report

    decryption_report = decrypt_store8_opaque_messages(
        data.get('message', []),
        crypto_context,
        enabled=decrypt_store8_opaque,
    )
    crypto_profile = profile_store8_crypto_data(
        data.get('message', []),
        artifacts_report=crypto_inventory,
        decryption_report=decryption_report,
    )
    opaque_rows = crypto_profile["store8_opaque_rows"]
    data["_store8_crypto_profile"] = crypto_profile
    data["_store8_decryption_report"] = decryption_report
    data["_opaque_status"] = {
        **crypto_profile,
        **data.get("_webview_crypto_artifacts", {}),
        "decryption": decryption_report.get("summary", {}),
    }
    if opaque_rows:
        print(f"  Store 8 opaque rows: {opaque_rows}")
        record_warning(
            "IndexedDB Store 8 contains encrypted msgRowOpaqueData rows. Rows are preserved, but offline body recovery needs genericStorage text or the WebWA network salt used with the local HKDF material.",
            count=opaque_rows,
            **data["_opaque_status"],
        )

    idb.close()
    return data


# ─────────────────────────────────────────────────────────────────────────────
# SQLite (decrypted) extraction
# ─────────────────────────────────────────────────────────────────────────────

def _quote_sql_identifier(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _apply_wal_and_open(db_path: pathlib.Path, sanity_table: str | None = None):
    """
    Open a SQLite DB that may be in WAL-only mode.

    New WhatsApp versions (v2.3000+) keep all data exclusively in the WAL
    and never checkpoint to the main DB file.

    PRIMARY strategy: copy both .dec.db and .dec.db-wal to a temp directory
    and let SQLite's native WAL mechanism handle the merge.  This is exactly
    what DB Browser does and produces zero B-tree corruption.

    FALLBACK strategy: if native WAL fails (e.g. SQLite auto-deletes the WAL
    due to checksum issues on some builds), manually apply WAL frames with
    header restoration and progressive row-level recovery.

    Returns (conn, tmp_dir_or_None) -- caller must close conn and delete tmp.
    """
    wal_hs   = 32   # WAL file header size
    frame_hs = 24   # WAL frame header size

    # Check for a companion WAL file FIRST
    wal_path = pathlib.Path(str(db_path) + "-wal")
    if not wal_path.is_file() or wal_path.stat().st_size <= wal_hs:
        # No usable WAL -- genuinely empty DB or already checkpointed
        return sqlite3.connect(str(db_path)), None

    # ---- PRIMARY: Native SQLite WAL handling ---------------------------------
    # Copy both files to a temp directory so we never mutate evidence.
    # SQLite will read the main DB header, discover WAL mode, and apply
    # the WAL frames using its own (much more robust) WAL reader.
    try:
        tmp_dir = tempfile.mkdtemp(prefix='waren6_nwal_')
        tmp_db  = pathlib.Path(tmp_dir) / db_path.name
        tmp_wal = pathlib.Path(tmp_dir) / wal_path.name

        shutil.copy2(db_path, tmp_db)
        shutil.copy2(wal_path, tmp_wal)

        # Also copy -shm if present (helps SQLite skip rebuilding it)
        shm_path = pathlib.Path(str(db_path) + "-shm")
        if shm_path.is_file():
            shutil.copy2(shm_path, pathlib.Path(tmp_dir) / shm_path.name)

        conn = sqlite3.connect(str(tmp_db))

        if sanity_table:
            try:
                quoted_table = _quote_sql_identifier(sanity_table)
                test_count = conn.execute(f"SELECT COUNT(*) FROM {quoted_table}").fetchone()[0]
                print(f"    Native WAL: table '{sanity_table}' readable ({test_count} rows)")
                return conn, tmp_dir
            except sqlite3.DatabaseError as e:
                print(f"    Native WAL path unavailable for table '{sanity_table}' ({e}); using manual WAL apply")
                conn.close()
                shutil.rmtree(tmp_dir, ignore_errors=True)
        else:
            conn.execute("PRAGMA schema_version").fetchone()
            print("    Native WAL: database opened with companion WAL")
            return conn, tmp_dir
    except Exception as e:
        print(f"    Native WAL setup unavailable ({e}); using manual WAL apply")

    # ---- FALLBACK: Manual WAL frame application ------------------------------
    # Parse WAL frames ourselves and write them into the DB page slots.
    # This is needed when SQLite's WAL reader rejects the file (e.g. checksum
    # mismatch on certain Python/SQLite build combinations).
    db_data  = bytearray(db_path.read_bytes())
    wal_data = wal_path.read_bytes()

    # Detect page size from the WAL file header
    wal_magic = struct.unpack('>I', wal_data[0:4])[0]
    if wal_magic not in (0x377F0682, 0x377F0683):
        print(f"    WARNING: Unexpected WAL magic 0x{wal_magic:08X} -- skipping manual apply")
        return sqlite3.connect(str(db_path)), None

    ps = struct.unpack('>I', wal_data[8:12])[0]
    if ps < 512 or ps > 65536 or (ps & (ps - 1)) != 0:
        print(f"    WARNING: WAL reports implausible page size {ps} -- falling back to 4096")
        ps = 4096
    else:
        print(f"    WAL page size: {ps} bytes")

    frame_size   = frame_hs + ps
    total_frames = max(0, (len(wal_data) - wal_hs) // frame_size)
    if total_frames == 0:
        return sqlite3.connect(str(db_path)), None

    # Collect pages (last write wins -- standard WAL semantics)
    page_map: dict = {}
    for i in range(total_frames):
        off = wal_hs + i * frame_size
        if off + frame_hs + ps > len(wal_data):
            break
        page_num = struct.unpack('>I', wal_data[off:off + 4])[0]
        if page_num == 0:
            continue
        page_map[page_num] = wal_data[off + frame_hs : off + frame_hs + ps]

    if not page_map:
        return sqlite3.connect(str(db_path)), None

    # Extend DB buffer if WAL references pages beyond current size
    max_page = max(page_map)
    required = max_page * ps
    if len(db_data) < required:
        db_data.extend(b'\x00' * (required - len(db_data)))
    if len(db_data) < ps:
        db_data.extend(b'\x00' * (ps - len(db_data)))

    # Save the stub DB's valid SQLite file header before WAL overlay
    SQLITE_HDR_LEN = 100
    SQLITE_MAGIC   = b'SQLite format 3\x00'
    stub_hdr_valid = (
        len(db_data) >= SQLITE_HDR_LEN and
        bytes(db_data[:16]) == SQLITE_MAGIC
    )
    saved_hdr = bytes(db_data[:SQLITE_HDR_LEN]) if stub_hdr_valid else None

    # Write each WAL page to its correct offset
    for page_num, page_bytes in page_map.items():
        start = (page_num - 1) * ps
        db_data[start : start + ps] = page_bytes

    # Restore the correct SQLite file header (bytes 0-99 of page 1)
    if saved_hdr and 1 in page_map:
        db_data[:SQLITE_HDR_LEN] = saved_hdr
    elif not stub_hdr_valid:
        if bytes(db_data[:16]) == SQLITE_MAGIC:
            hdr_ps_raw = ps if ps < 65536 else 1
            db_data[16] = (hdr_ps_raw >> 8) & 0xFF
            db_data[17] =  hdr_ps_raw       & 0xFF
            print(f"    Patched page-size field in SQLite header: {ps}")
        else:
            print("    WARNING: Merged DB missing SQLite magic -- header may be corrupt")

    # Write merged result to a temp file (never mutate evidence)
    tmp_dir = tempfile.mkdtemp(prefix='waren6_wal_')
    tmp_db  = pathlib.Path(tmp_dir) / db_path.name
    tmp_db.write_bytes(db_data)

    print(f"    WAL applied (manual): {total_frames} frames, {len(page_map)} unique pages, "
          f"output={len(db_data):,} bytes")

    return sqlite3.connect(str(tmp_db)), tmp_dir

# Keep old name as an alias for any external callers
_open_db_with_wal = _apply_wal_and_open



def load_decrypted_messages(decrypted_dir: pathlib.Path):
    """Load messages from genericStorage.dec.db (WAL-based message store)."""
    candidates = list(decrypted_dir.rglob("genericStorage.dec.db"))
    candidates = [c for c in candidates if c.stat().st_size > 0]

    if not candidates:
        print("  WARNING: No genericStorage.dec.db found")
        return []

    db_path = candidates[0]
    wal_path = pathlib.Path(str(db_path) + "-wal")
    print(f"  Reading messages from: {db_path}")
    if wal_path.exists():
        print(f"  WAL file: {wal_path.stat().st_size:,} bytes")
    else:
        print(f"  WARNING: No .dec.db-wal found next to genericStorage.dec.db")

    conn, tmp_dir = _apply_wal_and_open(db_path, sanity_table="message")
    cursor = conn.cursor()

    try:
        # Tier 1: Full table scan (fast path, works when DB is intact)
        try:
            cursor.execute("SELECT id, chatId, timestamp, text FROM message")
            rows = cursor.fetchall()
            print(f"  Messages from SQLite (full scan): {len(rows)}")
            return [{'id': r[0], 'chatId': r[1], 'timestamp': r[2], 'text': r[3]}
                    for r in rows]
        except sqlite3.DatabaseError as e:
            print(f"  Full scan failed ({e}) -- trying chunked rowid recovery...")

        # Tier 2: Chunked rowid scan with progressive refinement
        # When WAL pages are missing, B-tree interior nodes are corrupt.
        # Large range queries hit those nodes and fail, even though individual
        # rows in the range are accessible via different B-tree paths.
        # Strategy: try chunks of 500, retry failed chunks at 50, then
        # retry failed sub-chunks at 1 (row-by-row).  This maximizes
        # recovery (~99.7%) while staying fast for the healthy regions.
        try:
            max_rowid = cursor.execute("SELECT MAX(rowid) FROM message").fetchone()[0]
            if max_rowid:
                results = []
                failed_ranges = []
                # Pass 1: large chunks
                for start in range(1, max_rowid + 1, 500):
                    try:
                        chunk_rows = cursor.execute(
                            "SELECT id, chatId, timestamp, text FROM message "
                            "WHERE rowid BETWEEN ? AND ?",
                            (start, start + 499)
                        ).fetchall()
                        results.extend(chunk_rows)
                    except sqlite3.DatabaseError:
                        failed_ranges.append((start, min(start + 499, max_rowid)))
                # Pass 2: retry failed ranges with smaller chunks
                still_failed = []
                for (rng_start, rng_end) in failed_ranges:
                    for start in range(rng_start, rng_end + 1, 50):
                        try:
                            chunk_rows = cursor.execute(
                                "SELECT id, chatId, timestamp, text FROM message "
                                "WHERE rowid BETWEEN ? AND ?",
                                (start, min(start + 49, rng_end))
                            ).fetchall()
                            results.extend(chunk_rows)
                        except sqlite3.DatabaseError:
                            still_failed.append((start, min(start + 49, rng_end)))
                # Pass 3: row-by-row for stubborn ranges
                unrecoverable = 0
                for (rng_start, rng_end) in still_failed:
                    for rid in range(rng_start, rng_end + 1):
                        try:
                            row = cursor.execute(
                                "SELECT id, chatId, timestamp, text FROM message "
                                "WHERE rowid = ?", (rid,)
                            ).fetchone()
                            if row:
                                results.append(row)
                        except sqlite3.DatabaseError:
                            unrecoverable += 1
                print(f"  Messages from SQLite (progressive recovery): "
                      f"{len(results)} rows, {unrecoverable} unrecoverable")
                if results:
                    return [{'id': r[0], 'chatId': r[1], 'timestamp': r[2], 'text': r[3]}
                            for r in results]
        except Exception as _ce:
            print(f"  Progressive scan failed: {_ce}")
        # Tier 3: Table discovery (handles renamed/restructured schema)
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cursor.fetchall()]
            print(f"  Available tables in genericStorage.dec.db: {tables}")
            for tbl in tables:
                if 'message' in tbl.lower() and 'fts' not in tbl.lower():
                    try:
                        cursor.execute(f"PRAGMA table_info({tbl})")
                        cols = [r[1].lower() for r in cursor.fetchall()]
                        print(f"  Table '{tbl}' columns: {cols}")
                        id_col   = next((c for c in cols if c in ('id', 'rowid')), None)
                        chat_col = next((c for c in cols if 'chat' in c), None)
                        ts_col   = next((c for c in cols if 'time' in c or c == 'ts'), None)
                        txt_col  = next((c for c in cols if c in ('text', 'body', 'content', 'message')), None)
                        if chat_col and ts_col:
                            sel_id   = id_col  or 'rowid'
                            sel_text = txt_col or 'NULL'
                            cursor.execute(
                                f"SELECT {sel_id}, {chat_col}, {ts_col}, {sel_text} FROM {tbl}"
                            )
                            rows = cursor.fetchall()
                            print(f"  Fallback: read {len(rows)} rows from table '{tbl}'")
                            return [{'id': r[0], 'chatId': r[1], 'timestamp': r[2], 'text': r[3]}
                                    for r in rows]
                    except Exception as _te:
                        print(f"  Could not read table '{tbl}': {_te}")
        except Exception as _disc:
            print(f"  Table discovery failed: {_disc}")

        print("  No readable message tables found -- genericStorage will be skipped")
        return []

    except Exception as e:
        print(f"  Failed to read messages: {e}")
        return []
    finally:
        conn.close()
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)

def load_decrypted_contacts(decrypted_dir: pathlib.Path):
    """Load contacts from contacts.dec.db for supplementary LID resolution."""
    candidates = list(decrypted_dir.rglob("contacts.dec.db"))
    candidates = [c for c in candidates if c.stat().st_size > 0]

    if not candidates:
        return []

    db_path = candidates[0]
    print(f"  Reading contacts from: {db_path}")

    conn, tmp_dir = _apply_wal_and_open(db_path, sanity_table="UserStatuses")
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT Jid, DbLid, ContactName, PushName
            FROM UserStatuses
            WHERE (Jid IS NOT NULL AND Jid != '')
               OR (DbLid IS NOT NULL AND DbLid != '')
        """)
        return cursor.fetchall()
    except Exception as e:
        print(f"  Failed to read contacts: {e}")
        return []
    finally:
        conn.close()
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# LID resolution
# ─────────────────────────────────────────────────────────────────────────────

def build_lid_resolver(idb_contacts, sqlite_contacts):
    """Build a comprehensive LID-to-phone/name lookup table.
    Priority: IndexedDB contact store > SQLite name-matching."""

    lid_to_phone = {}   # lid -> phone_jid (e.g., 15550101234@c.us)
    lid_to_name = {}    # lid -> contact name
    phone_to_name = {}  # phone_jid -> contact name

    # 1. IndexedDB contacts - these have direct LID-to-phone mapping
    for contact in idb_contacts:
        lid = safe_str(contact.get('id'))
        phone = safe_str(contact.get('phoneNumber'))
        name = safe_str(contact.get('name')) or safe_str(contact.get('shortName'))

        if lid:
            if phone:
                lid_to_phone[lid] = phone
            if name:
                lid_to_name[lid] = name
            if phone and name:
                phone_to_name[phone] = name

    # 2. SQLite contacts - supplement with name-matching for any gaps
    name_to_jid = {}
    name_to_lid = {}
    for jid, db_lid, contact_name, push_name in sqlite_contacts:
        name = contact_name or push_name
        if jid and name and '@s.whatsapp.net' in jid:
            name_to_jid[name] = jid
        if db_lid and name:
            name_to_lid[name] = db_lid

    # Cross-reference by name for LIDs not yet resolved
    supplemental = 0
    for name, lid in name_to_lid.items():
        if lid not in lid_to_phone and name in name_to_jid:
            jid = name_to_jid[name]
            phone = jid.replace('@s.whatsapp.net', '@c.us')
            lid_to_phone[lid] = phone
            lid_to_name[lid] = name
            supplemental += 1

    print(
        "  LID mappings: "
        f"{len(lid_to_phone)} from IndexedDB contacts, {supplemental} SQLite supplemental"
    )

    return lid_to_phone, lid_to_name, phone_to_name


def resolve_jid(jid, lid_to_phone, lid_to_name):
    """Resolve a JID to (phone_number, display_name)."""
    if not jid:
        return None, None

    phone = extract_phone(jid)
    if phone:
        name = lid_to_name.get(jid) or None
        return phone, name

    if jid.endswith('@lid'):
        mapped_phone_jid = lid_to_phone.get(jid)
        if mapped_phone_jid:
            phone = extract_phone(mapped_phone_jid)
            name = lid_to_name.get(jid)
            return phone, name
        else:
            name = lid_to_name.get(jid)
            return None, name

    return None, None


# ─────────────────────────────────────────────────────────────────────────────
# Terminal UX helpers
# ─────────────────────────────────────────────────────────────────────────────

def print_progress(iteration, total, prefix='', suffix='', decimals=1, length=40, fill='#'):
    """Call in a loop to create terminal progress bar"""
    if not PROGRESS_ENABLED or not sys.stdout.isatty():
        return
    if total <= 0:
        return
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    sys.stdout.write(f'\r  {prefix} |{bar}| {percent}% {suffix}')
    sys.stdout.flush()
    if iteration == total:
        sys.stdout.write('\n')

# ─────────────────────────────────────────────────────────────────────────────
# Text cleaning helpers
# ─────────────────────────────────────────────────────────────────────────────

_SOCIAL_DOMAINS = (
    'youtube.com', 'youtu.be', 'instagram.com', 'twitter.com', 'x.com',
    'fb.com', 'facebook.com', 'tiktok.com', 'vm.tiktok.com', 'reddit.com',
    'linkedin.com', 'snapchat.com',
)
_URL_RE = re.compile(r'https?://\S+', re.IGNORECASE)
_MEDIA_TYPES = ('document', 'image', 'video', 'sticker', 'ptt', 'audio', 'ptv', 'album', 'interactive')
_EMBEDDED_MEDIA_MARKERS = ('/9j/', 'iVBORw0K', 'iVBOR')


def strip_embedded_media_preview(text):
    """Remove an embedded thumbnail/base64 payload while preserving caption text."""
    if not text:
        return text
    marker_positions = [text.find(marker) for marker in _EMBEDDED_MEDIA_MARKERS if marker in text]
    if not marker_positions:
        return text
    first_marker = min(pos for pos in marker_positions if pos >= 0)
    prefix = text[:first_marker].rstrip()
    return prefix or None


def clean_media_text(text, msg_type=None, media_filename=None):
    """Remove base64 thumbnail blobs that FTS stores as message text."""
    if not text or msg_type not in _MEDIA_TYPES:
        return text
    # Base64 JPEG/PNG headers embedded in text = thumbnail artifact
    stripped = strip_embedded_media_preview(text)
    if stripped != text:
        return stripped
    # FTS stores "filename.ext filename.ext" pattern for documents
    if media_filename and text.strip().lower().startswith(media_filename.lower()):
        return None
    return text


def clean_rich_preview(text):
    """Strip social media rich-preview metadata, keep sender text + URL only."""
    if not text:
        return text
    urls = list(_URL_RE.finditer(text))
    if not urls:
        return text
    # Find first social-media URL
    social = next(
        (m for m in urls if any(d in m.group().lower() for d in _SOCIAL_DOMAINS)),
        None
    )
    if not social:
        return text
    # Preserve everything up to the end of the line containing that URL
    line_end = text.find('\n', social.end())
    trimmed = text[:line_end if line_end != -1 else len(text)].strip()
    return trimmed if trimmed else text


def is_duplicate_filename_artifact(text):
    if not text:
        return False
    return bool(re.fullmatch(r"(.+\.[A-Za-z0-9]{2,8})\s+\1", str(text).strip()))


def normalize_source_text_for_validation(text):
    if not text or not str(text).strip():
        return None
    normalized = strip_embedded_media_preview(str(text)) or str(text)
    if is_duplicate_filename_artifact(normalized):
        return None
    normalized = clean_rich_preview(normalized)
    return normalized if normalized and normalized.strip() else None



def build_unified_db(output_path, idb_data, sqlite_messages, lid_to_phone,
                     lid_to_name, phone_to_name, idb_path_str, decrypted_dir_str,
                     runtime_store8_supplement=None):
    """Build the unified SQLite database."""

    if os.path.exists(output_path):
        backup = output_path + '.bak'
        print(f"  Backing up existing DB to {backup}")
        if os.path.exists(backup):
            os.remove(backup)
        os.rename(output_path, backup)

    conn = sqlite3.connect(output_path)
    configure_unified_output_connection(conn)
    cursor = conn.cursor()
    runtime_store8_supplement = runtime_store8_supplement or {}
    runtime_store8_records = runtime_store8_supplement.get("records_by_msg_key", {})
    runtime_store8_summary = runtime_store8_supplement.get("summary", {})
    mention_batch = []
    edit_markers = {}
    edit_events = {}
    _resolve_cache = {}

    def cached_resolve_jid(jid):
        if not jid:
            return None, None
        if jid not in _resolve_cache:
            _resolve_cache[jid] = resolve_jid(jid, lid_to_phone, lid_to_name)
        return _resolve_cache[jid]

    # Create tables/views first; indexes are deferred until after bulk inserts.
    cursor.executescript(UNIFIED_TABLE_SCHEMA)

    message_insert_columns = (
        "msg_key", "msg_id", "chat_jid", "chat_name", "chat_phone",
        "sender_jid", "sender_phone", "sender_name",
        "from_me", "timestamp", "text", "is_group",
        "msg_type",
        "quoted_stanza_id", "quoted_participant", "quoted_msg_body", "quoted_msg_type",
        "call_duration", "call_outcome", "is_video_call",
        "media_mime_type", "media_filename", "media_size",
        "source", "source_id", "source_chat_id", "source_recovery",
        "store8_decrypted_text", "store8_decryption_status", "text_conflict_status",
        "body_status", "media_case_path", "media_sha256", "media_status",
        "is_edited", "edited_at", "edit_count", "edit_history_status",
    )
    message_insert_sql = (
        f"INSERT OR IGNORE INTO messages ({', '.join(message_insert_columns)}) "
        f"VALUES ({', '.join('?' for _ in message_insert_columns)})"
    )

    def queue_mentions(msg_key, chat_jid, record, source):
        if not msg_key:
            return
        for idx, mention in enumerate(extract_message_mentions(record)):
            kind = mention.get("kind") or "unknown"
            target_jid = safe_str(mention.get("target_jid"))
            display_text = safe_str(mention.get("display_text"))
            if kind == "all":
                mention_batch.append((
                    msg_key, chat_jid, idx, "all", None, None, None,
                    display_text or "@all", source, "high",
                ))
                continue
            target_phone, target_name = cached_resolve_jid(target_jid)
            mention_batch.append((
                msg_key, chat_jid, idx, kind, target_jid or None,
                target_phone, target_name, display_text, source,
                "high" if target_jid else "low",
            ))

    def queue_edit_evidence(msg_key, chat_jid, stanza_id, sender_jid, record, source, text):
        marker = extract_edit_marker(record, msg_key)
        if marker:
            current = edit_markers.get(msg_key)
            if not current or (marker.get("edited_at") or 0) > (current.get("edited_at") or 0):
                edit_markers[msg_key] = {
                    **marker,
                    "target_chat_jid": chat_jid,
                    "target_msg_id": stanza_id,
                    "source": source,
                }

        event = extract_message_edit_event(record, event_msg_key=msg_key, source=source, new_text=text)
        if not event:
            return
        _, _, _, event_sender = parse_msg_key(msg_key)
        editor_jid = sender_jid or event_sender
        editor_phone, editor_name = cached_resolve_jid(editor_jid) if editor_jid else (None, None)
        key = (
            event.get("target_msg_key"),
            event.get("edit_event_msg_key") or event.get("provenance_sha256"),
        )
        if key not in edit_events:
            edit_events[key] = {
                **event,
                "editor_jid": editor_jid,
                "editor_phone": editor_phone,
                "editor_name": editor_name,
            }

    # ── Metadata ──────────────────────────────────────────────────────────
    now = datetime.datetime.now().isoformat()
    metadata = {
        'tool': 'waren6.py (WAren6)',
        'extraction_time': now,
        'platform': platform.platform(),
        'python_version': platform.python_version(),
        'indexeddb_source': pathlib.Path(idb_path_str).name if idb_path_str else '',
        'decrypted_db_source': '<case-root>' if decrypted_dir_str else '',
        'total_indexeddb_contacts': str(len(idb_data.get('contact', []))),
        'total_sqlite_messages': str(len(sqlite_messages)),
        'total_resolved_lids': str(len(lid_to_phone)),
        'schema_version': '1.0',
        'runtime_store8_supplement_enabled': str(bool(runtime_store8_summary.get("enabled"))),
        'runtime_store8_supplement_path': safe_str(runtime_store8_summary.get("path")),
        'runtime_store8_supplement_records': str(runtime_store8_summary.get("records", 0)),
        'runtime_store8_supplement_records_with_text': str(runtime_store8_summary.get("records_with_text", 0)),
        'runtime_store8_supplement_usable_records': str(runtime_store8_summary.get("usable_records", 0)),
        'runtime_store8_supplement_parse_errors': str(runtime_store8_summary.get("parse_errors", 0)),
    }
    cursor.executemany(
        "INSERT OR REPLACE INTO extraction_metadata (key, value) VALUES (?, ?)",
        metadata.items()
    )

    # ── Contacts ──────────────────────────────────────────────────────────
    self_jid = None
    for contact in idb_data.get('contact', []):
        lid = safe_str(contact.get('id'))
        phone_jid = safe_str(contact.get('phoneNumber'))
        phone = extract_phone(phone_jid) if phone_jid else None
        name = safe_str(contact.get('name'))
        short = safe_str(contact.get('shortName'))
        push = safe_str(contact.get('pushName'))

        cursor.execute("""
            INSERT OR REPLACE INTO contacts
            (lid, phone_jid, phone_number, contact_name, short_name, push_name, confidence)
            VALUES (?, ?, ?, ?, ?, ?, 'high')
        """, (lid, phone_jid, phone, name, short, push))

    # Try to identify self — look for the Jid used in msgKeys with true_ prefix
    # Also check message-info for senderUserJid pattern
    msg_infos = idb_data.get('message-info', [])
    if msg_infos:
        sample = msg_infos[0]
        mk = sample.get('msgKey', '')
        from_me, chat_jid, stanza, sender = parse_msg_key(mk)
        if sender:
            self_jid = sender
            log_detail("  Self identified from message-info: [redacted]")

    # Also look at reactions where senderUserJid contains @c.us (phone format)
    for reaction in idb_data.get('reactions', []):
        sender = safe_str(reaction.get('senderUserJid'))
        mk = safe_str(reaction.get('msgKey'))
        if sender and mk and mk.startswith('true_'):
            if '@c.us' in sender:
                self_jid = sender
                break

    if self_jid:
        self_phone = extract_phone(self_jid)
        if self_phone:
            cursor.execute("""
                UPDATE contacts SET is_self = 1
                WHERE phone_number = ?
            """, (self_phone,))
            # Also add self to metadata
            cursor.execute("""
                INSERT OR REPLACE INTO extraction_metadata (key, value)
                VALUES ('self_phone', ?), ('self_jid', ?)
            """, (self_phone, self_jid))
            print("  Self phone: [redacted]")

    conn.commit()

    # ── Chats ─────────────────────────────────────────────────────────────
    for chat in idb_data.get('chat', []):
        chat_jid = safe_str(chat.get('id'))
        if not chat_jid:
            continue

        is_group = 1 if '@g.us' in chat_jid else 0
        is_nl = 1 if '@newsletter' in chat_jid else 0
        name = safe_str(chat.get('name'))

        # Resolve chat phone + name for 1:1 chats
        chat_phone_val = None
        if not is_group and not is_nl:
            chat_phone_val, resolved_name = cached_resolve_jid(chat_jid)
            if not name and resolved_name:
                name = resolved_name

        cursor.execute("""
            INSERT OR REPLACE INTO chats
            (chat_jid, chat_name, chat_phone, is_group, is_newsletter, unread_count,
             last_activity, mute_expiration, is_read_only)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            chat_jid, name, chat_phone_val, is_group, is_nl,
            safe_int(chat.get('unreadCount')),
            safe_int(chat.get('t')),
            safe_int(chat.get('muteExpiration')),
            1 if chat.get('isReadOnly') else 0,
        ))

    conn.commit()

    # ── Groups ────────────────────────────────────────────────────────────
    for grp in idb_data.get('group-metadata', []):
        gid = safe_str(grp.get('id'))
        if not gid:
            continue

        owner_lid = safe_str(grp.get('owner'))
        owner_phone, _ = cached_resolve_jid(owner_lid)

        cursor.execute("""
            INSERT OR REPLACE INTO groups
            (group_jid, subject, description, owner_lid, owner_phone, creation_time)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            gid,
            safe_str(grp.get('subject')),
            safe_str(grp.get('desc')),
            owner_lid, owner_phone,
            safe_int(grp.get('creation')),
        ))

        # Also ensure this group is in the chats table
        group_subject = safe_str(grp.get('subject'))
        cursor.execute("""
            INSERT OR IGNORE INTO chats (chat_jid, chat_name, is_group, is_newsletter)
            VALUES (?, ?, 1, 0)
        """, (gid, group_subject))
        if group_subject:
            cursor.execute("""
                UPDATE chats
                SET chat_name = ?,
                    is_group = 1,
                    is_newsletter = 0
                WHERE chat_jid = ?
            """, (group_subject, gid))
        else:
            cursor.execute("""
                UPDATE chats
                SET is_group = 1, is_newsletter = 0
                WHERE chat_jid = ?
            """, (gid,))

    conn.commit()

    # ── Group Participants ────────────────────────────────────────────────
    for part_rec in idb_data.get('participant', []):
        gid = safe_str(part_rec.get('groupId'))
        if not gid:
            continue

        participants = part_rec.get('participants', [])
        admins = set(str(a) for a in (part_rec.get('admins') or []))
        supers = set(str(s) for s in (part_rec.get('superAdmins') or []))

        for p in participants:
            p_str = str(p)
            p_phone, p_name = cached_resolve_jid(p_str)

            cursor.execute("""
                INSERT OR IGNORE INTO group_participants
                (group_jid, participant_lid, participant_phone, participant_name,
                 is_admin, is_super_admin)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                gid, p_str, p_phone, p_name,
                1 if p_str in admins else 0,
                1 if p_str in supers else 0,
            ))

        # Update participant count
        if participants:
            cursor.execute("""
                UPDATE groups SET participant_count = ? WHERE group_jid = ?
            """, (len(participants), gid))

    conn.commit()

    # ── Messages ──────────────────────────────────────────────────────────
    # PRIMARY APPROACH: Use IndexedDB Store 8 (message store) which has
    # fromMe directly encoded in the id field as true_/false_ prefix.
    # Then join text from genericStorage FTS by (chat_jid, timestamp).

    # Build chat name lookup
    chat_names = {}
    cursor.execute("SELECT chat_jid, chat_name FROM chats")
    for row in cursor.fetchall():
        chat_names[row[0]] = row[1]

    # Build genericStorage lookup: (chat_jid, timestamp) -> source rows.
    # Multiple real messages can share a chat/timestamp window, so track exact
    # source row indexes and mark only rows actually consumed by an IDB merge.
    generic_entries_by_chat_ts = {}
    used_generic_indexes = set()
    for idx, msg in enumerate(sqlite_messages):
        chat_jid, _, _ = normalize_chat_id(msg['chatId'])
        ts = safe_int(msg['timestamp'])
        text = msg['text']
        if chat_jid and ts:
            generic_entries_by_chat_ts.setdefault((chat_jid, ts), []).append({
                'index': idx,
                'id': msg.get('id'),
                'chatId': msg.get('chatId'),
                'timestamp': ts,
                'text': text,
            })

    def pick_generic_text(chat_jid, ts, idb_body, msg_type, media_filename):
        """Return the best unconsumed genericStorage text near an IDB row."""
        if idb_body:
            for entry in generic_entries_by_chat_ts.get((chat_jid, ts), []):
                if entry['index'] in used_generic_indexes:
                    continue
                raw_candidate = entry.get('text') or ''
                if raw_candidate == idb_body:
                    return (entry, raw_candidate, raw_candidate, 0)

        best = None
        best_score = None
        for delta in [0, -1, 1, -2, 2]:
            for entry in generic_entries_by_chat_ts.get((chat_jid, ts + delta), []):
                if entry['index'] in used_generic_indexes:
                    continue
                raw_candidate = entry.get('text') or ''
                if not raw_candidate.strip():
                    continue
                # Preserve genericStorage text as source evidence. Some media
                # rows store filenames or thumbnail-like payloads in text; those
                # still prove the source row exists and must not be filtered here.
                media_cleaned = clean_media_text(raw_candidate, msg_type=msg_type, media_filename=media_filename)
                candidate_for_match = (
                    clean_rich_preview(media_cleaned)
                    if media_cleaned else None
                )
                exact_text = bool(idb_body and raw_candidate == idb_body)
                # Prefer exact timestamp, then exact text, then richer text.
                score = (
                    0 if delta == 0 else 1,
                    0 if exact_text else 1,
                    -len(raw_candidate),
                )
                if best is None or score < best_score:
                    best = (entry, raw_candidate, candidate_for_match, delta)
                    best_score = score
        return best

    idb_messages = idb_data.get('message', [])
    idb_len = len(idb_messages)
    print(
        "  Source messages: "
        f"{idb_len} Store 8 rows, {len(sqlite_messages)} genericStorage rows"
    )

    # Process IndexedDB messages — these have fromMe directly
    idb_batch = []
    idb_msg_keys = set()
    skipped_types = set()
    opaque_unresolved_count = 0

    for i, msg_rec in enumerate(idb_messages):
        if i % 100 == 0 or i == idb_len - 1:
            print_progress(i + 1, idb_len, prefix='Parsing Store 8:', suffix='Complete')

        msg_key = safe_str(msg_rec.get('id'))
        if not msg_key:
            continue
        idb_msg_keys.add(msg_key)

        # Parse fromMe from the msg_key prefix
        from_me, chat_jid, stanza_id, sender_jid = parse_msg_key(msg_key)

        if not chat_jid:
            continue

        # Get timestamp
        ts = safe_int(msg_rec.get('t'))
        if not ts:
            continue

        # Get message type
        msg_type = safe_str(msg_rec.get('type'))

        # Get author (sender for group messages)
        author = msg_rec.get('author')
        if isinstance(author, dict):
            author = author.get('_serialized') or author.get('user')
        elif author is not None:
            author = safe_str(author)
        if author and not sender_jid:
            sender_jid = author

        # Determine group status
        is_group = 1 if '@g.us' in str(chat_jid) else 0
        chat_name = chat_names.get(chat_jid)

        # Resolve chat phone for 1:1 chats
        chat_phone, resolved_name = cached_resolve_jid(chat_jid)
        if not chat_name and resolved_name:
            chat_name = resolved_name

        # Resolve sender phone/name
        sender_phone = None
        sender_name = None
        if sender_jid:
            sender_phone, sender_name = cached_resolve_jid(sender_jid)

        # ── Reply / Quote context ────────────────────────────────────────
        quoted_stanza_id, quoted_participant, quoted_msg_body, quoted_msg_type = extract_quote_context(msg_rec)

        # ── Call log fields ───────────────────────────────────────────────
        call_duration = None
        call_outcome  = None
        is_video_call = 0
        if msg_type == 'call_log':
            call_duration = safe_int(msg_rec.get('callDuration'))
            call_outcome  = safe_str(msg_rec.get('callOutcome') or msg_rec.get('finalCallOutcome'))
            is_video_call = 1 if msg_rec.get('isVideoCall') else 0

        # ── Media metadata ────────────────────────────────────────────────
        media_mime_type = safe_str(msg_rec.get('mimetype'))
        media_filename  = safe_str(msg_rec.get('filename'))
        media_size      = safe_int(msg_rec.get('size'))

        # PRIMARY: read direct body fields. Some newer Store 8 rows only have
        # encrypted msgRowOpaqueData; keep those rows but mark recovery clearly.
        idb_body, idb_body_status = select_indexeddb_message_body(msg_rec)
        runtime_match = runtime_store8_records.get(msg_key)
        if not idb_body and runtime_match:
            runtime_body = runtime_supplement_text(runtime_match)
            if runtime_body:
                idb_body = runtime_body
                idb_body_status = "runtime_store8_decoded"

        # SUPPLEMENT: genericStorage lookup by exact/fuzzy timestamp.
        generic_match = pick_generic_text(
            chat_jid,
            ts,
            idb_body,
            msg_type,
            media_filename,
        )

        source = 'indexeddb'
        source_id = msg_key
        source_chat_id = None
        source_recovery = (
            'store8_opaque_decrypted'
            if idb_body_status == 'opaque_decrypted'
            else ('store8_runtime_decoded' if idb_body_status == 'runtime_store8_decoded'
            else ('store8_opaque_unresolved' if idb_body_status == 'opaque_unresolved' else 'store8')
            )
        )
        store8_decrypted_text = idb_body if idb_body_status in ('opaque_decrypted', 'runtime_store8_decoded') else None
        store8_decryption_status = (
            idb_body_status
            if idb_body_status.startswith('opaque_') or idb_body_status.startswith('runtime_')
            else None
        )
        text_conflict_status = None

        # Use whichever is richer, but consume a genericStorage row only when
        # it is identical to the IDB body or actually supplies the chosen text.
        text = idb_body
        preserve_raw_text = False
        if generic_match:
            entry, generic_text_raw, generic_text_for_match, delta = generic_match
            if delta == 0 and idb_body and generic_text_raw == idb_body:
                used_generic_indexes.add(entry['index'])
                source = 'indexeddb+genericStorage'
                source_id = f"{msg_key}|{entry.get('id')}"
                source_chat_id = entry.get('chatId')
                source_recovery = 'store8+genericStorage_exact'
                preserve_raw_text = True
            elif delta == 0 and generic_text_for_match and not idb_body:
                used_generic_indexes.add(entry['index'])
                text = generic_text_for_match
                source = 'indexeddb+genericStorage'
                source_id = f"{msg_key}|{entry.get('id')}"
                source_chat_id = entry.get('chatId')
                source_recovery = 'store8+genericStorage_exact'
                preserve_raw_text = generic_text_for_match == generic_text_raw
            elif (
                delta == 0
                and generic_text_for_match
                and idb_body
                and idb_body_status in ('opaque_decrypted', 'runtime_store8_decoded')
                and generic_text_for_match != idb_body
            ):
                used_generic_indexes.add(entry['index'])
                text = generic_text_for_match
                source = 'indexeddb+genericStorage'
                source_id = f"{msg_key}|{entry.get('id')}"
                source_chat_id = entry.get('chatId')
                source_recovery = f"{source_recovery}+genericStorage_conflict"
                text_conflict_status = 'genericStorage_text_preserved'
                preserve_raw_text = generic_text_for_match == generic_text_raw
                record_warning(
                    "Store 8 decrypted text conflicts with genericStorage text; preserved genericStorage text as primary.",
                    msg_key=msg_key,
                    timestamp=ts,
                    store8_text_sha256=sha256_bytes(idb_body.encode("utf-8", "replace")),
                    generic_text_sha256=sha256_bytes(generic_text_for_match.encode("utf-8", "replace")),
                )

        if not preserve_raw_text:
            # Strip base64 thumbnail blobs stored as text by non-source UI fields.
            text = clean_media_text(text, msg_type=msg_type, media_filename=media_filename)
            # Strip social media rich-preview metadata from link messages.
            if text:
                text = clean_rich_preview(text)

        if not text and idb_body_status == 'opaque_unresolved':
            opaque_unresolved_count += 1

        body_status = classify_body_status(
            text=text,
            msg_type=msg_type,
            source=source,
            source_recovery=source_recovery,
            store8_status=store8_decryption_status,
            media_mime_type=media_mime_type,
            media_filename=media_filename,
            media_size=media_size,
        )
        media_status = initial_media_status(
            msg_type=msg_type,
            media_mime_type=media_mime_type,
            media_filename=media_filename,
            media_size=media_size,
        )
        edit_marker = extract_edit_marker(msg_rec, msg_key)
        row_is_edited = 1 if edit_marker and not is_message_edit_protocol(msg_rec) else 0
        row_edited_at = edit_marker.get("edited_at") if row_is_edited else None
        row_edit_status = "marker_only" if row_is_edited else None

        idb_batch.append((
            msg_key, stanza_id, chat_jid, chat_name, chat_phone,
            sender_jid, sender_phone, sender_name,
            from_me, ts, text, is_group,
            msg_type,
            quoted_stanza_id, quoted_participant, quoted_msg_body, quoted_msg_type,
            call_duration, call_outcome, is_video_call,
            media_mime_type, media_filename, media_size,
            source, source_id, source_chat_id, source_recovery,
            store8_decrypted_text, store8_decryption_status, text_conflict_status,
            body_status, None, None, media_status,
            row_is_edited, row_edited_at, 0, row_edit_status,
        ))
        queue_mentions(msg_key, chat_jid, msg_rec, "store8")
        queue_edit_evidence(msg_key, chat_jid, stanza_id, sender_jid, msg_rec, "store8", text)

    if opaque_unresolved_count:
        record_warning(
            "Store 8 encrypted opaque rows remained without body text after genericStorage merge.",
            count=opaque_unresolved_count,
            recovery="store8_opaque_unresolved",
        )
        log_detail(f"  Opaque Store 8 rows without recovered text: {opaque_unresolved_count}")

    # Insert all IndexedDB messages
    log_detail(f"  Inserting {len(idb_batch)} messages from IndexedDB Store 8...")
    execute_many_counting(cursor, message_insert_sql, idb_batch, "indexeddb_message_insert")
    conn.commit()

    # Runtime capture can see serializer output for rows that are no longer in
    # the copied Store 8 snapshot. Keep those as supplement-only forensic rows.
    runtime_only_batch = []
    runtime_generic_coverage = Counter()
    for msg_key, runtime_rec in runtime_store8_records.items():
        if msg_key in idb_msg_keys:
            continue

        from_me, chat_jid, stanza_id, sender_jid = parse_msg_key(msg_key)
        chat_jid = chat_jid or safe_str(runtime_rec.get('chat_jid'))
        if not chat_jid:
            record_warning(
                "Runtime Store 8 supplement row has text but no parseable chat JID.",
                msg_key=msg_key,
                row_id=safe_str(runtime_rec.get('row_id')),
            )
            continue

        ts = safe_int(runtime_rec.get('timestamp') or runtime_rec.get('t'))
        if not ts:
            record_warning(
                "Runtime Store 8 supplement row has text but no usable timestamp.",
                msg_key=msg_key,
                row_id=safe_str(runtime_rec.get('row_id')),
            )
            continue

        if from_me is None and isinstance(runtime_rec.get('from_me'), bool):
            from_me = 1 if runtime_rec.get('from_me') else 0

        sender_jid = sender_jid or safe_str(runtime_rec.get('sender_jid'))
        msg_type = safe_str(runtime_rec.get('type')) or 'chat'
        text = runtime_supplement_text(runtime_rec)
        is_group = 1 if '@g.us' in str(chat_jid) else 0
        chat_name = chat_names.get(chat_jid)

        chat_phone, resolved_name = cached_resolve_jid(chat_jid)
        if not chat_name and resolved_name:
            chat_name = resolved_name

        sender_phone = None
        sender_name = None
        if sender_jid:
            sender_phone, sender_name = cached_resolve_jid(sender_jid)

        media_mime_type = safe_str(runtime_rec.get('mimetype'))
        media_filename = safe_str(runtime_rec.get('filename'))
        media_size = safe_int(runtime_rec.get('size') or runtime_rec.get('media_size'))
        quoted_stanza_id, quoted_participant, quoted_msg_body, quoted_msg_type = extract_quote_context(runtime_rec)
        source_recovery = 'runtime_store8_only'
        store8_decryption_status = 'runtime_store8_decoded' if text else None
        body_status = classify_body_status(
            text=text,
            msg_type=msg_type,
            source='runtime_store8',
            source_recovery=source_recovery,
            store8_status=store8_decryption_status,
            media_mime_type=media_mime_type,
            media_filename=media_filename,
            media_size=media_size,
        )
        if not text and body_status == 'missing_unexpected':
            continue

        media_status = initial_media_status(
            msg_type=msg_type,
            media_mime_type=media_mime_type,
            media_filename=media_filename,
            media_size=media_size,
        )
        edit_marker = extract_edit_marker(runtime_rec, msg_key)
        row_is_edited = 1 if edit_marker and not is_message_edit_protocol(runtime_rec) else 0
        row_edited_at = edit_marker.get("edited_at") if row_is_edited else None
        row_edit_status = "marker_only" if row_is_edited else None

        runtime_only_batch.append((
            msg_key, stanza_id or safe_str(runtime_rec.get('row_id')) or msg_key,
            chat_jid, chat_name, chat_phone,
            sender_jid, sender_phone, sender_name,
            from_me, ts, text, is_group,
            msg_type,
            quoted_stanza_id, quoted_participant, quoted_msg_body, quoted_msg_type,
            None, None, 0,
            media_mime_type, media_filename, media_size,
            'runtime_store8', msg_key, chat_jid, source_recovery,
            text, store8_decryption_status, None,
            body_status, None, None, media_status,
            row_is_edited, row_edited_at, 0, row_edit_status,
        ))
        if text:
            runtime_generic_coverage[(chat_jid, ts, message_identity_text(text))] += 1
        queue_mentions(msg_key, chat_jid, runtime_rec, "runtime")
        queue_edit_evidence(msg_key, chat_jid, stanza_id, sender_jid, runtime_rec, "runtime", text)

    if runtime_only_batch:
        log_detail(f"  Inserting {len(runtime_only_batch)} runtime-only Store 8 messages...")
        execute_many_counting(cursor, message_insert_sql, runtime_only_batch, "runtime_store8_only_insert")
        cursor.execute("""
            INSERT OR REPLACE INTO extraction_metadata (key, value)
            VALUES ('runtime_store8_only_inserted', ?)
        """, (str(len(runtime_only_batch)),))
    conn.commit()

    if mention_batch:
        execute_many_counting(cursor, """
            INSERT OR IGNORE INTO message_mentions
            (msg_key, chat_jid, mention_index, kind, target_jid, target_phone,
             target_name, display_text, source, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, mention_batch, "message_mention_insert")
        conn.commit()

    # Now insert any genericStorage messages NOT specifically consumed above.
    # (these will have from_me=NULL but at least preserve the text)
    fts_only_batch = []
    fts_len = len(sqlite_messages)

    # Process only if we actually have FTS messages
    if fts_len > 0:
        for i, msg in enumerate(sqlite_messages):
            if i % 100 == 0 or i == fts_len - 1:
                print_progress(i + 1, fts_len, prefix='Parsing FTS:    ', suffix='Complete')

            raw_chat_id = msg['chatId']
            chat_jid, stanza_id, sender_jid = normalize_chat_id(raw_chat_id)
            ts = safe_int(msg['timestamp'])
            text = msg['text']

            if not chat_jid or not ts:
                continue

            # Skip only rows that were actually consumed by an IndexedDB merge.
            # Timestamp-only coverage is unsafe for forensics because several
            # distinct messages can sit inside the same ±2s window.
            if i in used_generic_indexes:
                continue

            runtime_key = (chat_jid, ts, message_identity_text(text))
            if runtime_generic_coverage.get(runtime_key, 0) > 0:
                runtime_generic_coverage[runtime_key] -= 1
                continue

            is_group = 1 if '@g.us' in str(chat_jid) else 0
            chat_name = chat_names.get(chat_jid)
            chat_phone, resolved_name = cached_resolve_jid(chat_jid)
            if not chat_name and resolved_name:
                chat_name = resolved_name
            sender_phone = None
            sender_name = None
            if sender_jid:
                sender_phone, sender_name = cached_resolve_jid(sender_jid)

            body_status = classify_body_status(
                text=text,
                msg_type='chat',
                source='genericStorage',
                source_recovery='sqlite_recovered_row',
            )

            fts_only_batch.append((
                None, stanza_id or str(msg['id']), chat_jid, chat_name, chat_phone,
                sender_jid, sender_phone, sender_name,
                None, ts, text, is_group,
                'chat', None, None, None, None,
                None, None, 0, None, None, None,
                'genericStorage', str(msg['id']), raw_chat_id, 'sqlite_recovered_row',
                None, None, None,
                body_status, None, None, None,
                0, None, 0, None,
            ))

    if fts_only_batch:
        log_detail(f"  Inserting {len(fts_only_batch)} FTS-only messages (no IndexedDB match)...")
        execute_many_counting(cursor, message_insert_sql, fts_only_batch, "generic_storage_message_insert")
    conn.commit()

    print("  [>] Creating unified query indexes...")
    create_unified_indexes(conn)
    conn.commit()

    # ── Fallback enrichment for FTS-only messages ─────────────────────────
    # Store 8 only keeps recent messages; older ones exist only in FTS.
    # Use reporting-info (received msgs) and message-info (sent msgs)
    # timestamps to populate fromMe for those.
    ts_lookup = {}  # (chat_jid, ts) -> (msgKey, from_me, sender)

    for ri in idb_data.get('reporting-info', []):
        mk = safe_str(ri.get('msgKey'))
        if not mk:
            continue
        fm, cjid, stanza, sender = parse_msg_key(mk)
        ts = safe_int(ri.get('msgTs'))
        if cjid and ts:
            key = (cjid, ts)
            if key not in ts_lookup:
                ts_lookup[key] = (mk, fm, sender)

    for mi in idb_data.get('message-info', []):
        mk = safe_str(mi.get('msgKey'))
        if not mk:
            continue
        fm, cjid, stanza, sender = parse_msg_key(mk)
        ts = safe_int(mi.get('delivery'))
        if cjid and ts:
            key = (cjid, ts)
            if key not in ts_lookup:
                ts_lookup[key] = (mk, fm, sender)

    # Pass: exact + fuzzy ±2s timestamp match on FTS-only messages
    fallback_enriched = 0
    fallback_updates = []
    cursor.execute("""
        SELECT rowid, chat_jid, timestamp FROM messages
        WHERE from_me IS NULL AND timestamp IS NOT NULL
    """)
    for rowid, chat_jid, ts in cursor.fetchall():
        matched = None
        for delta in [0, -1, 1, -2, 2]:
            key = (chat_jid, ts + delta)
            if key in ts_lookup:
                matched = ts_lookup[key]
                break
        if matched:
            mk, fm, sender = matched
            s_phone, s_name = (None, None)
            if sender:
                s_phone, s_name = cached_resolve_jid(sender)
            fallback_updates.append((mk, fm, sender, s_phone, s_name, rowid))

    if fallback_updates:
        cursor.executemany("""
            UPDATE messages SET
                msg_key = COALESCE(msg_key, ?),
                from_me = ?,
                sender_jid = COALESCE(sender_jid, ?),
                sender_phone = COALESCE(sender_phone, ?),
                sender_name = COALESCE(sender_name, ?)
            WHERE rowid = ? AND from_me IS NULL
        """, fallback_updates)
        fallback_enriched = len(fallback_updates)

    conn.commit()
    log_detail(f"  Fallback enrichment (reporting+message-info): {fallback_enriched} messages")

    # In 1:1 chats, WhatsApp FTS-only rows represent messages sent by self.
    # Keep unresolved personal-chat direction conservative and explicit.
    cursor.execute("""
        UPDATE messages SET from_me = 1
        WHERE from_me IS NULL AND is_group = 0
    """)
    personal_fixed = cursor.rowcount
    conn.commit()
    log_detail(f"  Personal-chat fromMe fix: {personal_fixed} messages set to sent")

    # ── Edited-message evidence ──────────────────────────────────────────
    def target_row_for_msg_key(target_key):
        return cursor.execute(
            """
            SELECT rowid, chat_jid, msg_id, text, timestamp
            FROM messages
            WHERE msg_key = ?
            ORDER BY rowid ASC
            LIMIT 1
            """,
            (target_key,),
        ).fetchone()

    def insert_message_edit(target_key, event, edit_index, target_chat_jid=None, target_msg_id=None, previous_text=None):
        editor_jid = event.get("editor_jid")
        editor_phone = event.get("editor_phone")
        editor_name = event.get("editor_name")
        cursor.execute(
            """
            INSERT OR IGNORE INTO message_edits
            (target_msg_key, target_chat_jid, target_msg_id, edit_event_msg_key,
             edit_index, edited_at, editor_jid, editor_phone, editor_name,
             previous_text, new_text, source, confidence, provenance_sha256)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                target_key,
                target_chat_jid,
                target_msg_id,
                event.get("edit_event_msg_key"),
                edit_index,
                event.get("edited_at"),
                editor_jid,
                editor_phone,
                editor_name,
                previous_text,
                event.get("new_text"),
                event.get("source"),
                event.get("confidence"),
                event.get("provenance_sha256"),
            ),
        )
        return cursor.rowcount > 0

    edit_targets_seen = set()
    edit_protocol_folded = 0
    edit_protocol_orphans = 0
    events_by_target = {}
    for event in edit_events.values():
        events_by_target.setdefault(event["target_msg_key"], []).append(event)

    for target_key, events in events_by_target.items():
        events.sort(key=lambda ev: ((ev.get("edited_at") or 0), ev.get("edit_event_msg_key") or ""))
        row = target_row_for_msg_key(target_key)
        orphan_recovered = False
        if not row:
            first = next((ev for ev in events if ev.get("new_text")), events[0])
            if first.get("new_text"):
                from_me, chat_jid, stanza_id, sender_jid = parse_msg_key(target_key)
                chat_jid = chat_jid or safe_str(first.get("target_chat_jid"))
                if chat_jid:
                    chat_name = chat_names.get(chat_jid)
                    chat_phone, resolved_name = cached_resolve_jid(chat_jid)
                    if not chat_name and resolved_name:
                        chat_name = resolved_name
                    sender_phone, sender_name = cached_resolve_jid(sender_jid) if sender_jid else (None, None)
                    body_status = classify_body_status(
                        text=first.get("new_text"),
                        msg_type="chat",
                        source=first.get("source"),
                        source_recovery="store8_message_edit_orphan",
                    )
                    cursor.execute(message_insert_sql, (
                        target_key, stanza_id, chat_jid, chat_name, chat_phone,
                        sender_jid, sender_phone, sender_name,
                        from_me, first.get("edited_at"), first.get("new_text"),
                        1 if "@g.us" in chat_jid else 0,
                        "chat", None, None, None, None,
                        None, None, 0,
                        None, None, None,
                        first.get("source") or "store8",
                        first.get("edit_event_msg_key"),
                        chat_jid,
                        "store8_message_edit_orphan",
                        first.get("new_text"),
                        "runtime_store8_decoded" if first.get("source") == "runtime" else None,
                        None,
                        body_status,
                        None, None, None,
                        1, first.get("edited_at"), len(events), "event_only_orphan",
                    ))
                    row = target_row_for_msg_key(target_key)
                    edit_protocol_orphans += 1
                    orphan_recovered = True
        if not row:
            continue

        rowid, target_chat_jid, target_msg_id, _target_text, _target_ts = row
        edit_targets_seen.add(target_key)
        inserted = 0
        for idx, event in enumerate(events, start=1):
            if insert_message_edit(target_key, event, idx, target_chat_jid, target_msg_id):
                inserted += 1
        latest_time = max((ev.get("edited_at") or 0 for ev in events), default=0) or None
        status = "event_only_orphan" if orphan_recovered else "event_history"
        cursor.execute(
            """
            UPDATE messages
            SET is_edited = 1,
                edited_at = COALESCE(?, edited_at),
                edit_count = MAX(COALESCE(edit_count, 0), ?),
                edit_history_status = ?
            WHERE msg_key = ?
            """,
            (latest_time, len(events), status, target_key),
        )
        edit_protocol_folded += inserted

    for target_key, marker in edit_markers.items():
        if target_key in edit_targets_seen:
            continue
        row = target_row_for_msg_key(target_key)
        if not row:
            continue
        cursor.execute(
            """
            UPDATE messages
            SET is_edited = 1,
                edited_at = COALESCE(?, edited_at),
                edit_history_status = COALESCE(edit_history_status, 'marker_only')
            WHERE msg_key = ?
            """,
            (marker.get("edited_at"), target_key),
        )

    # Preserve same-key text variants before stable-key deduplication.
    cursor.execute(
        """
        SELECT msg_key
        FROM messages
        WHERE msg_key IS NOT NULL
        GROUP BY msg_key
        HAVING COUNT(*) > 1 AND COUNT(DISTINCT COALESCE(text, '')) > 1
        """
    )
    variant_keys = [row[0] for row in cursor.fetchall()]
    variant_revision_count = 0
    # Prefetch existing message_edits counts once instead of running a
    # SELECT COUNT(*) per target_key inside the loop below.
    existing_edit_counts = {
        row[0]: row[1]
        for row in cursor.execute(
            "SELECT target_msg_key, COUNT(*) FROM message_edits "
            "WHERE target_msg_key IS NOT NULL GROUP BY target_msg_key"
        ).fetchall()
    }
    for target_key in variant_keys:
        rows = cursor.execute(
            """
            SELECT rowid, chat_jid, msg_id, timestamp, text, sender_jid, sender_phone, sender_name
            FROM messages
            WHERE msg_key = ?
            ORDER BY COALESCE(timestamp, 0), rowid
            """,
            (target_key,),
        ).fetchall()
        if len(rows) < 2:
            continue
        base = rows[0]
        previous_text = base[4]
        existing_count = existing_edit_counts.get(target_key, 0)
        for offset, row in enumerate(rows[1:], start=1):
            text_variant = row[4]
            if (text_variant or "") == (previous_text or ""):
                continue
            event = {
                "edit_event_msg_key": target_key,
                "edited_at": row[3],
                "editor_jid": row[5],
                "editor_phone": row[6],
                "editor_name": row[7],
                "previous_text": previous_text,
                "new_text": text_variant,
                "source": "same_msg_key_variant",
                "confidence": "medium",
                "provenance_sha256": sha256_bytes(f"{target_key}:{row[0]}:{text_variant}".encode("utf-8", "replace")),
            }
            if insert_message_edit(
                target_key,
                event,
                existing_count + offset,
                base[1],
                base[2],
                previous_text=previous_text,
            ):
                variant_revision_count += 1
            previous_text = text_variant
        latest = rows[-1]
        cursor.execute(
            """
            UPDATE messages
            SET text = COALESCE(?, text),
                is_edited = 1,
                edited_at = COALESCE(?, edited_at),
                edit_count = (
                    SELECT COUNT(*) FROM message_edits WHERE target_msg_key = ?
                ),
                edit_history_status = COALESCE(edit_history_status, 'variant_history')
            WHERE rowid = ?
            """,
            (latest[4], latest[3], target_key, base[0]),
        )

    conn.commit()
    if edit_markers or edit_events or variant_revision_count:
        cursor.executemany(
            "INSERT OR REPLACE INTO extraction_metadata (key, value) VALUES (?, ?)",
            {
                "edited_message_markers": str(len(edit_markers)),
                "message_edit_protocol_events": str(len(edit_events)),
                "message_edit_protocol_folded": str(edit_protocol_folded),
                "message_edit_protocol_orphans": str(edit_protocol_orphans),
                "message_edit_variant_revisions": str(variant_revision_count),
            }.items(),
        )
        conn.commit()

    # ── Enrich quoted-message bodies from originals in the same chat ───────
    # Newer WhatsApp exports often omit quotedMsg.body, but the original row is
    # usually present. Fill the denormalized quote preview for future DBs.
    quote_body_changes_before = conn.total_changes
    cursor.execute("""
        WITH original_quotes AS (
            SELECT chat_jid, msg_id, text, msg_type
            FROM (
                SELECT
                    chat_jid,
                    msg_id,
                    text,
                    msg_type,
                    ROW_NUMBER() OVER (
                        PARTITION BY chat_jid, msg_id
                        ORDER BY timestamp ASC, rowid ASC
                    ) AS rn
                FROM messages
                WHERE msg_id IS NOT NULL
                  AND text IS NOT NULL
                  AND TRIM(text) != ''
            )
            WHERE rn = 1
        )
        UPDATE messages AS q
        SET quoted_msg_body = original_quotes.text,
            quoted_msg_type = COALESCE(q.quoted_msg_type, original_quotes.msg_type)
        FROM original_quotes
        WHERE q.chat_jid = original_quotes.chat_jid
          AND q.quoted_stanza_id = original_quotes.msg_id
          AND q.quoted_stanza_id IS NOT NULL
          AND (q.quoted_msg_body IS NULL OR TRIM(q.quoted_msg_body) = '')
    """)
    quote_body_fixed = conn.total_changes - quote_body_changes_before
    conn.commit()
    log_detail(f"  Quote body enrichment: {quote_body_fixed} replies filled from original messages")

    # ── Deduplicate only stable IndexedDB key duplicates ─────────────────
    # Do not collapse by text/timestamp. For forensic work, repeated source
    # rows with the same text and timestamp can be real evidence.
    cursor.execute("""
        DELETE FROM messages
        WHERE rowid IN (
            SELECT m.rowid
            FROM messages AS m
            JOIN (
                SELECT msg_key, MIN(rowid) AS keep_rowid
                FROM messages
                WHERE msg_key IS NOT NULL
                GROUP BY msg_key
                HAVING COUNT(*) > 1
            ) AS duplicates
              ON m.msg_key = duplicates.msg_key
             AND m.rowid != duplicates.keep_rowid
        )
    """)
    deduped1 = cursor.rowcount
    conn.commit()

    log_detail(f"  Deduplication: removed {deduped1} duplicate messages (exact match)")

    # Summary
    cursor.execute("SELECT COUNT(*) FROM messages WHERE from_me IS NOT NULL")
    enriched_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM messages")
    total_count = cursor.fetchone()[0]
    if total_count > 0:
        log_detail(f"  fromMe coverage: {enriched_count}/{total_count} ({enriched_count/total_count*100:.1f}%)")
    else:
        log_detail("  fromMe coverage: N/A (0 messages)")

    # ── Message receipts ──────────────────────────────────────────────────
    receipt_batch = []
    for mi in idb_data.get('message-info', []):
        mk = safe_str(mi.get('msgKey'))
        recv_jid = safe_str(mi.get('receiverUserJid'))
        if not mk or not recv_jid:
            continue

        recv_phone, recv_name = cached_resolve_jid(recv_jid)
        delivery = safe_int(mi.get('delivery'))
        read = safe_int(mi.get('read'))
        played = safe_int(mi.get('played'))

        receipt_batch.append((mk, recv_jid, recv_phone, recv_name, delivery, read, played))

    if receipt_batch:
        execute_many_counting(cursor, """
            INSERT OR IGNORE INTO message_receipts
            (msg_key, receiver_jid, receiver_phone, receiver_name,
             delivery_time, read_time, played_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, receipt_batch, "message_receipt_insert")

    conn.commit()

    # ── Reactions ─────────────────────────────────────────────────────────
    reaction_batch = []
    for rxn in idb_data.get('reactions', []):
        parent = safe_str(rxn.get('parentMsgKey'))
        sender = safe_str(rxn.get('senderUserJid'))
        text = safe_str(rxn.get('reactionText'))
        ts = safe_int(rxn.get('timestamp'))

        if not parent or not sender:
            continue

        s_phone, s_name = cached_resolve_jid(sender)

        reaction_batch.append((parent, sender, s_phone, s_name, text, ts))

    if reaction_batch:
        execute_many_counting(cursor, """
            INSERT OR IGNORE INTO reactions
            (parent_msg_key, sender_jid, sender_phone, sender_name,
             reaction_text, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, reaction_batch, "reaction_insert")

    conn.commit()

    # ── Final stats ───────────────────────────────────────────────────────
    cursor.execute("SELECT COUNT(*) FROM messages")
    total_msgs = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM messages WHERE from_me IS NOT NULL")
    enriched_msgs = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM messages WHERE from_me = 1")
    sent = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM messages WHERE from_me = 0")
    received = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM contacts")
    total_contacts = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM contacts WHERE phone_number IS NOT NULL")
    resolved_contacts = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM chats")
    total_chats = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM reactions")
    total_reactions = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM messages WHERE text IS NULL OR TRIM(text) = ''")
    null_or_blank_text = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM messages WHERE store8_decryption_status = 'opaque_decrypted'")
    store8_decrypted_messages = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM messages WHERE store8_decryption_status = 'runtime_store8_decoded'")
    store8_runtime_decoded_messages = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM messages WHERE text_conflict_status IS NOT NULL")
    text_conflicts = cursor.fetchone()[0]
    cursor.execute("SELECT body_status, COUNT(*) FROM messages GROUP BY body_status")
    body_status_counts = {str(k or "unset"): int(v) for k, v in cursor.fetchall()}
    store8_opaque_unresolved_messages = body_status_counts.get("opaque_unresolved", 0)

    # Store final stats
    for k, v in {
        'total_messages': total_msgs,
        'messages_with_direction': enriched_msgs,
        'messages_sent': sent,
        'messages_received': received,
        'total_contacts': total_contacts,
        'resolved_contacts': resolved_contacts,
        'total_chats': total_chats,
        'total_reactions': total_reactions,
        'messages_null_or_blank_text': null_or_blank_text,
        'generic_storage_rows': len(sqlite_messages),
        'generic_storage_rows_merged': len(used_generic_indexes),
        'generic_storage_rows_inserted_unmatched': len(fts_only_batch),
        'store8_opaque_decrypted_messages': store8_decrypted_messages,
        'store8_runtime_decoded_messages': store8_runtime_decoded_messages,
        'store8_opaque_unresolved_messages': store8_opaque_unresolved_messages,
        'text_conflicts': text_conflicts,
        'body_status_counts': json.dumps(body_status_counts, sort_keys=True),
    }.items():
        cursor.execute(
            "INSERT OR REPLACE INTO extraction_metadata (key, value) VALUES (?, ?)",
            (k, str(v))
        )

    conn.commit()
    conn.close()

    return {
        'messages': total_msgs,
        'enriched': enriched_msgs,
        'sent': sent,
        'received': received,
        'contacts': total_contacts,
        'resolved': resolved_contacts,
        'chats': total_chats,
        'reactions': total_reactions,
        'null_or_blank_text': null_or_blank_text,
        'generic_storage_rows': len(sqlite_messages),
        'generic_storage_merged': len(used_generic_indexes),
        'generic_storage_inserted_unmatched': len(fts_only_batch),
        'store8_opaque_decrypted_messages': store8_decrypted_messages,
        'store8_runtime_decoded_messages': store8_runtime_decoded_messages,
        'store8_opaque_unresolved_messages': store8_opaque_unresolved_messages,
        'text_conflicts': text_conflicts,
        'body_status_counts': body_status_counts,
    }


def iter_local_media_files(case_root):
    """Yield local media-like files already present in a copied WAren6 case."""
    case_root = pathlib.Path(case_root)
    roots = []
    sessions_root = case_root / "sessions"
    if sessions_root.exists():
        roots.extend(path for path in sessions_root.glob("*/transfers") if path.is_dir())
        direct_transfers = sessions_root / "transfers"
        if direct_transfers.is_dir():
            roots.append(direct_transfers)
    indexeddb_root = case_root / "EBWebView_Default" / "IndexedDB"
    if indexeddb_root.exists():
        roots.extend(path for path in indexeddb_root.glob("*.indexeddb.blob") if path.is_dir())
    skipped_suffixes = {
        ".db", ".db-wal", ".db-shm", ".log", ".ldb", ".txt", ".json",
        ".manifest", ".current",
    }
    for root in roots:
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() in skipped_suffixes:
                continue
            yield file_path


def _case_relative(path, case_root):
    try:
        return str(pathlib.Path(path).resolve().relative_to(pathlib.Path(case_root).resolve()))
    except Exception:
        return str(path)


def index_local_media_assets(db_path, case_root, enabled=True):
    """Index local media files and link them to message rows by filename."""
    db_path = pathlib.Path(db_path)
    case_root = pathlib.Path(case_root)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(UNIFIED_SCHEMA)
        conn.execute(
            """
            UPDATE messages
            SET media_status = COALESCE(media_status, 'metadata_only')
            WHERE (media_filename IS NOT NULL AND TRIM(media_filename) <> '')
               OR (media_mime_type IS NOT NULL AND TRIM(media_mime_type) <> '')
               OR COALESCE(msg_type, '') IN ('image','video','sticker','ptt','audio','ptv','document','album','gif')
            """
        )
        if not enabled:
            conn.commit()
            return {
                "schema": "waren6.media-index-report.v1",
                "enabled": False,
                "files_indexed": 0,
                "assets_linked": 0,
                "messages_with_local_media": 0,
                "messages_missing_local_media": sqlite_scalar(
                    conn,
                    "SELECT COUNT(*) FROM messages WHERE media_status = 'metadata_only'",
                ),
            }

        message_rows = conn.execute(
            """
            SELECT rowid, msg_key, chat_jid, media_filename, media_mime_type
            FROM messages
            WHERE media_filename IS NOT NULL AND TRIM(media_filename) <> ''
            """
        ).fetchall()
        by_filename = {}
        for rowid, msg_key, chat_jid, filename, mime in message_rows:
            by_filename.setdefault(str(filename).lower(), []).append({
                "rowid": rowid,
                "msg_key": msg_key,
                "chat_jid": chat_jid,
                "mime": mime,
            })

        # Dedup pass first (cheap: resolve() + set membership). We hash and
        # match after this so we never SHA-256 the same physical file twice.
        distinct_files = []
        seen_files = set()
        for file_path in iter_local_media_files(case_root):
            try:
                resolved = str(file_path.resolve())
            except OSError:
                continue
            if resolved in seen_files:
                continue
            seen_files.add(resolved)
            distinct_files.append(file_path)

        # Parallel SHA-256: hashlib releases the GIL inside .update(), so
        # threads scale linearly on multi-core boxes without the memory
        # overhead of a process pool. Cap at 4 to stay friendly on modest
        # dual-core boxes (older laptops, low-power field-kit hardware).
        def _stat_and_hash(path):
            try:
                size = path.stat().st_size
            except OSError:
                return None
            try:
                digest = sha256_file(path)
            except OSError:
                return None
            return (path, size, digest)

        worker_count = max(1, min(4, os.cpu_count() or 1))
        hashed_entries = []
        if distinct_files:
            with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as pool:
                for entry in pool.map(_stat_and_hash, distinct_files):
                    if entry is not None:
                        hashed_entries.append(entry)

        # Build the write buffers in a single deterministic pass, then flush
        # with executemany so we take one B-tree traversal per (INSERT|UPDATE)
        # batch instead of one per row.
        files_indexed = 0
        assets_linked = 0
        insert_rows = []
        update_rows = []
        for file_path, size, digest in hashed_entries:
            files_indexed += 1
            filename = file_path.name
            rel = _case_relative(file_path, case_root)
            mime = mimetypes.guess_type(filename)[0]
            matches = by_filename.get(filename.lower()) or [None]
            for match in matches:
                insert_rows.append((
                    match.get("msg_key") if match else None,
                    match.get("chat_jid") if match else None,
                    str(file_path),
                    rel,
                    filename,
                    match.get("mime") if match and match.get("mime") else mime,
                    size,
                    digest,
                    "local_case_file",
                    "local_present" if match else "unlinked_local_file",
                ))
                if match:
                    update_rows.append((rel, digest, match["rowid"]))
                    assets_linked += 1

        if insert_rows:
            conn.executemany(
                """
                INSERT INTO media_assets
                (msg_key, chat_jid, original_path, case_relative_path, filename,
                 mime_type, size, sha256, acquisition_method, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                insert_rows,
            )
        if update_rows:
            conn.executemany(
                """
                UPDATE messages
                SET media_case_path = COALESCE(media_case_path, ?),
                    media_sha256 = COALESCE(media_sha256, ?),
                    media_status = 'local_present'
                WHERE rowid = ?
                """,
                update_rows,
            )

        conn.execute(
            """
            UPDATE messages
            SET media_status = 'missing_local_file'
            WHERE media_status = 'metadata_only'
              AND ((media_filename IS NOT NULL AND TRIM(media_filename) <> '')
                OR (media_mime_type IS NOT NULL AND TRIM(media_mime_type) <> '')
                OR COALESCE(msg_type, '') IN ('image','video','sticker','ptt','audio','ptv','document','album','gif'))
            """
        )
        conn.commit()
        report = {
            "schema": "waren6.media-index-report.v1",
            "enabled": True,
            "case_root": str(case_root),
            "files_indexed": files_indexed,
            "assets_linked": assets_linked,
            "messages_with_local_media": sqlite_scalar(
                conn,
                "SELECT COUNT(*) FROM messages WHERE media_status = 'local_present'",
            ),
            "messages_missing_local_media": sqlite_scalar(
                conn,
                "SELECT COUNT(*) FROM messages WHERE media_status = 'missing_local_file'",
            ),
            "unlinked_local_files": sqlite_scalar(
                conn,
                "SELECT COUNT(*) FROM media_assets WHERE status = 'unlinked_local_file'",
            ),
        }
        for k, v in report.items():
            if k == "schema":
                continue
            conn.execute(
                "INSERT OR REPLACE INTO extraction_metadata(key, value) VALUES (?, ?)",
                (f"media_{k}", json.dumps(v) if isinstance(v, (dict, list)) else str(v)),
            )
        conn.commit()
        return report
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Validation and report generation
# ─────────────────────────────────────────────────────────────────────────────

def sqlite_scalar(conn, sql, params=(), default=0):
    try:
        row = conn.execute(sql, params).fetchone()
        return row[0] if row else default
    except sqlite3.Error:
        return default


def sqlite_table_exists(conn, table_name):
    try:
        row = conn.execute(
            "SELECT COUNT(1) FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
        return bool(row and row[0])
    except sqlite3.Error:
        return False


def sqlite_column_exists(conn, table_name, column_name):
    try:
        return any(row[1] == column_name for row in conn.execute(f"PRAGMA table_info({table_name})"))
    except sqlite3.Error:
        return False


def source_text_counter(sqlite_messages):
    counter = Counter()
    for msg in sqlite_messages:
        text = normalize_source_text_for_validation(msg.get('text'))
        if not text:
            continue
        chat_jid, _, _ = normalize_chat_id(msg.get('chatId'))
        ts = safe_int(msg.get('timestamp'))
        if chat_jid and ts:
            counter[(chat_jid, ts, text)] += 1
    return counter


def unified_text_counter(conn):
    counter = Counter()
    for chat_jid, ts, text in conn.execute(
        "SELECT chat_jid, timestamp, text FROM messages WHERE text IS NOT NULL AND TRIM(text) <> ''"
    ):
        normalized = normalize_source_text_for_validation(text)
        if chat_jid and ts and normalized:
            counter[(chat_jid, int(ts), normalized)] += 1
    return counter


def unified_media_filename_counter(conn):
    counter = Counter()
    for chat_jid, ts, filename in conn.execute(
        "SELECT chat_jid, timestamp, media_filename FROM messages WHERE media_filename IS NOT NULL AND TRIM(media_filename) <> ''"
    ):
        if chat_jid and ts and filename:
            counter[(chat_jid, int(ts), filename)] += 1
    return counter


def validate_unified_database(db_path, sqlite_messages=None, runtime_store8_supplement=None):
    sqlite_messages = sqlite_messages or []
    runtime_store8_supplement = runtime_store8_supplement or {}
    conn = sqlite3.connect(str(db_path))
    try:
        body_status_counts = {
            str(status or "unset"): int(count)
            for status, count in conn.execute(
                "SELECT body_status, COUNT(*) FROM messages GROUP BY body_status"
            ).fetchall()
        }
        media_status_counts = {
            str(status or "unset"): int(count)
            for status, count in conn.execute(
                "SELECT media_status, COUNT(*) FROM messages GROUP BY media_status"
            ).fetchall()
        }
        metrics = {
            "messages": sqlite_scalar(conn, "SELECT COUNT(*) FROM messages"),
            "non_empty_text": sqlite_scalar(conn, "SELECT COUNT(*) FROM messages WHERE text IS NOT NULL AND TRIM(text) <> ''"),
            "null_or_blank_text": sqlite_scalar(conn, "SELECT COUNT(*) FROM messages WHERE text IS NULL OR TRIM(text) = ''"),
            "body_status_counts": body_status_counts,
            "missing_unexpected": body_status_counts.get("missing_unexpected", 0),
            "media_only_without_text": sqlite_scalar(
                conn,
                """
                SELECT COUNT(*) FROM messages
                WHERE body_status = 'media_only'
                """,
            ),
            "media_assets": sqlite_scalar(conn, "SELECT COUNT(*) FROM media_assets"),
            "media_status_counts": media_status_counts,
            "duplicate_msg_key_groups": sqlite_scalar(
                conn,
                """
                SELECT COUNT(*) FROM (
                    SELECT msg_key FROM messages
                    WHERE msg_key IS NOT NULL
                    GROUP BY msg_key HAVING COUNT(*) > 1
                )
                """,
            ),
            "provenance_rows": sqlite_scalar(
                conn,
                "SELECT COUNT(*) FROM messages WHERE source IS NOT NULL AND source_id IS NOT NULL",
            ),
            "store8_opaque_decrypted_messages": sqlite_scalar(
                conn,
                "SELECT COUNT(*) FROM messages WHERE store8_decryption_status = 'opaque_decrypted'",
            ),
            "store8_runtime_decoded_messages": sqlite_scalar(
                conn,
                "SELECT COUNT(*) FROM messages WHERE store8_decryption_status = 'runtime_store8_decoded'",
            ),
            "store8_opaque_unresolved_messages": sqlite_scalar(
                conn,
                "SELECT COUNT(*) FROM messages WHERE body_status = 'opaque_unresolved'",
            ),
            "store8_text_conflicts": sqlite_scalar(
                conn,
                "SELECT COUNT(*) FROM messages WHERE text_conflict_status IS NOT NULL",
            ),
            "contacts": sqlite_scalar(conn, "SELECT COUNT(*) FROM contacts"),
            "resolved_contacts": sqlite_scalar(conn, "SELECT COUNT(*) FROM contacts WHERE phone_number IS NOT NULL"),
            "chats": sqlite_scalar(conn, "SELECT COUNT(*) FROM chats"),
        }
        has_edit_columns = sqlite_column_exists(conn, "messages", "is_edited")
        has_message_edits = sqlite_table_exists(conn, "message_edits")
        metrics.update({
            "edited_message_markers": sqlite_scalar(
                conn,
                "SELECT COUNT(*) FROM messages WHERE COALESCE(is_edited, 0) = 1",
            ) if has_edit_columns else 0,
            "message_edit_protocol_events": sqlite_scalar(
                conn,
                "SELECT COUNT(DISTINCT edit_event_msg_key) FROM message_edits WHERE edit_event_msg_key IS NOT NULL",
            ) if has_message_edits else 0,
            "message_edit_protocol_folded": sqlite_scalar(
                conn,
                """
                SELECT COUNT(*)
                FROM message_edits
                WHERE source IN ('store8', 'runtime')
                """,
            ) if has_message_edits else 0,
            "message_edit_protocol_orphans": sqlite_scalar(
                conn,
                """
                SELECT COUNT(*)
                FROM messages
                WHERE source_recovery = 'store8_message_edit_orphan'
                """,
            ),
            "message_edit_variant_revisions": sqlite_scalar(
                conn,
                """
                SELECT COUNT(*)
                FROM message_edits
                WHERE source = 'same_msg_key_variant'
                """,
            ) if has_message_edits else 0,
            "replies_to_edited_messages": sqlite_scalar(
                conn,
                """
                SELECT COUNT(*)
                FROM messages AS q
                JOIN messages AS o
                  ON o.chat_jid = q.chat_jid
                 AND o.msg_id = q.quoted_stanza_id
                WHERE q.quoted_stanza_id IS NOT NULL
                  AND COALESCE(o.is_edited, 0) = 1
                """,
            ) if has_edit_columns else 0,
        })

        src_counter = source_text_counter(sqlite_messages)
        uni_counter = unified_text_counter(conn)
        media_counter = unified_media_filename_counter(conn)
        missing = []
        for key, count in src_counter.items():
            covered_as_text = uni_counter.get(key, 0)
            covered_as_media = media_counter.get(key, 0)
            deficit = count - max(covered_as_text, covered_as_media)
            if deficit > 0:
                missing.extend([key] * deficit)
        metrics.update({
            "source_messages": len(sqlite_messages),
            "source_non_empty_text": sum(1 for m in sqlite_messages if m.get('text') and str(m.get('text')).strip()),
            "missing_exact_text_keys": len(missing),
            "missing_exact_text_key_groups": len(set(missing)),
        })

        runtime_missing = []
        runtime_records = runtime_store8_supplement.get("records_by_msg_key") or {}
        runtime_summary = runtime_store8_supplement.get("summary") or {}
        runtime_warnings = runtime_summary.get("warnings") or []
        runtime_path = safe_str(runtime_summary.get("path"))
        runtime_enabled = bool(runtime_summary.get("enabled"))
        runtime_missing_file = bool(runtime_summary.get("missing_file"))
        if runtime_enabled and runtime_path and runtime_summary.get("missing_file") is not False and not os.path.exists(runtime_path):
            runtime_missing_file = True
        if not runtime_missing_file:
            runtime_missing_file = any(
                "file not found" in (safe_str(w.get("message") if isinstance(w, dict) else w) or "").lower()
                for w in runtime_warnings
            )
        metrics.update({
            "runtime_store8_supplement_enabled": 1 if runtime_enabled else 0,
            "runtime_store8_supplement_records": safe_int(runtime_summary.get("records")) or 0,
            "runtime_store8_supplement_records_with_text": safe_int(runtime_summary.get("records_with_text")) or 0,
            "runtime_store8_supplement_usable_records": safe_int(runtime_summary.get("usable_records")) or 0,
            "runtime_store8_supplement_parse_errors": safe_int(runtime_summary.get("parse_errors")) or 0,
            "runtime_store8_supplement_missing_file": 1 if runtime_missing_file else 0,
        })
        if runtime_records:
            for msg_key, record in runtime_records.items():
                expected = normalize_source_text_for_validation(runtime_supplement_text(record))
                if not expected:
                    continue
                row = conn.execute(
                    "SELECT text, store8_decrypted_text FROM messages WHERE msg_key = ? LIMIT 1",
                    (msg_key,),
                ).fetchone()
                actual_values = []
                if row:
                    actual_values = [
                        normalize_source_text_for_validation(row[0]),
                        normalize_source_text_for_validation(row[1]),
                    ]
                if expected not in actual_values:
                    runtime_missing.append({
                        "msg_key": msg_key,
                        "expected_sha256": sha256_bytes(expected.encode("utf-8", "replace")),
                        "actual_present": any(actual_values),
                    })
            metrics["runtime_text_keys_expected"] = sum(
                1 for record in runtime_records.values()
                if normalize_source_text_for_validation(runtime_supplement_text(record))
            )
            metrics["runtime_text_keys_missing_from_unified"] = len(runtime_missing)
        else:
            metrics["runtime_text_keys_expected"] = 0
            metrics["runtime_text_keys_missing_from_unified"] = 0

        status = "ok"
        errors = []
        warnings = []
        if metrics["duplicate_msg_key_groups"]:
            errors.append("duplicate_msg_key_groups")
        if metrics["missing_exact_text_keys"]:
            warnings.append("missing_exact_text_keys")
        if metrics["provenance_rows"] != metrics["messages"]:
            errors.append("provenance_gap")
        if metrics["missing_unexpected"]:
            errors.append("missing_unexpected")
        if metrics["runtime_text_keys_missing_from_unified"]:
            errors.append("runtime_text_keys_missing_from_unified")
        if metrics["runtime_store8_supplement_missing_file"]:
            errors.append("runtime_store8_supplement_missing_file")
        if metrics["runtime_store8_supplement_parse_errors"]:
            errors.append("runtime_store8_supplement_parse_errors")
        if errors:
            status = "error"

        return {
            "schema": "waren6.validation-report.v1",
            "status": status,
            "errors": errors,
            "warnings": warnings,
            "metrics": metrics,
            "missing_exact_text_samples": [
                {
                    "chat_jid": c,
                    "timestamp": t,
                    "text_sha256": sha256_bytes(
                        normalize_source_text_for_validation(text).encode("utf-8", "replace")
                    ),
                }
                for c, t, text in missing[:20]
            ],
            "runtime_text_missing_samples": runtime_missing[:20],
        }
    finally:
        conn.close()


def write_validation_report(path, db_path, sqlite_messages, idb_data,
                            runtime_seconds=None, runtime_store8_supplement=None,
                            media_index_report=None):
    report = validate_unified_database(
        db_path,
        sqlite_messages,
        runtime_store8_supplement=runtime_store8_supplement,
    )
    report["generated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    report["database"] = {
        "path": str(db_path),
        "size": os.path.getsize(db_path) if os.path.exists(db_path) else 0,
        "sha256": sha256_file(db_path) if os.path.exists(db_path) else None,
    }
    report["runtime"] = {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "runtime_seconds": runtime_seconds,
    }
    report["indexeddb_counts"] = {
        key: len(value) for key, value in sorted(idb_data.items()) if isinstance(value, list)
    }
    report["opaque_message_status"] = idb_data.get("_opaque_status", {})
    report["runtime_store8_supplement"] = idb_data.get("_runtime_store8_supplement", {})
    if media_index_report is not None:
        report["media_index"] = media_index_report
    report["store8_salt_hunt"] = idb_data.get("_store8_salt_hunt_report", {}).get("summary", {})
    report["events"] = EXTRACTION_EVENTS
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return report


def write_json_report(path, payload):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return path


def should_write_store8_debug_reports(args):
    return bool(
        getattr(args, "store8_debug", False)
        or getattr(args, "profile_store8_crypto", False)
        or getattr(args, "decrypt_store8_opaque", False)
        or getattr(args, "hunt_opaque_salt", False)
        or getattr(args, "opaque_salt_file", None)
        or getattr(args, "crypto_artifacts_report", None)
        or getattr(args, "store8_crypto_profile", None)
        or getattr(args, "store8_decryption_report", None)
        or getattr(args, "store8_salt_hunt_report", None)
    )


def should_write_media_index_report(with_media_index, media_index_report):
    return bool(with_media_index or media_index_report)


def report_timezone(timezone_name):
    if not timezone_name or timezone_name.lower() in ("local", "system"):
        return None
    if timezone_name.upper() == "UTC":
        return datetime.timezone.utc
    try:
        return ZoneInfo(timezone_name)
    except Exception:
        return None


def format_report_time(timestamp, timezone_name):
    ts = safe_int(timestamp)
    if not ts:
        return ""
    if ts > 9_999_999_999:
        ts = ts / 1000
    tz = report_timezone(timezone_name)
    dt = datetime.datetime.fromtimestamp(ts, tz=tz)
    return dt.strftime("%Y-%m-%d %I:%M %p")


def safe_filename(value, fallback="report"):
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip()).strip("._")
    return value[:120] or fallback


def load_report_rows(conn, chat_jid=None):
    params = []
    where = ""
    if chat_jid:
        where = "WHERE m.chat_jid = ?"
        params.append(chat_jid)
    sql = f"""
        SELECT
            m.rowid, m.chat_jid, COALESCE(m.chat_name, c.chat_name) AS chat_name,
            m.msg_id, m.msg_key, m.from_me, m.sender_jid, m.sender_phone,
            m.sender_name, m.timestamp, m.text, m.msg_type,
            m.media_mime_type, m.media_filename, m.media_size,
            m.media_case_path, m.media_sha256, m.media_status, m.body_status,
            m.source, m.source_id, m.source_chat_id, m.source_recovery
        FROM messages m
        LEFT JOIN chats c ON c.chat_jid = m.chat_jid
        {where}
        ORDER BY m.chat_jid, m.timestamp, m.rowid
    """
    cols = [
        "rowid", "chat_jid", "chat_name", "msg_id", "msg_key", "from_me",
        "sender_jid", "sender_phone", "sender_name", "timestamp", "text",
        "msg_type", "media_mime_type", "media_filename", "media_size",
        "media_case_path", "media_sha256", "media_status", "body_status",
        "source", "source_id", "source_chat_id", "source_recovery",
    ]
    return [dict(zip(cols, row)) for row in conn.execute(sql, params)]


def report_metadata(conn, db_path, timezone_name, tool_version, scope, filters):
    return {
        "schema": "waren6.report.v1",
        "tool": "WAren6",
        "tool_version": tool_version,
        "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "timezone": timezone_name or "local",
        "scope": scope,
        "filters": filters or {},
        "source_db": {
            "path": str(db_path),
            "size": os.path.getsize(db_path),
            "sha256": sha256_file(db_path),
        },
        "self_phone": sqlite_scalar(conn, "SELECT value FROM extraction_metadata WHERE key='self_phone'", default=None),
    }


def row_direction(row):
    if row.get("from_me") == 1:
        return "sent"
    if row.get("from_me") == 0:
        return "received"
    return "unknown"


def row_body(row):
    if row.get("text"):
        return str(row["text"])
    if row.get("body_status"):
        status = str(row["body_status"]).replace("_", " ")
        if status not in ("media only", "text present"):
            return f"[{status}]"
    media = row.get("media_filename") or row.get("media_mime_type") or row.get("msg_type") or "message"
    return f"[{media}]"


def write_html_report(path, title, metadata, rows, timezone_name):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("<!doctype html>\n<html><head><meta charset=\"utf-8\"><title>")
        f.write(html.escape(title))
        f.write("</title><style>")
        f.write("body{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#17202a}table{border-collapse:collapse;width:100%;font-size:12px}th,td{border:1px solid #ccd6dd;padding:6px;vertical-align:top}th{background:#eef3f7;text-align:left}.meta{color:#566573}.sent{background:#edf9f2}.received{background:#f8fbff}.unknown{background:#f7f7f7}")
        f.write("</style></head><body>")
        f.write(f"<h1>{html.escape(title)}</h1>")
        f.write(f"<p class=\"meta\">Exported by WAren6 {html.escape(str(metadata.get('tool_version')))} | Timezone: {html.escape(metadata.get('timezone') or 'local')} | Source SHA-256: {html.escape(metadata['source_db']['sha256'])}</p>")
        f.write("<table><thead><tr><th>Time</th><th>Chat</th><th>Direction</th><th>Sender</th><th>Message</th><th>Type</th><th>Body Status</th><th>Media</th><th>Source</th></tr></thead><tbody>")
        for row in rows:
            direction = row_direction(row)
            f.write(f"<tr class=\"{direction}\">")
            f.write(f"<td>{html.escape(format_report_time(row.get('timestamp'), timezone_name))}</td>")
            f.write(f"<td>{html.escape(row.get('chat_name') or row.get('chat_jid') or '')}</td>")
            f.write(f"<td>{direction}</td>")
            f.write(f"<td>{html.escape(row.get('sender_name') or row.get('sender_phone') or row.get('sender_jid') or '')}</td>")
            f.write(f"<td>{html.escape(row_body(row)).replace(chr(10), '<br>')}</td>")
            f.write(f"<td>{html.escape(row.get('msg_type') or '')}</td>")
            f.write(f"<td>{html.escape(row.get('body_status') or '')}</td>")
            media_bits = " | ".join(
                str(v) for v in (
                    row.get('media_case_path'),
                    row.get('media_sha256'),
                    row.get('media_status'),
                ) if v
            )
            f.write(f"<td>{html.escape(media_bits)}</td>")
            f.write(f"<td>{html.escape(row.get('source_recovery') or row.get('source') or '')}</td>")
            f.write("</tr>")
        f.write("</tbody></table></body></html>")


def write_delimited_report(path, rows, delimiter, timezone_name):
    fields = [
        "chat_jid", "msg_id", "msg_key", "display_time", "timestamp", "direction",
        "sender_jid", "sender_phone", "sender_name", "text", "msg_type",
        "body_status", "media_mime_type", "media_filename", "media_size",
        "media_case_path", "media_sha256", "media_status", "source",
        "source_id", "source_chat_id", "source_recovery",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter=delimiter, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            out = dict(row)
            out["display_time"] = format_report_time(row.get("timestamp"), timezone_name)
            out["direction"] = row_direction(row)
            writer.writerow(out)


def write_jsonl_report(path, rows, metadata, timezone_name):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(json.dumps({"type": "metadata", **metadata}, ensure_ascii=False) + "\n")
        for row in rows:
            out = dict(row)
            out["display_time"] = format_report_time(row.get("timestamp"), timezone_name)
            out["direction"] = row_direction(row)
            f.write(json.dumps(out, ensure_ascii=False) + "\n")


def pdf_escape(text):
    return str(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_simple_pdf(path, title, rows, metadata, timezone_name):
    lines = [
        title,
        f"WAren6 {metadata.get('tool_version')} | Timezone: {metadata.get('timezone')}",
        f"Source SHA-256: {metadata['source_db']['sha256']}",
        "",
    ]
    for row in rows:
        sender = row.get("sender_name") or row.get("sender_phone") or row.get("sender_jid") or ""
        line = f"{format_report_time(row.get('timestamp'), timezone_name)} | {row_direction(row)} | {sender} | {row_body(row)}"
        lines.append(line[:180])

    pages = [lines[i:i + 42] for i in range(0, len(lines), 42)] or [[]]
    objects = []
    page_ids = []
    next_id = 3
    for page in pages:
        content_lines = ["BT", "/F1 9 Tf", "40 770 Td", "12 TL"]
        for line in page:
            content_lines.append(f"({pdf_escape(line)}) Tj")
            content_lines.append("T*")
        content_lines.append("ET")
        stream = "\n".join(content_lines).encode("utf-8", "replace")
        content_id = next_id
        page_id = next_id + 1
        next_id += 2
        objects.append((content_id, b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"))
        objects.append((page_id, f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 1 0 R >> >> /Contents {content_id} 0 R >>".encode()))
        page_ids.append(page_id)
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    fixed_objects = [
        (1, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"),
        (2, f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode()),
        (next_id, b"<< /Type /Catalog /Pages 2 0 R >>"),
    ]
    all_objects = fixed_objects[:2] + objects + [fixed_objects[2]]
    root_id = next_id
    buf = bytearray(b"%PDF-1.4\n")
    offsets = {0: 0}
    for obj_id, body in sorted(all_objects, key=lambda item: item[0]):
        offsets[obj_id] = len(buf)
        buf.extend(f"{obj_id} 0 obj\n".encode())
        buf.extend(body)
        buf.extend(b"\nendobj\n")
    xref = len(buf)
    max_id = max(offsets)
    buf.extend(f"xref\n0 {max_id + 1}\n".encode())
    buf.extend(b"0000000000 65535 f \n")
    for obj_id in range(1, max_id + 1):
        buf.extend(f"{offsets.get(obj_id, 0):010d} 00000 n \n".encode())
    buf.extend(f"trailer << /Size {max_id + 1} /Root {root_id} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    with open(path, "wb") as f:
        f.write(buf)


def export_forensic_reports(db_path, output_dir, formats, timezone_name="local",
                            tool_version="1.0.0", scope="full", chat_jid=None):
    db_path = pathlib.Path(db_path)
    output_dir = pathlib.Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    formats = [fmt.lower() for fmt in formats]
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    outputs = {fmt: [] for fmt in formats}
    try:
        if scope == "per-chat" and not chat_jid:
            chats = [row[0] for row in conn.execute("SELECT chat_jid FROM chats ORDER BY chat_name, chat_jid")]
        else:
            chats = [chat_jid] if chat_jid else [None]

        manifest_files = []
        for current_chat in chats:
            rows = [dict(row) for row in load_report_rows(conn, current_chat)]
            if current_chat:
                chat_name = rows[0].get("chat_name") if rows else current_chat
                chat_hash = hashlib.sha256(current_chat.encode("utf-8")).hexdigest()[:10]
                stem = f"{safe_filename(chat_name or current_chat, 'chat')}_{chat_hash}"
                title = f"WAren6 Chat Report - {chat_name or current_chat}"
                filters = {"chat_jid": current_chat}
            else:
                stem = "full_case"
                title = "WAren6 Full Case Report"
                filters = {}

            metadata = report_metadata(conn, db_path, timezone_name, tool_version, scope, filters)
            metadata["message_count"] = len(rows)
            writers = {
                "html": lambda p: write_html_report(p, title, metadata, rows, timezone_name),
                "jsonl": lambda p: write_jsonl_report(p, rows, metadata, timezone_name),
                "csv": lambda p: write_delimited_report(p, rows, ",", timezone_name),
                "tsv": lambda p: write_delimited_report(p, rows, "\t", timezone_name),
                "pdf": lambda p: write_simple_pdf(p, title, rows, metadata, timezone_name),
            }
            for fmt in formats:
                if fmt not in writers:
                    continue
                path = output_dir / f"{stem}.{fmt}"
                writers[fmt](path)
                outputs[fmt].append(str(path))
                manifest_files.append({
                    "path": str(path),
                    "format": fmt,
                    "size": path.stat().st_size,
                    "sha256": sha256_file(path),
                })

        manifest = {
            "schema": "waren6.report-manifest.v1",
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "timezone": timezone_name,
            "source_db": str(db_path),
            "files": manifest_files,
        }
        manifest_path = output_dir / "report_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        return outputs
    finally:
        conn.close()


def write_report_manifest(manifest_path, db_path, timezone_name, report_outputs):
    files = []
    for fmt, paths in sorted(report_outputs.items()):
        for report_path in paths:
            path = pathlib.Path(report_path)
            files.append({
                "path": str(path),
                "format": fmt,
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            })
    manifest = {
        "schema": "waren6.report-manifest.v1",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "timezone": timezone_name,
        "source_db": str(db_path),
        "files": files,
    }
    manifest_path = pathlib.Path(manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    return manifest


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="WhatsApp Desktop Unified Database Extractor"
    )
    parser.add_argument(
        '--unify',
        help='Build unified_whatsapp.db from a WAren6 case folder or WAren6_<timestamp> archive')
    parser.add_argument(
        '--reports-only',
        help='Generate reports from an existing unified_whatsapp.db without reading source evidence')
    parser.add_argument(
        '--idb-path',
        help='Path to EBWebView Default profile (containing IndexedDB/)')
    parser.add_argument(
        '--decrypted-dir',
        help='Path to WAren6 output directory (containing *.dec.db files)')
    parser.add_argument(
        '--output',
        help='Output path for the unified SQLite database')
    parser.add_argument(
        '--validation-report',
        help='Optional path for WAren6 validation_report.json')
    parser.add_argument(
        '--reports-dir',
        help='Optional directory for forensic report exports')
    parser.add_argument(
        '--report-formats',
        default='html,jsonl,csv,tsv,pdf',
        help='Comma-separated forensic report formats: html,jsonl,csv,tsv,pdf')
    parser.add_argument(
        '--report-timezone',
        default='local',
        help='Timezone used in generated reports, e.g. local, UTC, Asia/Kolkata')
    parser.add_argument(
        '--report-scope',
        choices=['full', 'per-chat', 'all'],
        default='all',
        help='Generate full-case reports, per-chat reports, or both')
    parser.add_argument(
        '--tool-version',
        default='1.0.0',
        help='WAren6 version recorded in reports')
    parser.add_argument(
        '--no-progress',
        action='store_true',
        help='Disable terminal progress bars for captured/logged runs')
    parser.add_argument(
        '--verbose-console',
        action='store_true',
        help='Print detailed merge/enrichment counters during unification')
    parser.add_argument(
        '--profile-store8-crypto',
        action='store_true',
        help='Profile IndexedDB Store 8 opaque crypto artifacts and write JSON reports')
    parser.add_argument(
        '--store8-debug',
        action='store_true',
        help='Write Store 8 opaque crypto diagnostic JSON reports')
    parser.add_argument(
        '--decrypt-store8-opaque',
        action='store_true',
        help='Attempt offline Store 8 msgRowOpaqueData decryption using copied artifacts and optional salt file')
    parser.add_argument(
        '--opaque-salt-file',
        help='Examiner-supplied WebWA Store 8 network salt file (hex/base64/plain JSON)')
    parser.add_argument(
        '--crypto-artifacts-report',
        help='Output path for opaque_crypto_artifacts.json')
    parser.add_argument(
        '--store8-crypto-profile',
        help='Output path for store8_crypto_profile.json')
    parser.add_argument(
        '--store8-decryption-report',
        help='Output path for store8_decryption_report.json')
    parser.add_argument(
        '--hunt-opaque-salt',
        action='store_true',
        help='Scan copied offline artifacts for Store 8 network-salt candidates and validate them by decryption')
    parser.add_argument(
        '--opaque-artifact-path',
        action='append',
        default=[],
        help='Additional file or directory to scan for Store 8 network-salt candidates; repeatable')
    parser.add_argument(
        '--store8-salt-hunt-report',
        help='Output path for store8_salt_hunt_report.json')
    parser.add_argument(
        '--fast-salt-hunt',
        action='store_true',
        help=('Opt-in early exit for the salt hunter: stop scanning once >=3 '
              'validated candidates found AND 32 consecutive files produced no new hits. '
              'Default is exhaustive (multi-salt cases exist: WA reinstall, salt rotation).'))
    parser.add_argument(
        '--runtime-store8-jsonl',
        help='Live-runtime Store 8 JSONL supplement produced by tools/wa_live_runtime_capture.js')
    parser.add_argument(
        '--with-media-index',
        action='store_true',
        help='Index/hash local media files already present in the case folder')
    parser.add_argument(
        '--media-index-report',
        help='Output path for media_index_report.json')
    parser.add_argument(
        '--media-only',
        help=('Skip full unification and only run media indexing against an existing '
              'unified_whatsapp.db at this path. Enables deferring media hashing off '
              'the target to a more powerful machine after the archive transfer.'))
    parser.add_argument(
        '--profile',
        action='store_true',
        help=('Emit per-stage wall-clock timings into WAren6.manifest.json (unify_profile '
              'section) and also write unify_profile.json alongside the output DB.'))

    args = parser.parse_args()
    global PROGRESS_ENABLED, VERBOSE_CONSOLE
    PROGRESS_ENABLED = not args.no_progress
    VERBOSE_CONSOLE = bool(args.verbose_console)

    if args.reports_only:
        if not args.reports_dir:
            parser.error("--reports-dir is required with --reports-only")
        formats = [fmt.strip() for fmt in args.report_formats.split(',') if fmt.strip()]
        report_outputs = {fmt: [] for fmt in formats}
        if args.report_scope in ("full", "all"):
            outputs = export_forensic_reports(
                db_path=args.reports_only,
                output_dir=args.reports_dir,
                formats=formats,
                timezone_name=args.report_timezone,
                tool_version=args.tool_version,
                scope="full",
            )
            for fmt, paths in outputs.items():
                report_outputs.setdefault(fmt, []).extend(paths)
        if args.report_scope in ("per-chat", "all"):
            outputs = export_forensic_reports(
                db_path=args.reports_only,
                output_dir=pathlib.Path(args.reports_dir) / "chats",
                formats=formats,
                timezone_name=args.report_timezone,
                tool_version=args.tool_version,
                scope="per-chat",
            )
            for fmt, paths in outputs.items():
                report_outputs.setdefault(fmt, []).extend(paths)
        write_report_manifest(
            pathlib.Path(args.reports_dir) / "report_manifest.json",
            args.reports_only,
            args.report_timezone,
            report_outputs,
        )
        print(f"[OK] Forensic reports generated in {args.reports_dir}")
        return

    unify_case = None
    if args.unify:
        try:
            unify_case = prepare_unify_case(args.unify, args.output)
        except Exception as exc:
            parser.error(str(exc))
        idb_path = unify_case["idb_path"]
        decrypted_dir = unify_case["decrypted_dir"]
        output = str(unify_case["output"])
        if not args.validation_report:
            args.validation_report = str(pathlib.Path(output).with_name("validation_report.json"))
        if args.with_media_index and not args.media_index_report:
            args.media_index_report = str(pathlib.Path(output).with_name("media_index_report.json"))
    else:
        if not args.idb_path:
            parser.error("--idb-path is required unless --unify or --reports-only is used")
        idb_path = pathlib.Path(args.idb_path)
        decrypted_dir = pathlib.Path(args.decrypted_dir) if args.decrypted_dir else None
        output = args.output

    if not args.profile_store8_crypto and (not decrypted_dir or not output):
        parser.error("--decrypted-dir and --output are required unless --profile-store8-crypto is used")

    default_report_dir = decrypted_dir or pathlib.Path.cwd()
    write_store8_debug = should_write_store8_debug_reports(args)
    crypto_artifacts_report = args.crypto_artifacts_report or str(default_report_dir / "opaque_crypto_artifacts.json")
    store8_crypto_profile = args.store8_crypto_profile or str(default_report_dir / "store8_crypto_profile.json")
    store8_decryption_report = args.store8_decryption_report or str(default_report_dir / "store8_decryption_report.json")
    store8_salt_hunt_report = args.store8_salt_hunt_report or str(default_report_dir / "store8_salt_hunt_report.json")
    write_media_index_report = should_write_media_index_report(args.with_media_index, args.media_index_report)
    media_index_report_path = args.media_index_report or str(default_report_dir / "media_index_report.json")

    print("")
    print("+------------------------------------------------------------+")
    print("|        WAren6 WhatsApp Forensic Data Extractor             |")
    print("+------------------------------------------------------------+")

    # --profile: collect per-stage perf_counter timings. Uses perf_counter (monotonic)
    # rather than time.time so backwards clock adjustments during acquisition don't
    # skew the profile.
    stage_profile = [] if args.profile else None

    def _record_stage(name, wall_seconds, extra=None):
        if stage_profile is None:
            return
        entry = {"stage": name, "seconds": round(float(wall_seconds), 4)}
        if extra:
            entry.update(extra)
        stage_profile.append(entry)

    overall_start = time.time()
    overall_perf_start = time.perf_counter()

    # --media-only: run only media indexing against an existing unified_whatsapp.db.
    # Enables deferring the ~30-120s media hashing pass off the target to a faster
    # workstation after the .tar.zst archive transfer.
    if args.media_only:
        media_only_db = pathlib.Path(args.media_only)
        if not media_only_db.exists():
            parser.error(f"--media-only DB not found: {media_only_db}")
        media_only_case_root = pathlib.Path(args.decrypted_dir) if args.decrypted_dir else media_only_db.parent
        print(f"\n[1/1] Media-only indexing against {media_only_db}...")
        t_media_only = time.perf_counter()
        media_index_report = index_local_media_assets(
            str(media_only_db),
            media_only_case_root,
            enabled=True,
        )
        _record_stage("media_only_index", time.perf_counter() - t_media_only,
                      {"messages_linked": media_index_report.get("messages_with_local_media", 0)})
        if args.media_index_report or write_media_index_report:
            report_path = args.media_index_report or str(media_only_db.with_name("media_index_report.json"))
            write_json_report(report_path, media_index_report)
            print(f"  [OK] Media index report: {report_path}")
        print(
            "  Media index: "
            f"{media_index_report.get('messages_with_local_media', 0)} messages linked, "
            f"{media_index_report.get('messages_missing_local_media', 0)} missing local files"
        )
        if stage_profile is not None:
            profile_path = media_only_db.with_name("unify_profile.json")
            write_json_report(str(profile_path), {
                "schema": "waren6.unify-profile.v1",
                "mode": "media-only",
                "overall_seconds": round(time.perf_counter() - overall_perf_start, 4),
                "stages": stage_profile,
            })
            print(f"  [OK] Unify profile: {profile_path}")
        print("\n[1/1] Media-only pass complete.")
        return

    # 1. Extract IndexedDB
    print("\n[1/5] Extracting IndexedDB data...")
    t0 = time.time()
    t_perf = time.perf_counter()
    idb_data = extract_indexeddb(
        idb_path,
        opaque_salt_file=args.opaque_salt_file,
        decrypt_store8_opaque=args.decrypt_store8_opaque,
        hunt_opaque_salt=args.hunt_opaque_salt,
        opaque_artifact_paths=args.opaque_artifact_path,
        fast_salt_hunt=args.fast_salt_hunt,
    )
    _record_stage("extract_indexeddb", time.perf_counter() - t_perf)
    if idb_data and write_store8_debug:
        write_json_report(crypto_artifacts_report, idb_data.get("_opaque_crypto_artifacts", {}))
        write_json_report(store8_crypto_profile, idb_data.get("_store8_crypto_profile", {}))
        write_json_report(store8_decryption_report, idb_data.get("_store8_decryption_report", {}))
        write_json_report(store8_salt_hunt_report, idb_data.get("_store8_salt_hunt_report", {}))
        if args.profile_store8_crypto:
            print(f"  [OK] Opaque crypto artifacts: {crypto_artifacts_report}")
            print(f"  [OK] Store 8 crypto profile: {store8_crypto_profile}")
            print(f"  [OK] Store 8 decryption report: {store8_decryption_report}")
            if args.hunt_opaque_salt:
                print(f"  [OK] Store 8 salt hunt report: {store8_salt_hunt_report}")
    print(f"  [OK] IndexedDB data extracted in {time.time() - t0:.1f}s")

    if args.profile_store8_crypto and (not decrypted_dir or not output):
        print("\n[2/2] Store 8 crypto profiling complete.")
        cleanup_prepared_unify_case(unify_case, success=True)
        return

    runtime_store8_supplement = load_runtime_store8_supplement(args.runtime_store8_jsonl)
    if runtime_store8_supplement.get("summary", {}).get("enabled"):
        summary = runtime_store8_supplement["summary"]
        idb_data["_runtime_store8_supplement"] = summary
        print(
            "  Runtime Store 8 supplement: "
            f"{summary.get('usable_records', 0)} usable records from {summary.get('records', 0)} JSONL rows"
        )
    else:
        idb_data["_runtime_store8_supplement"] = runtime_store8_supplement.get("summary", {})

    # 2. Load decrypted SQLite messages
    print("\n[2/5] Loading decrypted SQLite messages...")
    t0 = time.time()
    t_perf = time.perf_counter()
    sqlite_messages = load_decrypted_messages(decrypted_dir)
    sqlite_contacts = load_decrypted_contacts(decrypted_dir)
    _record_stage("load_decrypted_sqlite", time.perf_counter() - t_perf,
                  {"messages": len(sqlite_messages), "contacts": len(sqlite_contacts)})
    print(f"  [OK] Decrypted SQLite data loaded in {time.time() - t0:.1f}s")

    # 3. Build LID resolver
    print("\n[3/5] Building LID resolver...")
    t0 = time.time()
    t_perf = time.perf_counter()
    lid_to_phone, lid_to_name, phone_to_name = build_lid_resolver(
        idb_data.get('contact', []),
        sqlite_contacts
    )
    _record_stage("build_lid_resolver", time.perf_counter() - t_perf)
    print(f"  [OK] LID resolver built in {time.time() - t0:.1f}s")

    # 4. Build unified database
    print("\n[4/5] Building unified database...")
    t0 = time.time()
    t_perf = time.perf_counter()
    stats = build_unified_db(
        output, idb_data, sqlite_messages,
        lid_to_phone, lid_to_name, phone_to_name,
        str(idb_path), str(decrypted_dir),
        runtime_store8_supplement=runtime_store8_supplement,
    )
    _record_stage("build_unified_db", time.perf_counter() - t_perf)
    if args.with_media_index:
        print("  [>] Indexing local media files; this hashes copied evidence media...")
    t_perf = time.perf_counter()
    media_index_report = index_local_media_assets(
        output,
        decrypted_dir,
        enabled=args.with_media_index,
    )
    _record_stage("media_index", time.perf_counter() - t_perf,
                  {"enabled": bool(args.with_media_index),
                   "messages_linked": media_index_report.get("messages_with_local_media", 0)})
    if write_media_index_report:
        write_json_report(media_index_report_path, media_index_report)
    if args.with_media_index:
        print(
            "  Media index: "
            f"{media_index_report.get('messages_with_local_media', 0)} messages linked, "
            f"{media_index_report.get('messages_missing_local_media', 0)} missing local files"
        )
    print(f"  [OK] Unified database built in {time.time() - t0:.1f}s")

    validation_report = None
    if args.validation_report:
        validation_report = write_validation_report(
            args.validation_report,
            output,
            sqlite_messages,
            idb_data,
            runtime_seconds=time.time() - overall_start,
            runtime_store8_supplement=runtime_store8_supplement,
            media_index_report=media_index_report,
        )
        print(f"  [OK] Validation report: {args.validation_report}")

    if args.reports_dir:
        formats = [fmt.strip() for fmt in args.report_formats.split(',') if fmt.strip()]
        exported_count = 0
        aggregate_report_outputs = {fmt: [] for fmt in formats}
        if args.report_scope in ('full', 'all'):
            report_outputs = export_forensic_reports(
                db_path=output,
                output_dir=args.reports_dir,
                formats=formats,
                timezone_name=args.report_timezone,
                tool_version=args.tool_version,
                scope="full",
            )
            exported_count += sum(len(paths) for paths in report_outputs.values())
            for fmt, paths in report_outputs.items():
                aggregate_report_outputs.setdefault(fmt, []).extend(paths)
        if args.report_scope in ('per-chat', 'all'):
            report_outputs = export_forensic_reports(
                db_path=output,
                output_dir=pathlib.Path(args.reports_dir) / "chats",
                formats=formats,
                timezone_name=args.report_timezone,
                tool_version=args.tool_version,
                scope="per-chat",
            )
            exported_count += sum(len(paths) for paths in report_outputs.values())
            for fmt, paths in report_outputs.items():
                aggregate_report_outputs.setdefault(fmt, []).extend(paths)
        write_report_manifest(
            pathlib.Path(args.reports_dir) / "report_manifest.json",
            output,
            args.report_timezone,
            aggregate_report_outputs,
        )
        print(f"  [OK] Forensic reports generated: {exported_count} files in {args.reports_dir}")

    # 5. Summary
    overall_time = time.time() - overall_start
    if stage_profile is not None:
        profile_output = pathlib.Path(output).with_name("unify_profile.json")
        write_json_report(str(profile_output), {
            "schema": "waren6.unify-profile.v1",
            "mode": "unify" if args.unify else "extract",
            "output_db": str(output),
            "overall_seconds": round(time.perf_counter() - overall_perf_start, 4),
            "wallclock_seconds": round(overall_time, 4),
            "stages": stage_profile,
        })
        print(f"  [OK] Unify profile: {profile_output}")
    print("\n[5/5] Done!")
    print("\n+------------------------------------------------------------+")
    print("|                    EXTRACTION SUMMARY                      |")
    print("+------------------------------------------------------------+")
    print(f"  Output Database:      {output}")
    print(f"  Messages Total:       {stats['messages']:,}")
    print(f"  Messages w/ Dir:      {stats['enriched']:,}")
    print(f"    > Sent:             {stats['sent']:,}")
    print(f"    > Received:         {stats['received']:,}")
    print(f"  Contacts Total:       {stats['contacts']:,}")
    print(f"  Contacts w/ Phone:    {stats['resolved']:,}")
    print(f"  Chats:                {stats['chats']:,}")
    print(f"  Reactions:            {stats['reactions']:,}")
    print(f"  Total Time:           {overall_time:.1f} seconds")
    print("+------------------------------------------------------------+")
    print("\nThis database is fully self-contained. Open it with any SQLite tool:")
    print(f"  sqlite3 {output}")
    print(f"  DB Browser for SQLite -> {output}")
    print(f"  python -c \"import sqlite3; ...\"")
    cleanup_prepared_unify_case(unify_case, success=True)


if __name__ == '__main__':
    main()
