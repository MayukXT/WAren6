export function systemNoticeMeta(msgType, rawText) {
    const type = String(msgType || '').toLowerCase();
    const text = String(rawText || '').trim();

    if (['gp2', 'group_notification'].includes(type)) {
        if (text.length > 72) {
            return { icon: 'group', title: 'Group event', detail: text };
        }
        return { icon: 'group', title: text || 'Group updated', detail: text ? 'Group event' : '' };
    }
    if (type === 'e2e_notification') {
        return { icon: 'lock', title: 'Messages are end-to-end encrypted', detail: text };
    }
    if (type === 'ephemeral_setting') {
        return { icon: 'timer', title: text || 'Disappearing messages changed', detail: text ? 'System setting' : '' };
    }
    if (type === 'pin_v1') {
        return { icon: 'pin', title: text || 'Message pinned', detail: text ? 'Pinned event' : '' };
    }
    return { icon: 'info', title: text || 'System event', detail: '' };
}
