import test from 'node:test';
import assert from 'node:assert/strict';

import {
    anchoredScrollTop,
    scrollTopForBottomDistance,
} from '../src/scroll-stability.js';

test('anchoredScrollTop compensates only for real anchor movement', () => {
    assert.equal(anchoredScrollTop({
        currentScrollTop: 240,
        anchorTopBefore: 120,
        anchorTopAfter: 180,
        maxScrollTop: 1000,
    }), 300);
});

test('anchoredScrollTop ignores sub-pixel anchor drift to prevent visual shudder', () => {
    assert.equal(anchoredScrollTop({
        currentScrollTop: 240,
        anchorTopBefore: 120,
        anchorTopAfter: 120.3,
        maxScrollTop: 1000,
    }), 240);
});

test('scrollTopForBottomDistance preserves the bottom offset after trimming', () => {
    assert.equal(scrollTopForBottomDistance({
        scrollHeight: 1800,
        clientHeight: 600,
        distanceFromBottom: 150,
    }), 1050);
});

