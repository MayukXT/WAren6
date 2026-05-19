function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function editHistoryStatusText(status) {
    if (status === 'marker_only') {
        return 'WhatsApp marked this message as edited, but edit history was not present in the extracted evidence.';
    }
    if (status === 'event_only_orphan') {
        return 'This message was recovered from a WhatsApp edit event because the original target row was not present.';
    }
    if (status === 'variant_history') {
        return 'Multiple text variants with the same WhatsApp message key were preserved as revisions.';
    }
    return 'Edit evidence recovered from WhatsApp Store 8.';
}

export function renderEditedMarker(msg = {}) {
    if (!msg?.is_edited) return '';
    const key = msg.msg_key ? ` data-message-edit-key="${escapeHtml(msg.msg_key)}"` : '';
    const button = msg.msg_key
        ? `<button class="msg-edit-info-btn" type="button"${key} title="View edit evidence" aria-label="View edit evidence">i</button>`
        : '';
    return `<span class="msg-edited-label">Edited</span>${button}`;
}

function renderRevision(edit, formatTime) {
    const when = edit?.edited_at ? formatTime(edit.edited_at) : 'Time not present';
    const actor = edit?.editor_name || edit?.editor_phone || edit?.editor_jid || 'Unknown editor';
    const previous = edit?.previous_text
        ? `<div class="message-edit-text"><span>Previous</span><p>${escapeHtml(edit.previous_text)}</p></div>`
        : '';
    const current = edit?.new_text
        ? `<div class="message-edit-text"><span>New</span><p>${escapeHtml(edit.new_text)}</p></div>`
        : '<div class="message-edit-text muted">New text was not present in extracted evidence.</div>';
    return `
        <div class="message-edit-row">
            <div class="message-edit-row-head">
                <strong>Revision ${Number(edit?.edit_index || 0) || ''}</strong>
                <span>${escapeHtml(when)}</span>
            </div>
            <div class="message-edit-actor">${escapeHtml(actor)}</div>
            ${previous}
            ${current}
        </div>
    `;
}

function renderQuoteSnapshots(snapshots, formatTime) {
    if (!Array.isArray(snapshots) || snapshots.length === 0) return '';
    return `
        <div class="message-edit-section">
            <h3>Quote snapshots</h3>
            ${snapshots.map(snapshot => `
                <div class="message-edit-quote">
                    <span>${escapeHtml(snapshot?.timestamp ? formatTime(snapshot.timestamp) : 'Time not present')}</span>
                    <p>${escapeHtml(snapshot?.quoted_msg_body || '')}</p>
                </div>
            `).join('')}
        </div>
    `;
}

export function renderEditHistoryContent(history = {}, { formatTime } = {}) {
    const timeFormatter = typeof formatTime === 'function' ? formatTime : value => String(value ?? '');
    const edits = Array.isArray(history?.edits) ? history.edits : [];
    const snapshots = Array.isArray(history?.quote_snapshots) ? history.quote_snapshots : [];
    const status = history?.history_status || (edits.length ? 'event_history' : 'marker_only');

    const rows = edits.length
        ? `<div class="message-edit-list">${edits.map(edit => renderRevision(edit, timeFormatter)).join('')}</div>`
        : `<div class="message-info-empty">${escapeHtml(editHistoryStatusText(status))}</div>`;

    return `
        <div class="message-edit-summary">${escapeHtml(editHistoryStatusText(status))}</div>
        ${rows}
        ${renderQuoteSnapshots(snapshots, timeFormatter)}
    `;
}
