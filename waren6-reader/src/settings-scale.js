export const SCALE_BASELINE_VERSION = 2;
export const UI_SCALE_BASELINE = 1.25;
export const DEFAULT_UI_SCALE = 100;
export const MIN_UI_SCALE = 50;
export const MAX_UI_SCALE = 200;

export function clampUiScale(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return DEFAULT_UI_SCALE;
    return Math.max(MIN_UI_SCALE, Math.min(MAX_UI_SCALE, numeric));
}

export function effectiveUiScale(uiScale) {
    return (clampUiScale(uiScale) / 100) * UI_SCALE_BASELINE;
}

export function migrateUiScaleSetting(raw) {
    const next = { ...(raw || {}) };

    if (next.scaleBaselineVersion !== SCALE_BASELINE_VERSION && Number(next.uiScale) === 125) {
        next.uiScale = DEFAULT_UI_SCALE;
    }

    next.uiScale = clampUiScale(next.uiScale);
    next.scaleBaselineVersion = SCALE_BASELINE_VERSION;
    return next;
}

