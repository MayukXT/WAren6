import test from 'node:test';
import assert from 'node:assert/strict';

import {
    effectiveUiScale,
    migrateUiScaleSetting,
} from '../src/settings-scale.js';

test('maps user-facing 100 percent to the new 125 percent visual baseline', () => {
    assert.equal(effectiveUiScale(100), 1.25);
});

test('keeps the UI scale setting conventional while migrating old 125 percent preference', () => {
    assert.deepEqual(
        migrateUiScaleSetting({ uiScale: 125 }),
        { uiScale: 100, scaleBaselineVersion: 2 }
    );
});

