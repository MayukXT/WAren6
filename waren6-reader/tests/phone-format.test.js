import test from 'node:test';
import assert from 'node:assert/strict';

import {
    compactPhoneNumber,
    formatPhoneNumber,
    phoneDigits,
} from '../src/phone-format.js';

test('formats international phone numbers with country codes', () => {
    assert.equal(formatPhoneNumber('910000000000'), '+91 00000 00000');
    assert.equal(formatPhoneNumber('15550101234'), '+1 555 010 1234');
    assert.equal(formatPhoneNumber('442079460958'), '+44 207 946 0958');
    assert.equal(formatPhoneNumber('8801712345678'), '+880 171 234 5678');
});

test('does not invent a country code for local-only numbers', () => {
    assert.equal(formatPhoneNumber('5551234567'), '555 123 4567');
});

test('normalizes JIDs and formatted labels to digits', () => {
    assert.equal(phoneDigits('+1 (555) 010-1234@c.us'), '15550101234');
    assert.equal(compactPhoneNumber('15550101234@c.us'), '+15550101234');
});
