import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import {
    contactInfoDisplay,
    contactDisplayName,
    contactInitials,
    contactMatchesFilter,
    contactMatchesSearch,
    contactSubtitle,
} from '../src/message-contacts.js';

test('contact row secondary action is view chat instead of info', () => {
    const main = readFileSync(new URL('../src/main.js', import.meta.url), 'utf8');

    assert.match(main, /data-contact-action="view-chat">View chat<\/button>/);
    assert.doesNotMatch(main, /data-contact-action="info">Info<\/button>/);
    assert.doesNotMatch(main, /action === 'info'/);
});

test('contact browser prefers saved names and formats fallback phone labels', () => {
    const saved = {
        display_name: 'Example Saved',
        phone_number: '15550101001',
    };
    const unsaved = {
        phone_number: '15550101002',
        jid: '10097652678836@lid',
    };

    assert.equal(contactDisplayName(saved), 'Example Saved');
    assert.equal(contactDisplayName(unsaved), '+1 555 010 1002');
    assert.equal(contactInitials(saved), 'ES');
});

test('self contact rows render as You instead of the owner phone', () => {
    const self = {
        is_self: true,
        phone_number: '910000000000',
        contact_name: '',
    };

    assert.equal(contactDisplayName(self), 'You');
    assert.equal(contactInitials(self), 'YO');
    assert.equal(contactSubtitle(self), '+91 00000 00000');
});

test('contact browser filters saved, unsaved, and active personal chats', () => {
    const saved = { contact_name: 'Saved Contact', is_group: false, message_count: 0 };
    const unsavedActive = { phone_number: '15550101003', is_group: false, message_count: 42 };

    assert.equal(contactMatchesFilter(saved, 'saved'), true);
    assert.equal(contactMatchesFilter(saved, 'unsaved'), false);
    assert.equal(contactMatchesFilter(unsavedActive, 'unsaved'), true);
    assert.equal(contactMatchesFilter(unsavedActive, 'chats'), true);
});

test('contact browser excludes group rows from contact filters', () => {
    const group = {
        display_name: 'School Group',
        is_group: true,
        is_business: true,
        message_count: 8,
    };

    assert.equal(contactMatchesFilter(group, 'all'), false);
    assert.equal(contactMatchesFilter(group, 'chats'), false);
    assert.equal(contactMatchesFilter(group, 'business'), false);
    assert.equal(contactMatchesFilter(group, 'groups'), false);
});

test('contact browser search covers names, phones, jid, and subtitles', () => {
    const contact = {
        display_name: 'Example Contact',
        phone_number: '15550101234',
        jid: '250848017924129@lid',
        push_name: 'Example Push',
    };

    assert.equal(contactMatchesSearch(contact, 'example push'), true);
    assert.equal(contactMatchesSearch(contact, '010'), true);
    assert.equal(contactMatchesSearch(contact, 'missing'), false);
    assert.equal(contactSubtitle(contact), '+1 555 010 1234');
});

test('contact browser formats non-Indian international numbers', () => {
    assert.equal(contactDisplayName({ phone_number: '15550101234' }), '+1 555 010 1234');
    assert.equal(contactDisplayName({ phone_number: '442079460958' }), '+44 207 946 0958');
});

test('contact browser does not repeat the same fallback phone label', () => {
    const unsaved = {
        phone_number: '15550101002',
        jid: '10097652678836@lid',
    };

    assert.equal(contactDisplayName(unsaved), '+1 555 010 1002');
    assert.equal(contactSubtitle(unsaved), '');
});

test('contact info card avoids duplicate phone lines for unsaved contacts', () => {
    const display = contactInfoDisplay({
        phone_number: '15550101002',
        phone_jid: '15550101002@s.whatsapp.net',
        contact_name: null,
        short_name: null,
        push_name: null,
        is_self: false,
    }, '10097652678836@lid');

    assert.equal(display.name, '+1 555 010 1002');
    assert.equal(display.phoneLine, '');
    assert.equal(display.about, 'Unsaved contact');
});

test('contact info card renders the owner as You', () => {
    const display = contactInfoDisplay({
        phone_number: '910000000000',
        phone_jid: '910000000000@s.whatsapp.net',
        is_self: true,
    }, '910000000000@s.whatsapp.net');

    assert.equal(display.name, 'You');
    assert.equal(display.phoneLine, '+91 00000 00000');
    assert.equal(display.about, 'This is your own number');
});

test('group member rendering maps owner phone to You', () => {
    const main = readFileSync(new URL('../src/main.js', import.meta.url), 'utf8');

    assert.match(main, /const isSelfMember = .*participantMatchesSelf/s);
    assert.match(main, /const name = isSelfMember \? 'You'/);
});

test('group message sender names are clickable contact links', () => {
    const main = readFileSync(new URL('../src/main.js', import.meta.url), 'utf8');

    assert.match(main, /const linkClass = senderContactJid \? ' msg-contact-link' : ''/);
    assert.match(main, /data-contact-jid="\$\{escapeAttr\(senderContactJid\)\}"/);
});

test('contact names do not render decorative ellipsis dots', () => {
    const css = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8');
    const namedBlocks = [
        '.contact-name',
        '.member-name',
        '.search-contact-name',
    ];

    for (const selector of namedBlocks) {
        const escapedSelector = selector.replace('.', '\\.');
        const block = css.match(new RegExp(`[^{}]*${escapedSelector}[^{}]*\\{[^}]+\\}`))?.[0] || '';
        assert.ok(block, `${selector} style block should exist`);
        assert.doesNotMatch(block, /text-overflow:\s*ellipsis/);
    }
});

test('contact links do not add dotted underlines to names', () => {
    const css = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8');
    const block = css.match(/\.msg-contact-link\s*\{[^}]+}/)?.[0] || '';

    assert.ok(block, '.msg-contact-link style block should exist');
    assert.doesNotMatch(block, /text-decoration-style:\s*dotted/);
});
