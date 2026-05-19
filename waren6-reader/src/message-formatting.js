import { formatPhoneNumber, phoneDigits } from './phone-format.js';

function escapeHtml(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function escapeAttr(s) {
    return escapeHtml(s).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function linkify(html) {
    return html.replace(
        /(https?:\/\/[^\s<>"'&]+(?:&amp;[^\s<>"'&]+)*)/gi,
        '<a href="$1" class="msg-link" target="_blank" rel="noopener noreferrer">$1</a>'
    );
}

const CONTACT_TOKEN_RE = /(^|[^\w/])(@\+?\d[\d .()\-]{6,}\d(?:@(lid|c\.us|s\.whatsapp\.net))?|@\+?\d[\d .()\-]{6,}\d|\+\d[\d .()\-]{6,}\d|\b\d{10,15}(?:@(lid|c\.us|s\.whatsapp\.net))?\b)(?=$|[^\w])/g;

function contactLinkForToken(token, resolver) {
    const digits = token.replace(/\D/g, '');
    const isTaggedOrInternational = token.startsWith('@') || token.startsWith('+');
    const explicitDomain = token.match(/@(lid|c\.us|s\.whatsapp\.net)\b/i)?.[1];
    const maxDigits = explicitDomain ? 20 : 15;
    if (digits.length < (isTaggedOrInternational ? 8 : 10) || digits.length > maxDigits) return token;
    const jid = explicitDomain ? `${digits}@${explicitDomain}` : `${digits}@c.us`;
    const resolved = typeof resolver === 'function' ? resolver({ token, digits, jid }) : null;
    const label = resolved?.label || token;
    const targetJid = resolved?.jid || jid;
    return `<span class="msg-contact-link" role="button" tabindex="0" data-contact-jid="${escapeAttr(targetJid)}">${escapeHtml(label)}</span>`;
}

function linkifyContactsInText(text, resolver) {
    return text.replace(CONTACT_TOKEN_RE, (_match, prefix, token) => `${prefix}${contactLinkForToken(token, resolver)}`);
}

function linkifyContacts(html, resolver) {
    return html
        .split(/(<a\b[\s\S]*?<\/a>|<code\b[\s\S]*?<\/code>|<[^>]+>)/gi)
        .map(part => part.startsWith('<') ? part : linkifyContactsInText(part, resolver))
        .join('');
}

function normalizeMentionLabel(value) {
    return String(value || '').trim().replace(/^@/, '');
}

function mentionLabel(mention) {
    const kind = String(mention?.kind || '').toLowerCase();
    if (kind === 'all') {
        const label = normalizeMentionLabel(mention?.display_text) || 'all';
        return label.startsWith('all') ? `@${label}` : `@${label}`;
    }

    const phone = formatPhoneNumber(mention?.target_phone) || '';
    const fallbackId = mention?.target_jid ? String(mention.target_jid).split('@')[0] : '';
    const label = normalizeMentionLabel(mention?.display_text)
        || normalizeMentionLabel(mention?.target_name)
        || phone
        || fallbackId
        || 'Unknown contact';
    return label.startsWith('+') ? `@${label}` : `@${label}`;
}

function mentionTargetJid(mention) {
    if (mention?.target_jid) return String(mention.target_jid);
    const digits = phoneDigits(mention?.target_phone);
    return digits ? `${digits}@c.us` : '';
}

function escapedMentionCandidates(mention) {
    const values = new Set();
    const add = (value) => {
        const raw = String(value || '').trim();
        if (!raw) return;
        values.add(raw.startsWith('@') ? raw : `@${raw}`);
    };

    add(mention?.display_text);
    add(mention?.target_name);
    add(mention?.target_jid);
    add(String(mention?.target_jid || '').split('@')[0]);

    const phone = phoneDigits(mention?.target_phone);
    if (phone) {
        add(phone);
        add(formatPhoneNumber(phone));
        add(`+${phone}`);
    }

    if (String(mention?.kind || '').toLowerCase() === 'all') {
        add('@all');
        add('@everyone');
    }

    return [...values]
        .filter(Boolean)
        .sort((a, b) => b.length - a.length)
        .map(escapeHtml);
}

function renderMentionSpan(mention) {
    const label = mentionLabel(mention);
    if (String(mention?.kind || '').toLowerCase() === 'all') {
        return `<span class="msg-mention msg-mention-all" title="Group-wide mention">${escapeHtml(label)}</span>`;
    }

    const targetJid = mentionTargetJid(mention);
    const contactAttrs = targetJid
        ? ` role="button" tabindex="0" data-contact-jid="${escapeAttr(targetJid)}"`
        : '';
    return `<span class="msg-mention msg-contact-link"${contactAttrs}>${escapeHtml(label)}</span>`;
}

function applyMentionMetadata(html, mentions = []) {
    const placeholders = [];
    let nextHtml = html;

    for (const mention of mentions || []) {
        const candidates = escapedMentionCandidates(mention);
        if (!candidates.length) continue;

        for (const candidate of candidates) {
            const index = nextHtml.indexOf(candidate);
            if (index < 0) continue;

            const token = `\u0000MENTION${placeholders.length}\u0000`;
            placeholders.push(renderMentionSpan(mention));
            nextHtml = `${nextHtml.slice(0, index)}${token}${nextHtml.slice(index + candidate.length)}`;
            break;
        }
    }

    return {
        html: nextHtml,
        restore: value => value.replace(/\u0000MENTION(\d+)\u0000/g, (_, index) => placeholders[Number(index)] || ''),
    };
}

function applyInlineFormatting(html) {
    const boundaryBefore = '(^|[\\s([{>])';
    const boundaryAfter = '(?=$|[\\s.,!?;:)\\]}<])';
    const tokenBody = '([^\\s$TOKEN](?:[^$TOKEN]*?[^\\s$TOKEN])?)';

    return html
        .replace(new RegExp(`${boundaryBefore}\\*${tokenBody.replaceAll('$TOKEN', '*')}\\*${boundaryAfter}`, 'g'), '$1<strong>$2</strong>')
        .replace(new RegExp(`${boundaryBefore}_${tokenBody.replaceAll('$TOKEN', '_')}_${boundaryAfter}`, 'g'), '$1<em>$2</em>')
        .replace(new RegExp(`${boundaryBefore}~${tokenBody.replaceAll('$TOKEN', '~')}~${boundaryAfter}`, 'g'), '$1<s>$2</s>');
}

export function renderWhatsAppText(text, options = {}) {
    const codeBlocks = [];
    let html = escapeHtml(text);
    const mentionState = applyMentionMetadata(html, options.mentions || []);
    html = mentionState.html;

    html = html.replace(/```([\s\S]*?)```/g, (_, code) => {
        const token = `\u0000CODE${codeBlocks.length}\u0000`;
        codeBlocks.push(`<code class="msg-inline-code">${code}</code>`);
        return token;
    });

    html = applyInlineFormatting(html);
    html = html.replace(/\n/g, '<br>');
    html = html.replace(/\u0000CODE(\d+)\u0000/g, (_, index) => codeBlocks[Number(index)] || '');

    html = linkify(html);
    html = options.contactLinks ? linkifyContacts(html, options.contactResolver) : html;
    return mentionState.restore(html);
}
