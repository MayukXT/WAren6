import test from 'node:test';
import assert from 'node:assert/strict';

import { renderSpecialMessageContent, specialMessageMeta } from '../src/message-special-types.js';

test('special message metadata covers rough WhatsApp message types', () => {
    assert.equal(specialMessageMeta({ msg_type: 'poll_creation', text: 'Class vote' }).title, 'Poll');
    assert.equal(specialMessageMeta({ msg_type: 'pinned_message' }).title, 'Pinned message');
    assert.equal(specialMessageMeta({ msg_type: 'vcard' }).title, 'Contact card');
    assert.equal(specialMessageMeta({ msg_type: 'location' }).title, 'Location');
    assert.equal(specialMessageMeta({ msg_type: 'interactive' }).title, 'Interactive message');
    assert.equal(specialMessageMeta({ msg_type: 'rich_response' }).title, 'Rich response');
    assert.equal(specialMessageMeta({ msg_type: 'ptv' }).title, 'Video note');
});

test('special message renderer escapes detail text', () => {
    const html = renderSpecialMessageContent({ msg_type: 'poll_creation', text: '<script>alert(1)</script>' });

    assert.match(html, /class="msg-special-card"/);
    assert.match(html, /Poll/);
    assert.match(html, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
});
