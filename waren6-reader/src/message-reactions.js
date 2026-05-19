import { formatPhoneNumber } from './phone-format.js';
import { participantMatchesSelf } from './message-participants.js';

function escapeHtml(value) {
    return String(value || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function escapeAttr(value) {
    return escapeHtml(value).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function reactionSenderLabel(reaction, { selfPhone = '' } = {}) {
    if ([
        reaction?.sender_phone,
        reaction?.sender_jid,
        reaction?.sender_name,
    ].some(value => participantMatchesSelf(value, { selfPhone }))) {
        return 'You';
    }

    return String(reaction?.sender_name || '').trim()
        || formatPhoneNumber(reaction?.sender_phone)
        || String(reaction?.sender_jid || '').split('@')[0]
        || 'Unknown';
}

function reactionSenderKey(reaction, index) {
    return String(reaction?.sender_jid || '').trim()
        || String(reaction?.sender_phone || '').trim()
        || String(reaction?.sender_name || '').trim()
        || `row:${index}`;
}

function reactionTimestamp(reaction) {
    const ts = Number(reaction?.timestamp);
    return Number.isFinite(ts) ? ts : 0;
}

export function latestReactionRows(reactions = []) {
    const latestBySender = new Map();

    (reactions || []).forEach((reaction, index) => {
        const key = `${reaction?.parent_msg_key || ''}|${reactionSenderKey(reaction, index)}`;
        const current = { reaction, timestamp: reactionTimestamp(reaction), index };
        const previous = latestBySender.get(key);
        if (!previous || current.timestamp > previous.timestamp ||
            (current.timestamp === previous.timestamp && current.index > previous.index)) {
            latestBySender.set(key, current);
        }
    });

    return [...latestBySender.values()]
        .map(item => item.reaction)
        .filter(reaction => String(reaction?.reaction_text || '').trim());
}

export function summarizeReactions(reactions = [], { selfPhone = '' } = {}) {
    const byText = new Map();

    for (const reaction of latestReactionRows(reactions)) {
        const text = String(reaction?.reaction_text || '').trim();
        if (!text) continue;
        if (!byText.has(text)) {
            byText.set(text, { text, count: 0, senders: [] });
        }
        const item = byText.get(text);
        item.count += 1;
        const sender = reactionSenderLabel(reaction, { selfPhone });
        if (sender && !item.senders.includes(sender)) item.senders.push(sender);
    }

    return [...byText.values()];
}

export function renderReactionSummary(reactions = [], { msgKey = '', selfPhone = '' } = {}) {
    const summary = summarizeReactions(reactions, { selfPhone });
    if (!summary.length) return '';

    const keyAttr = msgKey ? ` data-reaction-msg-key="${escapeAttr(msgKey)}"` : '';
    return `<div class="msg-reactions" role="button" tabindex="0"${keyAttr} title="View reactions">${summary.map(item => {
        const count = item.count > 1 ? `<span class="reaction-count">${item.count}</span>` : '';
        return `<span class="reaction-pill" title="${escapeAttr(item.senders.join(', '))}">${escapeHtml(item.text)}${count}</span>`;
    }).join('')}</div>`;
}

export function renderReactionDetailsContent(reactions = [], { formatTime, selfPhone = '' } = {}) {
    const rows = latestReactionRows(reactions);
    if (!rows.length) {
        return '<div class="reaction-detail-empty">No reaction rows were extracted for this message.</div>';
    }

    return `<div class="reaction-detail-list">${rows.map(reaction => {
        const timestamp = reaction.timestamp
            ? (typeof formatTime === 'function' ? formatTime(reaction.timestamp) : String(reaction.timestamp))
            : '';
        return `
            <div class="reaction-detail-row">
                <span class="reaction-detail-emoji">${escapeHtml(reaction.reaction_text)}</span>
                <span class="reaction-detail-main">
                    <span class="reaction-detail-name">${escapeHtml(reactionSenderLabel(reaction, { selfPhone }))}</span>
                    ${timestamp ? `<span class="reaction-detail-time">${escapeHtml(timestamp)}</span>` : ''}
                </span>
            </div>
        `;
    }).join('')}</div>`;
}
