import test from 'node:test';
import assert from 'node:assert/strict';

import {
    callCanJumpToMessage,
    callDayLabel,
    callDirectionMeta,
    callMatchesFilter,
    callMatchesSearch,
    callOutcomeMeta,
    callTitle,
} from '../src/message-calls.js';

test('call history classifies missed, answered, voice, and video calls', () => {
    const missed = { call_outcome: 'Missed', is_video_call: false, call_duration: null };
    const answeredVideo = { call_outcome: 'Completed', is_video_call: true, call_duration: 127 };

    assert.deepEqual(callOutcomeMeta(missed), { label: 'Missed', tone: 'missed' });
    assert.deepEqual(callOutcomeMeta(answeredVideo), { label: 'Answered', tone: 'answered' });
    assert.equal(callTitle(missed), 'Missed voice call');
    assert.equal(callTitle(answeredVideo), 'Answered video call');
});

test('call history filters direction, status, and media type', () => {
    const outgoingVideo = { from_me: 1, is_video_call: true, call_outcome: 'Completed', call_duration: 12 };
    const missedIncoming = { from_me: 0, is_video_call: false, call_outcome: 'Missed' };

    assert.equal(callMatchesFilter(outgoingVideo, 'outgoing'), true);
    assert.equal(callMatchesFilter(outgoingVideo, 'video'), true);
    assert.equal(callMatchesFilter(outgoingVideo, 'missed'), false);
    assert.equal(callMatchesFilter(missedIncoming, 'incoming'), true);
    assert.equal(callMatchesFilter(missedIncoming, 'missed'), true);
});

test('call history search, date labels, direction labels, and jump state are stable', () => {
    const call = {
        rowid: 44,
        chat_jid: '123@c.us',
        chat_name: 'Example Contact',
        phone: '15550101234',
        timestamp: 1778311974,
        from_me: 1,
    };

    assert.equal(callMatchesSearch(call, 'example 010'), true);
    assert.equal(callDayLabel(call), 'Saturday, May 9, 2026');
    assert.deepEqual(callDirectionMeta(call), { label: 'Outgoing', tone: 'outgoing' });
    assert.equal(callCanJumpToMessage(call), true);
});
