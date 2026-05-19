import test from 'node:test';
import assert from 'node:assert/strict';

import {
    messageTickHtml,
    tickStateForMessage,
} from '../src/message-status-ticks.js';

test('sent messages default to a single sent tick when no receipt row exists', () => {
    const state = tickStateForMessage({ from_me: 1, msg_key: 'm1', msg_type: 'chat' }, new Map());

    assert.equal(state.status, 'sent');
    assert.equal(state.ticks, 1);
    assert.match(messageTickHtml({ from_me: 1, msg_key: 'm1', msg_type: 'chat' }, new Map()), /msg-tick-sent/);
});

test('delivered and read receipt statuses render double ticks with read coloring', () => {
    const statuses = new Map([
        ['m2', 'delivered'],
        ['m3', 'read'],
    ]);

    assert.equal(tickStateForMessage({ from_me: 1, msg_key: 'm2', msg_type: 'chat' }, statuses).ticks, 2);
    assert.match(messageTickHtml({ from_me: 1, msg_key: 'm2', msg_type: 'chat' }, statuses), /msg-tick-delivered/);
    assert.match(messageTickHtml({ from_me: 1, msg_key: 'm3', msg_type: 'chat' }, statuses), /msg-tick-read/);
    assert.match(messageTickHtml({ from_me: 1, msg_key: 'm3', msg_type: 'chat' }, statuses), /data-message-info-key="m3"/);
});

test('received messages and call logs do not render message ticks', () => {
    assert.equal(tickStateForMessage({ from_me: 0, msg_key: 'm1', msg_type: 'chat' }, new Map()), null);
    assert.equal(tickStateForMessage({ from_me: 1, msg_key: 'm1', msg_type: 'call_log' }, new Map()), null);
    assert.equal(messageTickHtml({ from_me: 0, msg_key: 'm1', msg_type: 'chat' }, new Map()), '');
});
