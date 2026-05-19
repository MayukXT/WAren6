import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
    chatDisplayName,
    chatMatchesListFilter,
    isChannelChat,
} from '../src/message-chats.js';

const __dirname = dirname(fileURLToPath(import.meta.url));

test('numeric WhatsApp groups with missing chat_name stay in Groups, not Channels', () => {
    const chat = {
        chat_jid: '120363424823211291@g.us',
        chat_name: null,
        chat_phone: null,
        is_group: true,
        is_newsletter: false,
    };

    assert.equal(isChannelChat(chat), false);
    assert.equal(chatMatchesListFilter(chat, 'group'), true);
    assert.equal(chatMatchesListFilter(chat, 'channel'), false);
});

test('newsletter chats are channels only when the DB or JID says newsletter', () => {
    const newsletter = {
        chat_jid: '1234567890@newsletter',
        chat_name: 'The Times',
        is_group: false,
        is_newsletter: true,
    };

    assert.equal(isChannelChat(newsletter), true);
    assert.equal(chatMatchesListFilter(newsletter, 'channel'), true);
    assert.equal(chatMatchesListFilter(newsletter, 'personal'), false);
});

test('chat display name prefers group subject supplied by backend', () => {
    const chat = {
        chat_jid: '120363424823211291@g.us',
        chat_name: 'Example Study Group',
        chat_phone: null,
    };

    assert.equal(chatDisplayName(chat), 'Example Study Group');
});

test('chat list escapes avatar attributes from database content', () => {
    const source = readFileSync(join(__dirname, '..', 'src', 'main.js'), 'utf8');

    assert.match(source, /const safeInitials = escapeAttr\(initials\)/);
    assert.match(source, /const safeChatJid = escapeAttr\(chat\.chat_jid\)/);
    assert.doesNotMatch(source, /data-initials="\$\{initials\}"/);
    assert.doesNotMatch(source, /data-jid="\$\{chat\.chat_jid\}"/);
    assert.match(source, /function chatItemForJid\(jid\)/);
    assert.doesNotMatch(source, /querySelector\(`\.chat-item\[data-jid="\$\{chatJid\}"\]`\)/);
    assert.doesNotMatch(source, /querySelector\(`\.chat-item\[data-jid="\$\{activeChatId\}"\]`\)/);
});
