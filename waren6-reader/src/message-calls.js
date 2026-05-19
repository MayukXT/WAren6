export function callIsVideo(call) {
    return call?.is_video_call === 1
        || call?.is_video_call === true
        || String(call?.is_video_call).toLowerCase() === 'true';
}

export function callOutcomeMeta(call) {
    const outcome = String(call?.call_outcome || '').toLowerCase();
    const missed = outcome.includes('missed') || outcome === '2' || outcome === 'missed_call';
    const declined = outcome.includes('rejected') || outcome.includes('declined') || outcome === '3';
    const answered = outcome.includes('accepted')
        || outcome.includes('answered')
        || outcome.includes('completed')
        || outcome === '1'
        || Number(call?.call_duration) > 0;

    if (missed) return { label: 'Missed', tone: 'missed' };
    if (declined) return { label: 'Declined', tone: 'declined' };
    if (answered) return { label: 'Answered', tone: 'answered' };
    return { label: 'Call', tone: 'neutral' };
}

export function callDirectionMeta(call) {
    if (Number(call?.from_me) === 1) return { label: 'Outgoing', tone: 'outgoing' };
    if (Number(call?.from_me) === 0) return { label: 'Incoming', tone: 'incoming' };
    return { label: 'Unknown', tone: 'unknown' };
}

export function callTitle(call) {
    const outcome = callOutcomeMeta(call);
    const type = callIsVideo(call) ? 'video call' : 'voice call';
    return outcome.label === 'Call' ? type.replace(/^\w/, ch => ch.toUpperCase()) : `${outcome.label} ${type}`;
}

export function callMatchesFilter(call, filter = 'all') {
    const normalized = String(filter || 'all').toLowerCase();
    const outcome = callOutcomeMeta(call).tone;
    const direction = callDirectionMeta(call).tone;
    const isVideo = callIsVideo(call);

    if (normalized === 'all') return true;
    if (normalized === 'missed') return outcome === 'missed';
    if (normalized === 'answered') return outcome === 'answered';
    if (normalized === 'incoming') return direction === 'incoming';
    if (normalized === 'outgoing') return direction === 'outgoing';
    if (normalized === 'voice') return !isVideo;
    if (normalized === 'video') return isVideo;
    return true;
}

export function callMatchesSearch(call, query = '') {
    const tokens = String(query || '').toLowerCase().trim().split(/\s+/).filter(Boolean);
    if (!tokens.length) return true;
    const haystack = [
        call?.chat_name,
        call?.sender_name,
        call?.phone,
        call?.sender_phone,
        call?.chat_jid,
        call?.call_outcome,
        callTitle(call),
        callDirectionMeta(call).label,
    ].filter(Boolean).join(' ').toLowerCase();
    return tokens.every(token => haystack.includes(token));
}

export function callDayLabel(call, locale = 'en-US') {
    const ts = Number(call?.timestamp || 0);
    if (!Number.isFinite(ts) || ts <= 0) return 'Undated';
    return new Intl.DateTimeFormat(locale, {
        weekday: 'long',
        month: 'long',
        day: 'numeric',
        year: 'numeric',
        timeZone: 'UTC',
    }).format(new Date(ts * 1000));
}

export function callCanJumpToMessage(call) {
    return Boolean(call?.chat_jid && Number.isFinite(Number(call?.rowid)));
}
