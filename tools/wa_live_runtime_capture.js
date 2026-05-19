#!/usr/bin/env node
/*
 * WAren6 live runtime Store 8 capture.
 *
 * This is a research/supplement path, not the default offline forensic path.
 * It attaches to a local WebView2 DevTools endpoint and asks the running
 * WhatsApp runtime to serialize Store 8 message rows using its loaded code.
 *
 * No external npm packages are required. Requires a recent Node.js with
 * global fetch and WebSocket support.
 */

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const VERSION = "1.0.0";

function usage(exitCode = 0) {
  const text = `
Usage:
  node tools/wa_live_runtime_capture.js --out live-runtime-research/runtime_store8_messages.jsonl

Options:
  --port <port>        DevTools port. Default: 9222
  --host <host>        DevTools host. Default: 127.0.0.1
  --out <path>         JSONL output path. Required
  --summary <path>     Summary JSON output path. Default: <out>.summary.json
  --limit <n>          Capture at most n rows. Default: all rows
  --hash-only          Do not write body/caption text, only hashes and lengths
  --help               Show this help

Before running, WhatsApp WebView2 must be started with a local DevTools port,
for example by temporarily setting WebView2 AdditionalBrowserArguments to:
  --remote-debugging-port=9222 --remote-debugging-address=127.0.0.1
`;
  process.stderr.write(text.trimStart());
  process.exit(exitCode);
}

function parseArgs(argv) {
  const args = {
    host: "127.0.0.1",
    port: 9222,
    out: null,
    summary: null,
    limit: null,
    hashOnly: false,
  };
  for (let i = 2; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--help" || arg === "-h") usage(0);
    if (arg === "--hash-only") {
      args.hashOnly = true;
      continue;
    }
    const next = argv[i + 1];
    if (!next || next.startsWith("--")) {
      throw new Error(`Missing value for ${arg}`);
    }
    i += 1;
    if (arg === "--host") args.host = next;
    else if (arg === "--port") args.port = Number(next);
    else if (arg === "--out") args.out = next;
    else if (arg === "--summary") args.summary = next;
    else if (arg === "--limit") args.limit = Number(next);
    else throw new Error(`Unknown argument: ${arg}`);
  }
  if (!args.out) throw new Error("--out is required");
  if (!Number.isInteger(args.port) || args.port <= 0) throw new Error("--port must be a positive integer");
  if (args.limit != null && (!Number.isInteger(args.limit) || args.limit <= 0)) {
    throw new Error("--limit must be a positive integer");
  }
  if (!args.summary) args.summary = `${args.out}.summary.json`;
  return args;
}

function sha256String(value) {
  return crypto.createHash("sha256").update(String(value ?? ""), "utf8").digest("hex");
}

function sha256File(filePath) {
  const hash = crypto.createHash("sha256");
  hash.update(fs.readFileSync(filePath));
  return hash.digest("hex");
}

async function getJson(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} returned HTTP ${res.status}`);
  return res.json();
}

async function connectWebSocket(wsUrl) {
  const ws = new WebSocket(wsUrl);
  let nextId = 1;
  const pending = new Map();

  ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) reject(new Error(JSON.stringify(message.error)));
      else resolve(message.result);
    }
  };

  await new Promise((resolve, reject) => {
    ws.onopen = resolve;
    ws.onerror = reject;
    setTimeout(() => reject(new Error("Timed out while connecting to DevTools WebSocket")), 10000);
  });

  return {
    call(method, params = {}, timeoutMs = 120000) {
      const id = nextId;
      nextId += 1;
      ws.send(JSON.stringify({ id, method, params }));
      return new Promise((resolve, reject) => {
        pending.set(id, { resolve, reject });
        setTimeout(() => {
          if (pending.has(id)) {
            pending.delete(id);
            reject(new Error(`${method} timed out`));
          }
        }, timeoutMs);
      });
    },
    close() {
      ws.close();
    },
  };
}

function buildRuntimeExpression(limit) {
  const limitLiteral = limit == null ? "null" : String(limit);
  return `(async () => {
    const table = require("WAWebSchemaMessage").getMessageTable();
    const serializer = require("WAWebDBMessageSerialization");
    const rows = await table.all();
    const limit = ${limitLiteral};
    const selected = limit == null ? rows : rows.slice(0, limit);

    function asString(value) {
      if (value == null) return null;
      if (typeof value === "string") return value;
      if (typeof value === "number" || typeof value === "boolean") return String(value);
      try { return value.toString(); } catch (err) { return null; }
    }

    function cleanText(value) {
      const text = asString(value);
      return text && text.length ? text : null;
    }

    function opaqueLength(value) {
      if (!value) return null;
      return value.byteLength || value.length || null;
    }

    const messages = [];
    const byType = {};
    let withText = 0;
    let serializerErrors = 0;

    for (const row of selected) {
      let msg = null;
      try {
        msg = serializer.messageFromDbRow(row);
      } catch (err) {
        serializerErrors += 1;
        msg = {};
      }

      const msgKey = asString(row.id || (msg && msg.id));
      const body = cleanText(msg && msg.body);
      const caption = cleanText(msg && msg.caption);
      const title = cleanText(msg && msg.title);
      const description = cleanText(msg && msg.description);
      const matchedText = cleanText(msg && msg.matchedText);
      const text = body || caption || title || description || matchedText;
      if (text) withText += 1;

      const msgType = asString((msg && msg.type) || row.type);
      byType[msgType || "unknown"] = (byType[msgType || "unknown"] || 0) + 1;

      messages.push({
        schema: "waren6.live-runtime-store8-message.v1",
        source: "whatsapp_webview2_runtime",
        msg_key: msgKey,
        timestamp: row.t ?? (msg && msg.t) ?? null,
        row_id: row.rowId ?? null,
        type: msgType,
        subtype: asString((msg && msg.subtype) || row.subtype),
        from_me: msgKey ? msgKey.startsWith("true_") : null,
        chat_jid: asString((msg && msg.to) || row.to || (msg && msg.from) || row.from),
        sender_jid: asString((msg && msg.author) || row.author || row.sender),
        body,
        caption,
        title,
        description,
        matched_text: matchedText,
        filename: cleanText((msg && msg.filename) || row.filename),
        mimetype: cleanText((msg && msg.mimetype) || row.mimetype),
        media_key: cleanText(row.mediaKey || (msg && msg.mediaKey)),
        media_key_timestamp: row.mediaKeyTimestamp ?? (msg && msg.mediaKeyTimestamp) ?? null,
        filehash: cleanText(row.filehash || (msg && msg.filehash)),
        enc_filehash: cleanText(row.encFilehash || (msg && msg.encFilehash)),
        static_url: cleanText(row.staticUrl || (msg && msg.staticUrl)),
        direct_path: cleanText(row.directPath || (msg && msg.directPath)),
        deprecated_mms3_url: cleanText(row.deprecatedMms3Url || (msg && msg.deprecatedMms3Url)),
        thumbnail_direct_path: cleanText(row.thumbnailDirectPath || (msg && msg.thumbnailDirectPath)),
        thumbnail_sha256: cleanText(row.thumbnailSha256 || (msg && msg.thumbnailSha256)),
        thumbnail_enc_sha256: cleanText(row.thumbnailEncSha256 || (msg && msg.thumbnailEncSha256)),
        media_size: row.size ?? (msg && msg.size) ?? null,
        duration: row.duration ?? (msg && msg.duration) ?? null,
        width: row.width ?? (msg && msg.width) ?? null,
        height: row.height ?? (msg && msg.height) ?? null,
        opaque_byte_length: opaqueLength(row.msgRowOpaqueData),
        serializer_recovered_text: Boolean(text),
      });
    }

    return {
      schema: "waren6.live-runtime-store8-capture.v1",
      capture_version: "${VERSION}",
      href: location.href,
      title: document.title,
      total_store8_rows: rows.length,
      captured_rows: messages.length,
      rows_with_text: withText,
      rows_without_text: messages.length - withText,
      serializer_errors: serializerErrors,
      by_type: byType,
      messages,
    };
  })()`;
}

async function main() {
  const args = parseArgs(process.argv);
  const baseUrl = `http://${args.host}:${args.port}`;
  const targets = await getJson(`${baseUrl}/json/list`);
  const page = targets.find((target) => target.type === "page" && /web\\.whatsapp\\.com/.test(target.url))
    || targets.find((target) => target.type === "page");
  if (!page) throw new Error("No WebView2 page target found on the DevTools endpoint");

  const cdp = await connectWebSocket(page.webSocketDebuggerUrl);
  try {
    await cdp.call("Runtime.enable");
    const result = await cdp.call(
      "Runtime.evaluate",
      {
        expression: buildRuntimeExpression(args.limit),
        awaitPromise: true,
        returnByValue: true,
      },
      180000,
    );

    const payload = result.result && result.result.value;
    if (!payload || !Array.isArray(payload.messages)) {
      throw new Error("Runtime did not return a Store 8 message payload");
    }

    const outPath = path.resolve(args.out);
    const summaryPath = path.resolve(args.summary);
    fs.mkdirSync(path.dirname(outPath), { recursive: true });
    fs.mkdirSync(path.dirname(summaryPath), { recursive: true });

    const stream = fs.createWriteStream(outPath, { encoding: "utf8" });
    let bodyRows = 0;
    let captionRows = 0;
    for (const message of payload.messages) {
      const body = message.body || "";
      const caption = message.caption || "";
      if (body) bodyRows += 1;
      if (caption) captionRows += 1;
      message.body_sha256 = body ? sha256String(body) : null;
      message.caption_sha256 = caption ? sha256String(caption) : null;
      message.text_length = (body || caption || message.title || message.description || message.matched_text || "").length;
      if (args.hashOnly) {
        delete message.body;
        delete message.caption;
        delete message.title;
        delete message.description;
        delete message.matched_text;
      }
      stream.write(`${JSON.stringify(message)}\n`);
    }
    await new Promise((resolve, reject) => {
      stream.end(resolve);
      stream.on("error", reject);
    });

    const summary = {
      schema: "waren6.live-runtime-store8-summary.v1",
      capture_version: VERSION,
      captured_at: new Date().toISOString(),
      target_url: payload.href,
      target_title: payload.title,
      total_store8_rows: payload.total_store8_rows,
      captured_rows: payload.captured_rows,
      rows_with_text: payload.rows_with_text,
      rows_without_text: payload.rows_without_text,
      body_rows: bodyRows,
      caption_rows: captionRows,
      serializer_errors: payload.serializer_errors,
      by_type: payload.by_type,
      hash_only: args.hashOnly,
      output_jsonl: outPath,
      output_jsonl_sha256: sha256File(outPath),
    };
    fs.writeFileSync(summaryPath, JSON.stringify(summary, null, 2), "utf8");

    process.stdout.write(JSON.stringify({
      output_jsonl: outPath,
      summary_json: summaryPath,
      total_store8_rows: summary.total_store8_rows,
      captured_rows: summary.captured_rows,
      rows_with_text: summary.rows_with_text,
      rows_without_text: summary.rows_without_text,
      output_jsonl_sha256: summary.output_jsonl_sha256,
    }, null, 2));
    process.stdout.write("\n");
  } finally {
    cdp.close();
  }
}

main().catch((err) => {
  process.stderr.write(`ERROR: ${err.stack || err.message}\n`);
  process.exit(1);
});
