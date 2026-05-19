const DATE_LOCALE = 'en-US';

export function supportedRegionalTimes() {
    const base = [
        { value: 'local', label: 'System local time' },
        { value: 'UTC', label: 'UTC' },
    ];
    if (typeof Intl.supportedValuesOf !== 'function') {
        return base;
    }
    const zones = Intl.supportedValuesOf('timeZone')
        .filter(zone => zone !== 'UTC')
        .map(zone => ({ value: zone, label: zone.replaceAll('_', ' ') }));
    return base.concat(zones);
}

export function normalizeRegionalTime(value) {
    if (!value || value === 'local') return 'local';
    try {
        new Intl.DateTimeFormat(DATE_LOCALE, { timeZone: value }).format(new Date());
        return value;
    } catch {
        return 'local';
    }
}

function dateFromEpoch(epochSeconds) {
    if (!epochSeconds || epochSeconds <= 0) return null;
    const ts = epochSeconds > 9_999_999_999 ? epochSeconds : epochSeconds * 1000;
    const d = new Date(ts);
    return Number.isNaN(d.getTime()) ? null : d;
}

function optionsWithZone(regionalTime, options) {
    const zone = normalizeRegionalTime(regionalTime);
    return zone === 'local' ? options : { ...options, timeZone: zone };
}

export function formatClockTime(epochSeconds, regionalTime = 'local') {
    const d = dateFromEpoch(epochSeconds);
    if (!d) return '';
    return new Intl.DateTimeFormat(DATE_LOCALE, optionsWithZone(regionalTime, {
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
    })).format(d);
}

export function formatDateSeparator(epochSeconds, regionalTime = 'local') {
    const d = dateFromEpoch(epochSeconds);
    if (!d) return '';
    return new Intl.DateTimeFormat(DATE_LOCALE, optionsWithZone(regionalTime, {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
    })).format(d);
}

export function formatExactDateTime(epochSeconds, regionalTime = 'local') {
    const d = dateFromEpoch(epochSeconds);
    if (!d) return '';
    return new Intl.DateTimeFormat(DATE_LOCALE, optionsWithZone(regionalTime, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
    })).format(d);
}

export function formatShortDate(epochSeconds, regionalTime = 'local') {
    const d = dateFromEpoch(epochSeconds);
    if (!d) return '';
    return new Intl.DateTimeFormat(DATE_LOCALE, optionsWithZone(regionalTime, {
        day: 'numeric',
        month: 'short',
    })).format(d);
}

function dateKey(date, regionalTime = 'local') {
    return new Intl.DateTimeFormat('en-CA', optionsWithZone(regionalTime, {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
    })).format(date);
}

export function formatChatPreviewTime(epochSeconds, regionalTime = 'local') {
    const d = dateFromEpoch(epochSeconds);
    if (!d) return '';
    const now = new Date();
    if (dateKey(d, regionalTime) === dateKey(now, regionalTime)) {
        return formatClockTime(epochSeconds, regionalTime);
    }
    const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    if (dateKey(d, regionalTime) === dateKey(yesterday, regionalTime)) {
        return 'Yesterday';
    }
    return formatShortDate(epochSeconds, regionalTime);
}

export function regionalTimeLabel(regionalTime = 'local') {
    const normalized = normalizeRegionalTime(regionalTime);
    return normalized === 'local' ? 'System local time' : normalized;
}
