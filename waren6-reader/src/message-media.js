const MEDIA_TYPES = new Set(['image', 'video', 'sticker', 'ptt', 'audio', 'ptv', 'document', 'album']);
const EMBEDDED_PREVIEW_MARKERS = ['/9j/', 'iVBORw0K', 'iVBOR'];
const ALBUM_GROUP_KINDS = new Set(['image', 'video', 'gif']);
export const DEFAULT_MEDIA_PAGE_SIZE = 120;

export function mediaDisplayKind(msg) {
    const msgType = String(msg?.msg_type || '').toLowerCase();
    const mimeType = String(msg?.media_mime_type || '').toLowerCase();

    if (MEDIA_TYPES.has(msgType)) return msgType;
    if (mimeType.startsWith('image/')) return 'image';
    if (mimeType.startsWith('video/')) return 'video';
    if (mimeType.startsWith('audio/')) return 'audio';
    if (msg?.media_filename || msg?.media_size || mimeType) return 'document';
    return msgType || 'media';
}

export function isMediaMessage(msg) {
    return MEDIA_TYPES.has(String(msg?.msg_type || '').toLowerCase())
        || Boolean(msg?.media_mime_type || msg?.media_filename || msg?.media_size);
}

export function mediaIsStatusBroadcast(msg) {
    return [
        msg?.chat_jid,
        msg?.chat_name,
    ].some(value => String(value || '').trim().toLowerCase().startsWith('status@broadcast'));
}

export function mediaMatchesFilter(msg, filter = 'all') {
    const normalized = String(filter || 'all').toLowerCase();
    if (normalized === 'all') return true;
    if (normalized === 'missing') return String(msg?.media_status || '').toLowerCase() === 'missing_local_file';
    if (normalized === 'status') return mediaIsStatusBroadcast(msg);

    const kind = mediaDisplayKind(msg);
    if (normalized === 'photos') return ['image', 'album', 'gif'].includes(kind);
    if (normalized === 'videos') return ['video', 'ptv'].includes(kind);
    if (normalized === 'audio') return ['audio', 'ptt'].includes(kind);
    if (normalized === 'documents') return kind === 'document';
    if (normalized === 'stickers') return kind === 'sticker';
    return true;
}

export function mediaMatchesSearch(msg, query = '') {
    const tokens = String(query || '').toLowerCase().trim().split(/\s+/).filter(Boolean);
    if (!tokens.length) return true;
    const haystack = [
        msg?.media_filename,
        msg?.chat_jid,
        msg?.chat_name,
        msg?.sender_name,
        msg?.media_mime_type,
        msg?.msg_type,
        msg?.text,
        msg?.media_status,
    ].filter(Boolean).join(' ').toLowerCase();
    return tokens.every(token => haystack.includes(token));
}

export function mediaMonthLabel(msg, locale = 'en-US') {
    const ts = Number(msg?.timestamp || 0);
    if (!Number.isFinite(ts) || ts <= 0) return 'Undated';
    return new Intl.DateTimeFormat(locale, {
        month: 'long',
        year: 'numeric',
        timeZone: 'UTC',
    }).format(new Date(ts * 1000));
}

export function mediaAvailabilityLabel(msg) {
    const status = String(msg?.media_status || '').toLowerCase();
    if (status === 'local_present') return 'Available';
    if (status === 'missing_local_file') return 'Missing local file';
    if (status === 'metadata_only') return 'Metadata only';
    if (status === 'unlinked_local_file') return 'Unlinked file';
    return status ? status.replace(/_/g, ' ') : 'Unknown';
}

export function mediaCanJumpToMessage(msg) {
    return Boolean(msg?.chat_jid && Number.isFinite(Number(msg?.rowid)));
}

export function visibleMediaCaption(rawText) {
    if (!rawText) return '';
    const indexes = EMBEDDED_PREVIEW_MARKERS
        .map(marker => rawText.indexOf(marker))
        .filter(index => index >= 0);
    if (!indexes.length) return rawText.trim();
    return rawText.slice(0, Math.min(...indexes)).trim();
}

export function isAlbumGroupMedia(msg) {
    return ALBUM_GROUP_KINDS.has(mediaDisplayKind(msg));
}

function albumSenderKey(msg) {
    return [
        msg?.chat_jid || '',
        msg?.from_me ?? '',
        msg?.sender_jid || '',
        msg?.sender_phone || '',
    ].map(value => String(value).trim()).join('|');
}

function albumSenderIdentity(msg) {
    return String(msg?.sender_jid || msg?.sender_phone || '').trim();
}

function albumRunCanAccept(run, msg, maxGapSeconds) {
    if (!run.length) return true;
    const first = run[0];
    const prev = run[run.length - 1];
    const sameChatDirection = String(first?.chat_jid || '').trim() === String(msg?.chat_jid || '').trim()
        && String(first?.from_me ?? '').trim() === String(msg?.from_me ?? '').trim();
    if (!sameChatDirection) return false;

    const prevSender = albumSenderIdentity(prev);
    const nextSender = albumSenderIdentity(msg);
    if (mediaDisplayKind(prev) === 'album' && !prevSender && nextSender) {
        return true;
    }
    if (prevSender && nextSender && prevSender !== nextSender) return false;
    if (!prevSender && !nextSender && albumSenderKey(first) !== albumSenderKey(msg)) return false;

    const prevTs = Number(prev?.timestamp || 0);
    const nextTs = Number(msg?.timestamp || 0);
    if (!Number.isFinite(prevTs) || !Number.isFinite(nextTs) || prevTs <= 0 || nextTs <= 0) return false;
    return Math.abs(nextTs - prevTs) <= maxGapSeconds;
}

function albumMarkerHasOwnMedia(msg) {
    if (mediaDisplayKind(msg) !== 'album') return false;
    const mime = String(msg?.media_mime_type || '').toLowerCase();
    return Boolean(msg?.media_case_path || msg?.media_filename || mime.startsWith('image/') || mime.startsWith('video/'));
}

function flushAlbumRun(run, output, options) {
    if (!run.length) return;

    const marker = run.find(msg => mediaDisplayKind(msg) === 'album') || null;
    const mediaMessages = run.filter(msg => isAlbumGroupMedia(msg) || albumMarkerHasOwnMedia(msg));
    const shouldCollapse = mediaMessages.length >= options.minItems
        || Boolean(marker && mediaMessages.length >= options.minItemsWithMarker);

    if (!shouldCollapse) {
        run.forEach(message => output.push({ type: 'message', message }));
        return;
    }

    output.push({
        type: 'album',
        id: `album-${run[0]?.rowid || 0}-${run[run.length - 1]?.rowid || 0}`,
        marker,
        messages: mediaMessages,
        sourceMessages: [...run],
    });
}

export function buildAlbumRenderItems(messages, {
    minItems = 4,
    minItemsWithMarker = 2,
    maxGapSeconds = 180,
} = {}) {
    const output = [];
    let run = [];

    for (const msg of messages || []) {
        const kind = mediaDisplayKind(msg);
        const candidate = isAlbumGroupMedia(msg) || kind === 'album';

        if (!candidate) {
            flushAlbumRun(run, output, { minItems, minItemsWithMarker });
            run = [];
            output.push({ type: 'message', message: msg });
            continue;
        }

        if (albumRunCanAccept(run, msg, maxGapSeconds)) {
            run.push(msg);
        } else {
            flushAlbumRun(run, output, { minItems, minItemsWithMarker });
            run = [msg];
        }
    }

    flushAlbumRun(run, output, { minItems, minItemsWithMarker });
    return output;
}

export function createMediaPagingState(pageSize = DEFAULT_MEDIA_PAGE_SIZE) {
    return {
        items: [],
        offset: 0,
        pageSize,
        hasMore: true,
        loading: false,
    };
}

export function appendMediaPage(state, pageItems = []) {
    const items = Array.isArray(pageItems) ? pageItems : [];
    const pageSize = Number(state?.pageSize || DEFAULT_MEDIA_PAGE_SIZE);
    const merged = [...(state?.items || []), ...items];

    return {
        items: merged,
        offset: merged.length,
        pageSize,
        hasMore: items.length >= pageSize,
        loading: false,
    };
}
