const STATUS_LABELS = {
    sent: 'Sent',
    delivered: 'Delivered',
    read: 'Read',
};

const SINGLE_CHECK_PATH = 'M5.8 11.9 1.9 8a.7.7 0 0 1 1-1l2.8 2.8 7.2-8.6a.7.7 0 0 1 1 .9l-7.7 9.3a.7.7 0 0 1-1 .1Z';
const DOUBLE_CHECK_PATH = 'M15.01 3.316l-.478-.372a.365.365 0 0 0-.51.063L8.666 9.88a.32.32 0 0 1-.484.032l-.358-.325a.32.32 0 0 0-.484.032l-.378.48a.418.418 0 0 0 .036.54l1.32 1.267c.143.14.361.125.484-.033l6.272-8.048a.366.366 0 0 0-.064-.51zm-4.1 0l-.478-.372a.365.365 0 0 0-.51.063L4.566 9.88a.32.32 0 0 1-.484.032L1.892 7.74a.366.366 0 0 0-.516.005l-.423.433a.364.364 0 0 0 .006.514l3.255 3.185c.143.14.361.125.484-.033l6.272-8.048a.365.365 0 0 0-.063-.51z';

function escapeAttr(value) {
    return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

export function normalizeReceiptStatus(status) {
    const value = String(status || '').toLowerCase();
    if (value === 'read' || value === 'delivered' || value === 'sent') return value;
    return null;
}

export function tickStateForMessage(msg, statusByKey = new Map()) {
    if (!msg || msg.from_me !== 1 || String(msg.msg_type || '').toLowerCase() === 'call_log') {
        return null;
    }

    const cached = msg.msg_key && typeof statusByKey.get === 'function'
        ? statusByKey.get(msg.msg_key)
        : null;
    const status = normalizeReceiptStatus(cached) || 'sent';
    return {
        status,
        label: STATUS_LABELS[status],
        ticks: status === 'sent' ? 1 : 2,
    };
}

export function messageTickHtml(msg, statusByKey = new Map()) {
    const state = tickStateForMessage(msg, statusByKey);
    if (!state) return '';

    const path = state.ticks === 1 ? SINGLE_CHECK_PATH : DOUBLE_CHECK_PATH;
    const infoAttrs = msg?.msg_key
        ? ` role="button" tabindex="0" data-message-info-key="${escapeAttr(msg.msg_key)}"`
        : '';
    return `<span class="msg-tick msg-tick-${state.status}" title="${state.label}" aria-label="${state.label}"${infoAttrs}><svg viewBox="0 0 16 15" width="16" height="15" aria-hidden="true"><path fill="currentColor" d="${path}"/></svg></span>`;
}
