const SUBPIXEL_DRIFT = 0.5;

function clampScrollTop(value, maxScrollTop) {
    const max = Math.max(0, Number(maxScrollTop) || 0);
    const next = Number(value);
    if (!Number.isFinite(next)) return 0;
    return Math.max(0, Math.min(max, next));
}

export function anchoredScrollTop({
    currentScrollTop,
    anchorTopBefore,
    anchorTopAfter,
    maxScrollTop,
}) {
    const delta = Number(anchorTopAfter) - Number(anchorTopBefore);
    if (!Number.isFinite(delta) || Math.abs(delta) < SUBPIXEL_DRIFT) {
        return clampScrollTop(currentScrollTop, maxScrollTop);
    }
    return clampScrollTop(Number(currentScrollTop) + delta, maxScrollTop);
}

export function scrollTopForBottomDistance({
    scrollHeight,
    clientHeight,
    distanceFromBottom,
}) {
    const maxScrollTop = Math.max(0, Number(scrollHeight) - Number(clientHeight));
    return clampScrollTop(maxScrollTop - Number(distanceFromBottom || 0), maxScrollTop);
}

