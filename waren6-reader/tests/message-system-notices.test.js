import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import {
    systemNoticeMeta,
} from '../src/message-system-notices.js';

test('long group system notices use a compact label and muted detail text', () => {
    const detail = 'An unofficial students school group for Class 12 Science, 2026-27. Please add a member tag as such: Name Surname.';
    const meta = systemNoticeMeta('group_notification', detail);

    assert.equal(meta.icon, 'group');
    assert.equal(meta.title, 'Group event');
    assert.equal(meta.detail, detail);
});

test('system notice styling fits the chat timeline instead of oversized pills', () => {
    const css = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8');
    const noticeBlock = css.match(/\.msg-system-notification\s*\{[^}]+}/)?.[0] || '';
    const contentBlock = css.match(/\.system-notice-content\s*\{[^}]+}/)?.[0] || '';
    const iconBlock = css.match(/\.system-icon\s*\{[^}]+}/)?.[0] || '';
    const detailBlock = css.match(/\.system-detail\s*\{[^}]+}/)?.[0] || '';

    assert.ok(noticeBlock, '.msg-system-notification style block should exist');
    assert.ok(contentBlock, '.system-notice-content style block should exist');
    assert.ok(iconBlock, '.system-icon style block should exist');
    assert.ok(detailBlock, '.system-detail style block should exist');

    assert.doesNotMatch(noticeBlock, /border-radius:\s*999px/);
    assert.doesNotMatch(noticeBlock, /box-shadow:/);
    assert.match(contentBlock, /border-radius:\s*10px/);
    assert.match(iconBlock, /width:\s*6px/);
    assert.doesNotMatch(css, /system-group\s+\.system-icon::before\s*\{\s*content:\s*'👥'/);
    assert.match(detailBlock, /white-space:\s*normal/);
    assert.doesNotMatch(detailBlock, /text-overflow:\s*ellipsis/);
});
