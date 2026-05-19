import test from 'node:test';
import assert from 'node:assert/strict';

import {
    isCenteredSystemNoticeType,
    isDeletedMessage,
    isDeletedMessageType,
} from '../src/message-classification.js';

test('deleted message types are not centered system notices', () => {
    assert.equal(isDeletedMessageType('revoke'), true);
    assert.equal(isDeletedMessageType('revoked'), true);
    assert.equal(isCenteredSystemNoticeType('revoke'), false);
    assert.equal(isCenteredSystemNoticeType('revoked'), false);
});

test('body status can mark protocol rows as deleted messages', () => {
    assert.equal(isDeletedMessage({ msg_type: 'protocol', body_status: 'revoked_or_deleted' }), true);
    assert.equal(isDeletedMessage({ msg_type: 'protocol', body_status: 'system_event' }), false);
});

test('application-level system messages remain centered notices', () => {
    assert.equal(isCenteredSystemNoticeType('e2e_notification'), true);
    assert.equal(isCenteredSystemNoticeType('pin_v1'), true);
    assert.equal(isCenteredSystemNoticeType('group_notification'), true);
});

