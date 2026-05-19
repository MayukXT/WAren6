import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import {
    isMediaMessage,
    mediaAvailabilityLabel,
    appendMediaPage,
    buildAlbumRenderItems,
    createMediaPagingState,
    mediaCanJumpToMessage,
    mediaDisplayKind,
    mediaMatchesFilter,
    mediaMatchesSearch,
    mediaMonthLabel,
    visibleMediaCaption,
} from '../src/message-media.js';

test('media tile markup classes have matching stylesheet selectors', () => {
    const main = readFileSync(new URL('../src/main.js', import.meta.url), 'utf8');
    const css = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8');
    const classes = [
        'media-thumb-icon',
        'media-status-pill',
        'media-tile-body',
        'media-tile-title',
        'media-tile-chat',
        'media-tile-detail',
        'media-tile-actions',
    ];

    for (const className of classes) {
        assert.match(main, new RegExp(`class="[^"]*${className}`));
        assert.match(css, new RegExp(`\\.${className}(?:[\\s,{.:#>]|$)`));
    }
});

test('collapsed chat album markup classes have matching stylesheet selectors', () => {
    const main = readFileSync(new URL('../src/main.js', import.meta.url), 'utf8');
    const css = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8');
    const classes = [
        'msg-album-card',
        'msg-album-grid',
        'msg-album-tile',
        'album-detail-grid',
        'album-reaction-chip',
    ];

    for (const className of classes) {
        assert.match(main, new RegExp(className));
        assert.match(css, new RegExp(`\\.${className}(?:[\\s,{.:#>]|$)`));
    }
});

test('media filter tabs expose status broadcast filtering', () => {
    const index = readFileSync(new URL('../src/index.html', import.meta.url), 'utf8');

    assert.match(index, /data-media-filter="status">Status<\/button>/);
});

test('interactive rows with video MIME metadata render as media', () => {
    const msg = { msg_type: 'interactive', media_mime_type: 'video/mp4' };

    assert.equal(isMediaMessage(msg), true);
    assert.equal(mediaDisplayKind(msg), 'video');
});

test('embedded JPEG preview blobs are stripped from visible media caption', () => {
    const raw = '*New: Keep conversations going*\nPaste a link and send. /9j/4AAQSkZJRgABAgAAAQABAAD';

    assert.equal(
        visibleMediaCaption(raw),
        '*New: Keep conversations going*\nPaste a link and send.'
    );
});

test('long normal captions are still visible captions', () => {
    const raw = `Intro ${'normal words '.repeat(80)}`;

    assert.equal(visibleMediaCaption(raw).startsWith('Intro normal words'), true);
    assert.equal(visibleMediaCaption(raw).length > 500, true);
});

test('media browser filters by whatsapp-like media category and missing status', () => {
    const image = { msg_type: 'image', media_mime_type: 'image/jpeg', media_status: 'local_present' };
    const missingSticker = { msg_type: 'sticker', media_status: 'missing_local_file' };
    const statusImage = { msg_type: 'image', media_mime_type: 'image/jpeg', chat_jid: 'status@broadcast' };
    const suffixedStatus = { msg_type: 'video', media_mime_type: 'video/mp4', chat_name: 'status@broadcast_AC' };
    const chatImage = { msg_type: 'image', media_mime_type: 'image/jpeg', chat_jid: '12345@c.us' };

    assert.equal(mediaMatchesFilter(image, 'photos'), true);
    assert.equal(mediaMatchesFilter(image, 'videos'), false);
    assert.equal(mediaMatchesFilter(missingSticker, 'stickers'), true);
    assert.equal(mediaMatchesFilter(missingSticker, 'missing'), true);
    assert.equal(mediaMatchesFilter(statusImage, 'status'), true);
    assert.equal(mediaMatchesFilter(suffixedStatus, 'status'), true);
    assert.equal(mediaMatchesFilter(chatImage, 'status'), false);
});

test('media browser search matches filename, chat name, mime, and caption text', () => {
    const item = {
        media_filename: 'Result XII.pdf',
        chat_name: 'Example Chat',
        media_mime_type: 'application/pdf',
        text: 'Board result document',
    };

    assert.equal(mediaMatchesSearch(item, 'xii example'), true);
    assert.equal(mediaMatchesSearch(item, 'image'), false);
});

test('media browser exposes month labels, availability labels, and chat jump state', () => {
    const item = {
        rowid: 42,
        chat_jid: '123@c.us',
        timestamp: 1778311974,
        media_status: 'missing_local_file',
    };

    assert.equal(mediaMonthLabel(item), 'May 2026');
    assert.equal(mediaAvailabilityLabel(item), 'Missing local file');
    assert.equal(mediaCanJumpToMessage(item), true);
});

test('album grouping collapses four adjacent same-sender photo or video messages', () => {
    const messages = [
        { rowid: 1, chat_jid: 'g@g.us', sender_jid: 'a@lid', from_me: 0, timestamp: 1000, msg_type: 'image' },
        { rowid: 2, chat_jid: 'g@g.us', sender_jid: 'a@lid', from_me: 0, timestamp: 1001, msg_type: 'video' },
        { rowid: 3, chat_jid: 'g@g.us', sender_jid: 'a@lid', from_me: 0, timestamp: 1002, msg_type: 'image' },
        { rowid: 4, chat_jid: 'g@g.us', sender_jid: 'a@lid', from_me: 0, timestamp: 1003, msg_type: 'image' },
    ];

    const items = buildAlbumRenderItems(messages);

    assert.equal(items.length, 1);
    assert.equal(items[0].type, 'album');
    assert.deepEqual(items[0].messages.map(msg => msg.rowid), [1, 2, 3, 4]);
});

test('album grouping keeps three loose photos separate without an album marker', () => {
    const messages = [
        { rowid: 1, chat_jid: 'g@g.us', sender_jid: 'a@lid', from_me: 0, timestamp: 1000, msg_type: 'image' },
        { rowid: 2, chat_jid: 'g@g.us', sender_jid: 'a@lid', from_me: 0, timestamp: 1001, msg_type: 'image' },
        { rowid: 3, chat_jid: 'g@g.us', sender_jid: 'a@lid', from_me: 0, timestamp: 1002, msg_type: 'image' },
    ];

    const items = buildAlbumRenderItems(messages);

    assert.equal(items.length, 3);
    assert.deepEqual(items.map(item => item.type), ['message', 'message', 'message']);
});

test('album marker collapses adjacent media and hides the empty marker bubble', () => {
    const messages = [
        { rowid: 10, chat_jid: 'g@g.us', sender_jid: 'a@lid', from_me: 0, timestamp: 1000, msg_type: 'album' },
        { rowid: 11, chat_jid: 'g@g.us', sender_jid: 'a@lid', from_me: 0, timestamp: 1001, msg_type: 'image' },
        { rowid: 12, chat_jid: 'g@g.us', sender_jid: 'a@lid', from_me: 0, timestamp: 1002, msg_type: 'image' },
        { rowid: 13, chat_jid: 'g@g.us', sender_jid: 'a@lid', from_me: 0, timestamp: 1003, msg_type: 'video' },
    ];

    const items = buildAlbumRenderItems(messages);

    assert.equal(items.length, 1);
    assert.equal(items[0].type, 'album');
    assert.equal(items[0].marker.rowid, 10);
    assert.deepEqual(items[0].messages.map(msg => msg.rowid), [11, 12, 13]);
});

test('album marker with missing sender metadata can still collapse its adjacent media', () => {
    const messages = [
        { rowid: 10, chat_jid: 'g@g.us', sender_jid: '', from_me: 0, timestamp: 1000, msg_type: 'album' },
        { rowid: 11, chat_jid: 'g@g.us', sender_jid: 'a@lid', from_me: 0, timestamp: 1001, msg_type: 'image' },
        { rowid: 12, chat_jid: 'g@g.us', sender_jid: 'a@lid', from_me: 0, timestamp: 1002, msg_type: 'video' },
    ];

    const items = buildAlbumRenderItems(messages);

    assert.equal(items.length, 1);
    assert.equal(items[0].type, 'album');
    assert.deepEqual(items[0].messages.map(msg => msg.rowid), [11, 12]);
});

test('album grouping splits at sender and time boundaries', () => {
    const messages = [
        { rowid: 1, chat_jid: 'g@g.us', sender_jid: 'a@lid', from_me: 0, timestamp: 1000, msg_type: 'image' },
        { rowid: 2, chat_jid: 'g@g.us', sender_jid: 'a@lid', from_me: 0, timestamp: 1001, msg_type: 'image' },
        { rowid: 3, chat_jid: 'g@g.us', sender_jid: 'b@lid', from_me: 0, timestamp: 1002, msg_type: 'image' },
        { rowid: 4, chat_jid: 'g@g.us', sender_jid: 'a@lid', from_me: 0, timestamp: 1400, msg_type: 'image' },
        { rowid: 5, chat_jid: 'g@g.us', sender_jid: 'a@lid', from_me: 0, timestamp: 1401, msg_type: 'image' },
    ];

    const items = buildAlbumRenderItems(messages);

    assert.equal(items.length, 5);
    assert.deepEqual(items.map(item => item.type), ['message', 'message', 'message', 'message', 'message']);
});

test('media paging appends blocks and advances offset without full-library loading', () => {
    const firstState = createMediaPagingState(3);
    const afterFirst = appendMediaPage(firstState, [{ rowid: 1 }, { rowid: 2 }, { rowid: 3 }]);
    const afterSecond = appendMediaPage(afterFirst, [{ rowid: 4 }]);

    assert.equal(firstState.offset, 0);
    assert.equal(afterFirst.offset, 3);
    assert.equal(afterFirst.hasMore, true);
    assert.deepEqual(afterFirst.items.map(item => item.rowid), [1, 2, 3]);
    assert.equal(afterSecond.offset, 4);
    assert.equal(afterSecond.hasMore, false);
    assert.deepEqual(afterSecond.items.map(item => item.rowid), [1, 2, 3, 4]);
});

test('media paging reset starts a new filter or search from offset zero', () => {
    const state = appendMediaPage(createMediaPagingState(2), [{ rowid: 1 }, { rowid: 2 }]);
    const reset = createMediaPagingState(state.pageSize);

    assert.equal(state.offset, 2);
    assert.equal(reset.offset, 0);
    assert.equal(reset.items.length, 0);
    assert.equal(reset.hasMore, true);
});
