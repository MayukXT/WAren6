import test from 'node:test';
import assert from 'node:assert/strict';

import {
    inferMentionsFromText,
    participantCandidatesFromText,
    participantMatchesSelf,
    rawParticipantId,
} from '../src/message-participants.js';

test('normalizes WhatsApp participant ids to bare digits', () => {
    assert.equal(rawParticipantId('+1 555 010 1234@c.us'), '15550101234');
    assert.equal(rawParticipantId('910000000000@lid'), '910000000000');
});

test('matches quoted participant to extracted self phone', () => {
    assert.equal(participantMatchesSelf('15550101234@c.us', {
        selfPhone: '+1 555 010 1234',
    }), true);
});

test('treats from-me quoted originals as the user', () => {
    assert.equal(participantMatchesSelf('910000000000@c.us', {
        quotedOriginal: { from_me: 1 },
    }), true);
});

test('does not mark a different participant as the user', () => {
    assert.equal(participantMatchesSelf('4915112345678@c.us', {
        selfPhone: '15550101234',
        quotedOriginal: { from_me: 0 },
    }), false);
});

test('extracts participant candidates from mentions and jid text', () => {
    assert.deepEqual(participantCandidatesFromText('Ask @250848017924129@lid and 15550101234@s.whatsapp.net'), [
        '250848017924129@lid',
        '15550101234@s.whatsapp.net',
    ]);
});

test('infers visible group mentions from member names and all tag', () => {
    const mentions = inferMentionsFromText('@~Example Member Amit @all @+91 00000 00001', [
        {
            participant_lid: '111@lid',
            participant_phone: '910000000001',
            participant_name: 'Example Member',
        },
    ]);

    assert.deepEqual(mentions.map(item => ({
        kind: item.kind,
        target_jid: item.target_jid,
        target_phone: item.target_phone,
        display_text: item.display_text,
        confidence: item.confidence,
    })), [
        {
            kind: 'participant',
            target_jid: '111@lid',
            target_phone: '910000000001',
            display_text: '~Example Member',
            confidence: 'inferred',
        },
        {
            kind: 'all',
            target_jid: null,
            target_phone: null,
            display_text: '@all',
            confidence: 'inferred',
        },
        {
            kind: 'participant',
            target_jid: '111@lid',
            target_phone: '910000000001',
            display_text: '+91 00000 00001',
            confidence: 'inferred',
        },
    ]);
});
