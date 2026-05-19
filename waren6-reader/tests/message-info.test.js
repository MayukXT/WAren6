import test from 'node:test';
import assert from 'node:assert/strict';

import { renderMessageInfoContent } from '../src/message-info.js';

const fmt = ts => `T${ts}`;

test('message info modal renders empty receipt state', () => {
    const html = renderMessageInfoContent([], { formatTime: fmt });

    assert.match(html, /No receipt rows were extracted/);
});

test('message info modal renders delivered read and played times', () => {
    const html = renderMessageInfoContent([
        {
            receiver_name: 'Example Sender',
            receiver_phone: '910000000001',
            delivery_time: 1770000001,
            read_time: 1770000002,
            played_time: 1770000003,
        },
    ], { formatTime: fmt });

    assert.match(html, /Example Sender/);
    assert.match(html, /Delivered<\/span><strong>T1770000001<\/strong>/);
    assert.match(html, /Read<\/span><strong>T1770000002<\/strong>/);
    assert.match(html, /Played<\/span><strong>T1770000003<\/strong>/);
});

test('message info maps the owner phone to You', () => {
    const html = renderMessageInfoContent([
        {
            receiver_phone: '910000000000',
            receiver_jid: '910000000000@s.whatsapp.net',
            delivery_time: 1770000001,
        },
    ], { formatTime: fmt, selfPhone: '910000000000' });

    assert.match(html, /class="message-info-recipient">You<\/div>/);
    assert.doesNotMatch(html, /00000 00000/);
});

test('message info panel is scrollable for large groups', async () => {
    const { readFileSync } = await import('node:fs');
    const css = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8');
    const panelBlock = css.match(/\.message-info-panel\s*\{[^}]+}/)?.[0] || '';
    const bodyBlock = css.match(/\.message-info-body\s*\{[^}]+}/)?.[0] || '';

    assert.match(panelBlock, /max-height:/);
    assert.match(panelBlock, /overflow:\s*hidden/);
    assert.match(bodyBlock, /overflow-y:\s*auto/);
    assert.match(bodyBlock, /min-height:\s*0/);
});
