import { formatPhoneNumber } from './phone-format.js';

export function digitsOnly(value) {
    return String(value || '').replace(/\D/g, '');
}

export function rawParticipantId(jid) {
    const raw = String(jid || '').split('@')[0].trim().replace(/^\+/, '');
    return digitsOnly(raw) || raw;
}

const PARTICIPANT_TOKEN_RE = /(^|[^\w/])(@?\+?\d[\d .()\-]{6,}\d(?:@(lid|c\.us|s\.whatsapp\.net))?)(?=$|[^\w])/g;

function normalizeParticipantCandidate(token) {
    const value = String(token || '').trim().replace(/^@(?=\+?\d)/, '');
    if (!value) return '';
    if (value.includes('@')) {
        const [raw, domain] = value.split('@');
        const normalizedRaw = digitsOnly(raw) || raw.replace(/^\+/, '');
        return normalizedRaw ? `${normalizedRaw}@${domain}` : '';
    }
    const raw = digitsOnly(value) || value.replace(/^\+/, '');
    return raw || '';
}

export function participantCandidatesFromText(text) {
    const candidates = [];
    String(text || '').replace(PARTICIPANT_TOKEN_RE, (_match, _prefix, token) => {
        const normalized = normalizeParticipantCandidate(token);
        if (normalized && !candidates.includes(normalized)) {
            candidates.push(normalized);
        }
        return token;
    });
    return candidates;
}

export function participantCacheKeys(jid) {
    const raw = rawParticipantId(jid);
    return [...new Set([jid, raw].filter(Boolean))];
}

function participantMentionJid(participant) {
    return participant?.participant_lid
        || participant?.participant_jid
        || participant?.jid
        || (participant?.participant_phone ? `${digitsOnly(participant.participant_phone)}@c.us` : '');
}

function pushMentionMatch(matches, index, mention) {
    if (index < 0) return;
    const key = `${index}:${mention.kind}:${mention.target_jid || ''}:${mention.display_text || ''}`;
    if (matches.some(item => item.key === key)) return;
    matches.push({ key, index, mention });
}

export function inferMentionsFromText(text, participants = []) {
    const source = String(text || '');
    if (!source.includes('@')) return [];

    const matches = [];
    source.replace(/(^|[^\w])@(all|everyone)\b/gi, (match, prefix) => {
        const index = source.indexOf(match);
        pushMentionMatch(matches, index + prefix.length, {
            kind: 'all',
            target_jid: null,
            target_phone: null,
            target_name: null,
            display_text: '@all',
            source: 'inferred',
            confidence: 'inferred',
        });
        return match;
    });

    for (const participant of participants || []) {
        const name = String(participant?.participant_name || participant?.name || '').trim();
        const phone = digitsOnly(participant?.participant_phone || participant?.phone || '');
        const targetJid = participantMentionJid(participant);
        const candidates = [];

        if (name) {
            candidates.push({ token: `@~${name}`, display: `~${name}` });
            candidates.push({ token: `@${name}`, display: name });
        }
        if (phone) {
            const formatted = formatPhoneNumber(phone);
            if (formatted) candidates.push({ token: `@${formatted}`, display: formatted });
            candidates.push({ token: `@+${phone}`, display: `+${phone}` });
            candidates.push({ token: `@${phone}`, display: phone });
        }
        if (targetJid) {
            candidates.push({ token: `@${targetJid}`, display: targetJid });
            candidates.push({ token: `@${targetJid.split('@')[0]}`, display: targetJid.split('@')[0] });
        }

        for (const candidate of candidates.sort((a, b) => b.token.length - a.token.length)) {
            const index = source.indexOf(candidate.token);
            if (index < 0) continue;
            pushMentionMatch(matches, index, {
                kind: 'participant',
                target_jid: targetJid || null,
                target_phone: phone || null,
                target_name: name || null,
                display_text: candidate.display,
                source: 'inferred',
                confidence: 'inferred',
            });
        }
    }

    return matches
        .sort((a, b) => a.index - b.index)
        .map(item => item.mention);
}

export function participantMatchesSelf(participant, { selfPhone = '', quotedOriginal = null } = {}) {
    if (quotedOriginal?.from_me === 1 || quotedOriginal?.from_me === true) return true;

    const participantDigits = rawParticipantId(participant);
    const selfDigits = digitsOnly(selfPhone);
    return Boolean(participantDigits && selfDigits && participantDigits === selfDigits);
}
