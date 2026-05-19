import { formatPhoneNumber } from './phone-format.js';

export function formatContactPhone(value) {
    return formatPhoneNumber(value) || '';
}

export function contactDisplayName(contact) {
    if (contact?.is_self) return 'You';

    const explicit = [
        contact?.display_name,
        contact?.contact_name,
        contact?.short_name,
        contact?.push_name,
        contact?.chat_name,
    ].map(value => String(value || '').trim()).find(Boolean);
    if (explicit) return explicit;

    const phone = formatContactPhone(contact?.phone_number || contact?.phone || contact?.phone_jid);
    if (phone) return phone;

    const jid = String(contact?.jid || contact?.chat_jid || contact?.lid || contact?.phone_jid || '').trim();
    return jid ? jid.split('@')[0] : 'Unknown contact';
}

function explicitContactName(contact) {
    return [
        contact?.display_name,
        contact?.contact_name,
        contact?.short_name,
        contact?.push_name,
        contact?.chat_name,
    ].map(value => String(value || '').trim()).find(Boolean) || '';
}

export function contactInitials(contact) {
    const name = contactDisplayName(contact).replace(/^\+/, '').trim();
    const words = name.split(/\s+/).filter(Boolean);
    if (!words.length) return '?';
    if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
    return `${words[0][0] || ''}${words[1][0] || ''}`.toUpperCase();
}

export function contactIsSaved(contact) {
    return Boolean(
        String(contact?.contact_name || '').trim()
        || String(contact?.short_name || '').trim()
    );
}

export function contactMatchesFilter(contact, filter = 'all') {
    const normalized = String(filter || 'all').toLowerCase();
    const messageCount = Number(contact?.message_count || 0);

    if (contact?.is_group) return false;
    if (normalized === 'all') return true;
    if (normalized === 'saved') return contactIsSaved(contact);
    if (normalized === 'unsaved') return !contactIsSaved(contact);
    if (normalized === 'groups') return false;
    if (normalized === 'chats') return messageCount > 0;
    if (normalized === 'business') return Boolean(contact?.is_business);
    return true;
}

export function contactMatchesSearch(contact, query = '') {
    const tokens = String(query || '').toLowerCase().trim().split(/\s+/).filter(Boolean);
    if (!tokens.length) return true;
    const haystack = [
        contactDisplayName(contact),
        contactSubtitle(contact),
        contact?.jid,
        contact?.chat_jid,
        contact?.lid,
        contact?.phone_jid,
        contact?.phone_number,
        contact?.contact_name,
        contact?.short_name,
        contact?.push_name,
        contact?.chat_name,
    ].filter(Boolean).join(' ').toLowerCase();
    return tokens.every(token => haystack.includes(token));
}

export function contactSubtitle(contact) {
    if (contact?.is_group) {
        const count = Number(contact?.message_count || 0);
        return count > 0 ? `${count.toLocaleString()} messages` : 'Group chat';
    }
    const phone = formatContactPhone(contact?.phone_number || contact?.phone || contact?.phone_jid);
    if (phone && phone === contactDisplayName(contact) && !explicitContactName(contact)) {
        return '';
    }
    return phone
        || String(contact?.jid || contact?.chat_jid || contact?.lid || '').split('@')[0];
}

export function contactMetaLine(contact) {
    const parts = [];
    const messageCount = Number(contact?.message_count || 0);
    const callCount = Number(contact?.call_count || 0);
    const mediaCount = Number(contact?.media_count || 0);

    if (contactIsSaved(contact) && !contact?.is_group) parts.push('Saved');
    if (!contactIsSaved(contact) && !contact?.is_group) parts.push('Unsaved');
    if (contact?.is_business) parts.push('Business');
    if (messageCount > 0) parts.push(`${messageCount.toLocaleString()} messages`);
    if (callCount > 0) parts.push(`${callCount.toLocaleString()} calls`);
    if (mediaCount > 0) parts.push(`${mediaCount.toLocaleString()} media`);
    return parts.join(' · ');
}

export function contactInfoDisplay(info, chatJid = '') {
    if (!info) {
        return {
            name: String(chatJid || '').split('@')[0] || 'Unknown contact',
            phoneLine: '',
            about: 'No contact details found.',
            copyPhone: '',
        };
    }

    const readablePhone = formatContactPhone(info.phone_number);
    const copyPhone = String(info.phone_number || '').replace(/\D/g, '');
    const explicit = explicitContactName(info);
    const name = info.is_self
        ? 'You'
        : (explicit || readablePhone || String(chatJid || info.lid || info.phone_jid || '').split('@')[0] || 'Unknown contact');
    const phoneLine = readablePhone && readablePhone !== name ? readablePhone : '';
    let about = '';

    if (info.is_self) {
        about = 'This is your own number';
    } else if (!explicit && readablePhone) {
        about = 'Unsaved contact';
    } else if (info.phone_jid && formatContactPhone(info.phone_jid) !== readablePhone) {
        about = formatContactPhone(info.phone_jid) || info.phone_jid;
    }

    return {
        name,
        phoneLine,
        about,
        copyPhone,
    };
}
