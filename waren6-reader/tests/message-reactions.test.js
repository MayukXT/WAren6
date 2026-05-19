import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import {
    latestReactionRows,
    renderReactionDetailsContent,
    renderReactionSummary,
    summarizeReactions,
} from '../src/message-reactions.js';

test('summarizes reactions by emoji and preserves sender labels', () => {
    const summary = summarizeReactions([
        { reaction_text: '✅', sender_name: 'Example Sender' },
        { reaction_text: '✅', sender_phone: '910000000001' },
        { reaction_text: '👍', sender_name: 'Example Other' },
    ]);

    assert.deepEqual(summary.map(item => ({
        text: item.text,
        count: item.count,
        senders: item.senders,
    })), [
        { text: '✅', count: 2, senders: ['Example Sender', '+91 00000 00001'] },
        { text: '👍', count: 1, senders: ['Example Other'] },
    ]);
});

test('uses latest reaction state per sender and ignores removed reactions', () => {
    const rows = [
        { parent_msg_key: 'm1', sender_jid: '111@lid', sender_name: 'Example Sender', reaction_text: '👍', timestamp: 100 },
        { parent_msg_key: 'm1', sender_jid: '111@lid', sender_name: 'Example Sender', reaction_text: '😂', timestamp: 200 },
        { parent_msg_key: 'm1', sender_jid: '222@lid', sender_name: 'Example Other', reaction_text: '😮', timestamp: 150 },
        { parent_msg_key: 'm1', sender_jid: '222@lid', sender_name: 'Example Other', reaction_text: '', timestamp: 250 },
        { parent_msg_key: 'm1', sender_jid: '333@lid', sender_name: 'Example Third', reaction_text: '😂', timestamp: 180 },
    ];

    const latest = latestReactionRows(rows);
    const summary = summarizeReactions(rows);
    const details = renderReactionDetailsContent(rows, { formatTime: value => `T${value}` });

    assert.deepEqual(latest.map(row => row.reaction_text), ['😂', '😂']);
    assert.equal(summary.length, 1);
    assert.equal(summary[0].text, '😂');
    assert.equal(summary[0].count, 2);
    assert.doesNotMatch(details, /👍|😮/);
    assert.match(details, /Example Sender/);
    assert.match(details, /Example Third/);
});

test('renders compact reaction pills under message bubbles', () => {
    const html = renderReactionSummary([
        { reaction_text: '✅', sender_name: 'Example Sender' },
        { reaction_text: '✅', sender_phone: '910000000001' },
    ], { msgKey: 'm1' });

    assert.match(html, /class="msg-reactions"/);
    assert.match(html, /data-reaction-msg-key="m1"/);
    assert.match(html, /role="button"/);
    assert.match(html, />✅<span class="reaction-count">2<\/span>/);
    assert.match(html, /title="Example Sender, \+91 00000 00001"/);
});

test('reaction labels map the owner phone to You', () => {
    const rows = [
        { parent_msg_key: 'm1', sender_phone: '910000000000', sender_name: '', reaction_text: '😂', timestamp: 1770000001 },
        { parent_msg_key: 'm1', sender_phone: '910000000001', sender_name: 'Example Sender', reaction_text: '😂', timestamp: 1770000002 },
    ];
    const summaryHtml = renderReactionSummary(rows, { msgKey: 'm1', selfPhone: '910000000000' });
    const detailsHtml = renderReactionDetailsContent(rows, {
        selfPhone: '910000000000',
        formatTime: ts => `D${ts}`,
    });

    assert.match(summaryHtml, /title="You, Example Sender"/);
    assert.match(detailsHtml, /class="reaction-detail-name">You<\/span>/);
    assert.doesNotMatch(detailsHtml, /00000 00000/);
});

test('reaction detail modal lists who reacted with exact timestamps', () => {
    const html = renderReactionDetailsContent([
        { reaction_text: '✅', sender_name: 'Example Sender', timestamp: 1770000001 },
        { reaction_text: '😄', sender_phone: '910000000001', timestamp: 1770000002 },
    ], { formatTime: ts => `D${ts}` });

    assert.match(html, /class="reaction-detail-row"/);
    assert.match(html, /Example Sender/);
    assert.match(html, />✅</);
    assert.match(html, /D1770000001/);
    assert.match(html, /\+91 00000 00001/);
    assert.match(html, />😄</);
});

test('reaction UI hangs below bubbles and detail panels scroll', () => {
    const css = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8');
    const reactionsBlock = css.match(/\.msg-reactions\s*\{[^}]+}/)?.[0] || '';
    const bubbleBlock = css.match(/\.msg-bubble\.has-reactions\s*\{[^}]+}/)?.[0] || '';
    const panelBlock = css.match(/\.reaction-info-panel\s*\{[^}]+}/)?.[0] || '';
    const bodyBlock = css.match(/\.reaction-info-body\s*\{[^}]+}/)?.[0] || '';

    assert.match(reactionsBlock, /position:\s*absolute/);
    assert.match(reactionsBlock, /bottom:\s*-/);
    assert.match(bubbleBlock, /margin-bottom:/);
    assert.match(panelBlock, /max-height:/);
    assert.match(bodyBlock, /overflow-y:\s*auto/);
});
