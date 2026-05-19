import test from 'node:test';
import assert from 'node:assert/strict';

import {
    renderEditedMarker,
    renderEditHistoryContent,
} from '../src/message-edits.js';

const fmt = ts => `T${ts}`;

test('edited marker renders label and info button only for edited messages', () => {
    assert.equal(renderEditedMarker({ is_edited: false }), '');

    const html = renderEditedMarker({
        msg_key: 'true_12345@c.us_A',
        is_edited: true,
    });

    assert.match(html, /Edited/);
    assert.match(html, /data-message-edit-key="true_12345@c\.us_A"/);
});

test('edit history modal renders full revisions and escapes evidence text', () => {
    const html = renderEditHistoryContent({
        msg_key: 'm1',
        history_status: 'event_history',
        edits: [
            {
                edit_index: 1,
                edited_at: 1770000100,
                previous_text: '<old>',
                new_text: '<new>',
                editor_name: 'Example',
            },
        ],
        quote_snapshots: [
            {
                msg_key: 'reply1',
                timestamp: 1770000200,
                quoted_msg_body: '<quoted>',
            },
        ],
    }, { formatTime: fmt });

    assert.match(html, /Revision 1/);
    assert.match(html, /T1770000100/);
    assert.match(html, /&lt;old&gt;/);
    assert.match(html, /&lt;new&gt;/);
    assert.match(html, /Quote snapshots/);
    assert.match(html, /&lt;quoted&gt;/);
});

test('edit history modal explains marker-only evidence', () => {
    const html = renderEditHistoryContent({
        msg_key: 'm1',
        history_status: 'marker_only',
        edits: [],
        quote_snapshots: [],
    }, { formatTime: fmt });

    assert.match(html, /marked this message as edited/);
    assert.match(html, /history was not present/);
});
