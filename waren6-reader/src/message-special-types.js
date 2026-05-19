function escapeHtml(value) {
    return String(value || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

const SPECIAL_TYPES = {
    poll_creation: { title: 'Poll', icon: 'Poll' },
    pinned_message: { title: 'Pinned message', icon: 'Pin' },
    vcard: { title: 'Contact card', icon: 'Contact' },
    location: { title: 'Location', icon: 'Location' },
    interactive: { title: 'Interactive message', icon: 'Interactive' },
    rich_response: { title: 'Rich response', icon: 'Rich' },
    ptv: { title: 'Video note', icon: 'Video' },
};

export function specialMessageMeta(msg) {
    const type = String(msg?.msg_type || '').toLowerCase();
    return SPECIAL_TYPES[type] || null;
}

export function renderSpecialMessageContent(msg) {
    const meta = specialMessageMeta(msg);
    if (!meta) return '';

    const detail = String(msg?.text || msg?.media_filename || msg?.msg_type || '').trim();
    return `
        <div class="msg-special-card" data-special-type="${escapeHtml(String(msg?.msg_type || 'unknown').toLowerCase())}">
            <span class="msg-special-icon">${escapeHtml(meta.icon)}</span>
            <span class="msg-special-copy">
                <span class="msg-special-title">${escapeHtml(meta.title)}</span>
                ${detail ? `<span class="msg-special-detail">${escapeHtml(detail)}</span>` : ''}
            </span>
        </div>
    `;
}
