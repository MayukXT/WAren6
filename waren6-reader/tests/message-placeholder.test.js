import test from 'node:test';
import assert from 'node:assert/strict';

import {
    missingMessageBodyLabel,
} from '../src/message-placeholders.js';

test('encrypted opaque chat rows are labelled instead of rendered as dots', () => {
    assert.equal(
        missingMessageBodyLabel({
            msg_type: 'chat',
            text: null,
            source_recovery: 'store8_opaque_unresolved',
        }),
        'Encrypted message body not recovered'
    );
});

test('unknown empty chat rows are labelled without decorative ellipsis', () => {
    const label = missingMessageBodyLabel({
        msg_type: 'chat',
        text: null,
        source_recovery: 'store8',
    });

    assert.equal(label.includes('...'), false);
    assert.equal(label.includes('·'), false);
});
