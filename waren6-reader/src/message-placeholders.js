const OPAQUE_RECOVERY_VALUES = new Set([
    'store8_opaque_unresolved',
]);

export function missingMessageBodyLabel(msg) {
    const bodyStatus = String(msg?.body_status || '').toLowerCase();
    const msgType = String(msg?.msg_type || 'chat').toLowerCase();
    const recovery = String(msg?.source_recovery || '').toLowerCase();

    if (bodyStatus === 'opaque_unresolved') {
        return 'Encrypted message body not recovered';
    }
    if (bodyStatus === 'media_only') {
        return 'Media message';
    }
    if (bodyStatus === 'call_event') {
        return 'Call event';
    }
    if (bodyStatus === 'system_event') {
        return 'System message';
    }
    if (bodyStatus === 'revoked_or_deleted') {
        return 'Deleted message';
    }
    if (OPAQUE_RECOVERY_VALUES.has(recovery)) {
        return 'Encrypted message body not recovered';
    }
    if (msgType === 'chat' || !msgType) {
        return 'Message body unavailable';
    }
    return 'Content unavailable';
}
