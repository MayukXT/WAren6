import test from 'node:test';
import assert from 'node:assert/strict';

import { renderWhatsAppText } from '../src/message-formatting.js';

test('renders WhatsApp bold italic strike and code markers', () => {
    const html = renderWhatsAppText('*bold* _italic_ ~gone~ ```code```');

    assert.match(html, /<strong>bold<\/strong>/);
    assert.match(html, /<em>italic<\/em>/);
    assert.match(html, /<s>gone<\/s>/);
    assert.match(html, /<code class="msg-inline-code">code<\/code>/);
});

test('escapes HTML before applying WhatsApp formatting', () => {
    const html = renderWhatsAppText('*<script>alert(1)</script>*');

    assert.equal(html, '<strong>&lt;script&gt;alert(1)&lt;/script&gt;</strong>');
});

test('keeps URLs linkified while formatting nearby text', () => {
    const html = renderWhatsAppText('*read* https://example.com/a_b?q=1');

    assert.match(html, /<strong>read<\/strong>/);
    assert.match(html, /<a href="https:\/\/example\.com\/a_b\?q=1"/);
    assert.doesNotMatch(html, /<em>/);
});

test('preserves line breaks', () => {
    assert.equal(renderWhatsAppText('one\ntwo'), 'one<br>two');
});

test('links explicit phone numbers to contact cards when enabled', () => {
    const html = renderWhatsAppText('Call +1 555 010 1234', { contactLinks: true });

    assert.match(html, /class="msg-contact-link"/);
    assert.match(html, /data-contact-jid="15550101234@c\.us"/);
    assert.match(html, />\+1 555 010 1234</);
});

test('links WhatsApp member tags to contact cards when enabled', () => {
    const html = renderWhatsAppText('@56586865271019 please check', { contactLinks: true });

    assert.match(html, /data-contact-jid="56586865271019@c\.us"/);
    assert.match(html, />@56586865271019</);
});

test('contact links can render resolved names instead of raw mention ids', () => {
    const html = renderWhatsAppText('Ask @250848017924129@lid about it', {
        contactLinks: true,
        contactResolver: () => ({
            jid: '250848017924129@lid',
            label: 'Example Member',
        }),
    });

    assert.match(html, /class="msg-contact-link"/);
    assert.match(html, /data-contact-jid="250848017924129@lid"/);
    assert.match(html, />Example Member</);
    assert.doesNotMatch(html, />@250848017924129@lid</);
});

test('mention metadata renders WhatsApp-style named member tags', () => {
    const html = renderWhatsAppText('@~Example Member Amit please check', {
        contactLinks: true,
        mentions: [
            {
                kind: 'participant',
                target_jid: '111@lid',
                target_name: 'Example Member',
                display_text: '~Example Member',
            },
        ],
    });

    assert.match(html, /class="[^"]*msg-mention[^"]*msg-contact-link/);
    assert.match(html, /data-contact-jid="111@lid"/);
    assert.match(html, />@~Example Member</);
});

test('mention metadata falls back to phone and keeps raw lid hidden', () => {
    const html = renderWhatsAppText('@250848017924129@lid hello', {
        contactLinks: true,
        mentions: [
            {
                kind: 'participant',
                target_jid: '250848017924129@lid',
                target_phone: '910000000001',
            },
        ],
    });

    assert.match(html, />@\+91 00000 00001</);
    assert.doesNotMatch(html, />@250848017924129@lid</);
});

test('all-member mentions render as non-contact mention chips', () => {
    const html = renderWhatsAppText('@all please read', {
        contactLinks: true,
        mentions: [{ kind: 'all', display_text: '@all' }],
    });

    assert.match(html, /class="msg-mention msg-mention-all"/);
    assert.doesNotMatch(html, /data-contact-jid/);
    assert.match(html, />@all</);
});

test('does not create contact links inside URLs', () => {
    const html = renderWhatsAppText('https://example.com/15550101234', { contactLinks: true });

    assert.match(html, /<a href="https:\/\/example\.com\/15550101234"/);
    assert.doesNotMatch(html, /msg-contact-link/);
});
