import { formatContactPhone } from './message-contacts.js';

export function chatDisplayName(chat) {
    if (chat?.chat_name) return chat.chat_name;
    if (chat?.chat_phone) return formatContactPhone(chat.chat_phone) || `+${chat.chat_phone}`;
    if (chat?.chat_jid) return String(chat.chat_jid).split('@')[0];
    return '—';
}

export function isChannelChat(chat) {
    const jid = String(chat?.chat_jid || '');
    if (chat?.is_newsletter) return true;
    if (jid.includes('@newsletter')) return true;
    if (jid.includes('@broadcast') && !chat?.is_group) return true;
    return false;
}

export function chatMatchesListFilter(chat, filter = 'personal') {
    const normalized = String(filter || 'personal').toLowerCase();
    const channel = isChannelChat(chat);
    if (normalized === 'channel') return channel;
    if (normalized === 'group') return Boolean(chat?.is_group) && !channel;
    return !chat?.is_group && !channel;
}
