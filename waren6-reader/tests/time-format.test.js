import test from 'node:test';
import assert from 'node:assert/strict';

import {
    formatClockTime,
    formatDateSeparator,
    formatExactDateTime,
    normalizeRegionalTime,
} from '../src/time-format.js';

test('message bubble time omits timezone suffix for UTC', () => {
    assert.equal(formatClockTime(1714564800, 'UTC'), '12:00 PM');
});

test('regional timezone changes displayed clock time', () => {
    assert.equal(formatClockTime(1714564800, 'Asia/Kolkata'), '5:30 PM');
});

test('date separator uses selected regional timezone', () => {
    assert.equal(formatDateSeparator(1714564800, 'UTC'), 'Wednesday, May 1, 2024');
});

test('exact date time includes date and clock for receipt details', () => {
    assert.equal(formatExactDateTime(1714564800, 'UTC'), 'May 1, 2024, 12:00 PM');
});

test('invalid regional time falls back to system local mode', () => {
    assert.equal(normalizeRegionalTime('Not/AZone'), 'local');
});
