const DELETED_MESSAGE_TYPES = new Set(['revoke', 'revoked']);
const CENTERED_SYSTEM_NOTICE_TYPES = new Set([
    'e2e_notification',
    'pin_v1',
    'ephemeral_setting',
    'gp2',
    'group_notification',
]);

export function isDeletedMessageType(msgType) {
    return DELETED_MESSAGE_TYPES.has(String(msgType || '').toLowerCase());
}

export function isDeletedMessage(msg) {
    if (typeof msg === 'string') return isDeletedMessageType(msg);
    const bodyStatus = String(msg?.body_status || '').toLowerCase();
    return isDeletedMessageType(msg?.msg_type) || bodyStatus === 'revoked_or_deleted';
}

export function isCenteredSystemNoticeType(msgType) {
    return CENTERED_SYSTEM_NOTICE_TYPES.has(String(msgType || '').toLowerCase());
}

