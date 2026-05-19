export function memberSearchText(member) {
    return [
        member?.name,
        member?.phone,
        member?.lid,
        member?.jid,
    ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
        .replace(/\s+/g, ' ')
        .trim();
}

export function memberMatchesQuery(searchText, query) {
    const normalizedQuery = String(query || '').toLowerCase().replace(/\s+/g, ' ').trim();
    if (!normalizedQuery) return true;

    const normalizedText = String(searchText || '').toLowerCase().replace(/\s+/g, ' ').trim();
    if (normalizedText.includes(normalizedQuery)) return true;

    const queryDigits = normalizedQuery.replace(/[^\d]/g, '');
    if (!queryDigits) return false;

    return normalizedText.replace(/[^\d]/g, '').includes(queryDigits);
}

