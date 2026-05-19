import test from 'node:test';
import assert from 'node:assert/strict';

import {
    memberMatchesQuery,
    memberSearchText,
} from '../src/member-search.js';

test('memberSearchText indexes member name, phone, and fallback id', () => {
    assert.equal(
        memberSearchText({
            name: 'Example Member',
            phone: '+1 555 010 1234',
            lid: '12345@lid',
        }),
        'example member +1 555 010 1234 12345@lid'
    );
});

test('memberMatchesQuery matches formatted phone numbers without requiring spaces', () => {
    const searchText = memberSearchText({
        name: 'Example Member',
        phone: '+1 555 010 1234',
    });

    assert.equal(memberMatchesQuery(searchText, '15550101234'), true);
});

test('memberMatchesQuery returns true for an empty query', () => {
    assert.equal(memberMatchesQuery('any member', '   '), true);
});
