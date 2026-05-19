import { formatPhoneNumber } from './phone-format.js';
import { participantMatchesSelf } from './message-participants.js';

function escapeHtml(value) {
    return String(value || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function receiptName(receipt, { selfPhone = '' } = {}) {
    if ([
        receipt?.receiver_phone,
        receipt?.receiver_jid,
        receipt?.receiver_name,
    ].some(value => participantMatchesSelf(value, { selfPhone }))) {
        return 'You';
    }

    return String(receipt?.receiver_name || '').trim()
        || formatPhoneNumber(receipt?.receiver_phone)
        || String(receipt?.receiver_jid || '').split('@')[0]
        || 'Unknown recipient';
}

function renderTime(label, value, formatTime) {
    if (!value) return '';
    const rendered = typeof formatTime === 'function' ? formatTime(value) : String(value);
    return `<span>${escapeHtml(label)}</span><strong>${escapeHtml(rendered)}</strong>`;
}

export function renderMessageInfoContent(receipts = [], { formatTime, selfPhone = '' } = {}) {
    if (!Array.isArray(receipts) || receipts.length === 0) {
        return '<div class="message-info-empty">No receipt rows were extracted for this message.</div>';
    }

    return `<div class="message-info-list">${receipts.map(receipt => {
        const times = [
            renderTime('Delivered', receipt.delivery_time, formatTime),
            renderTime('Read', receipt.read_time, formatTime),
            renderTime('Played', receipt.played_time, formatTime),
        ].filter(Boolean).join('');
        return `
            <div class="message-info-row">
                <div class="message-info-recipient">${escapeHtml(receiptName(receipt, { selfPhone }))}</div>
                <div class="message-info-times">${times || '<span>No timing metadata</span>'}</div>
            </div>
        `;
    }).join('')}</div>`;
}
