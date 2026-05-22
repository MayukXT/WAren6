import {
    DEFAULT_UI_SCALE,
    SCALE_BASELINE_VERSION,
    clampUiScale,
    effectiveUiScale,
    migrateUiScaleSetting,
} from './settings-scale.js';

import {
    anchoredScrollTop,
    scrollTopForBottomDistance,
} from './scroll-stability.js';

import {
    compactPhoneNumber,
    formatPhoneNumber,
} from './phone-format.js';

import {
    inferMentionsFromText,
    participantCandidatesFromText,
    participantCacheKeys,
    participantMatchesSelf,
    rawParticipantId,
} from './message-participants.js';

import {
    memberMatchesQuery,
    memberSearchText,
} from './member-search.js';

import {
    isCenteredSystemNoticeType,
    isDeletedMessage,
} from './message-classification.js';

import {
    missingMessageBodyLabel,
} from './message-placeholders.js';

import {
    systemNoticeMeta,
} from './message-system-notices.js';

import {
    contactInfoDisplay,
    contactDisplayName,
    contactInitials,
    contactMatchesFilter,
    contactMatchesSearch,
    contactMetaLine,
    contactSubtitle,
} from './message-contacts.js';

import {
    chatDisplayName,
    chatMatchesListFilter,
} from './message-chats.js';

import {
    callCanJumpToMessage,
    callDayLabel,
    callDirectionMeta,
    callMatchesFilter,
    callMatchesSearch,
    callOutcomeMeta as browserCallOutcomeMeta,
    callTitle,
} from './message-calls.js';

import {
    appendMediaPage,
    buildAlbumRenderItems,
    createMediaPagingState,
    isMediaMessage,
    mediaAvailabilityLabel,
    mediaCanJumpToMessage,
    mediaDisplayKind,
    mediaMatchesFilter,
    mediaMatchesSearch,
    mediaMonthLabel,
    visibleMediaCaption,
} from './message-media.js';

import { renderWhatsAppText } from './message-formatting.js';
import { messageTickHtml } from './message-status-ticks.js';
import { renderEditedMarker, renderEditHistoryContent } from './message-edits.js';
import { renderMessageInfoContent } from './message-info.js';
import { renderReactionDetailsContent, renderReactionSummary, summarizeReactions } from './message-reactions.js';
import { renderSpecialMessageContent, specialMessageMeta } from './message-special-types.js';

import {
    formatChatPreviewTime,
    formatClockTime,
    formatDateSeparator,
    formatExactDateTime,
    normalizeRegionalTime,
    supportedRegionalTimes,
} from './time-format.js';

import {
    CURRENT_READER_VERSION,
    RELEASE_PAGE_URL,
    checkForReaderUpdate,
    installInstalledUpdate,
    installPortableUpdate,
    openReleasePage,
    updateStatusText,
} from './reader-updater.js';

const { invoke, convertFileSrc } = window.__TAURI__.core;

// ---------------------------------------------------------------------------
// DOM refs
// ---------------------------------------------------------------------------
const setupScreen = document.getElementById('setup-screen');
const appScreen = document.getElementById('app-screen');
const btnSelectDb = document.getElementById('btn-select-db');
const setupError = document.getElementById('setup-error');
const setupInfo = document.getElementById('setup-info');

const tabChats = document.getElementById('tab-chats');
const tabMedia = document.getElementById('tab-media');
const tabContacts = document.getElementById('tab-contacts');
const tabCalls = document.getElementById('tab-calls');
const btnSwitchDb = document.getElementById('btn-switch-db');
const btnReaderInfo = document.getElementById('btn-reader-info');
const viewChatsSection = document.getElementById('view-chats-section');
const viewMediaSection = document.getElementById('view-media-section');
const viewContactsSection = document.getElementById('view-contacts-section');
const viewCallsSection = document.getElementById('view-calls-section');
const mediaGrid = document.getElementById('media-grid');
const mediaGridContainer = document.querySelector('.media-grid-container');
const mediaSummaryText = document.getElementById('media-summary-text');
const mediaSearchInput = document.getElementById('media-search-input');
const mediaFilterTabs = document.getElementById('media-filter-tabs');
const contactsList = document.getElementById('contacts-list');
const contactsSummaryText = document.getElementById('contacts-summary-text');
const contactsSearchInput = document.getElementById('contacts-search-input');
const contactsFilterTabs = document.getElementById('contacts-filter-tabs');
const callsList = document.getElementById('calls-list');
const callsSummaryText = document.getElementById('calls-summary-text');
const callsSearchInput = document.getElementById('calls-search-input');
const callsFilterTabs = document.getElementById('calls-filter-tabs');
const sidebar = document.querySelector('.sidebar');
const sidebarResizer = document.getElementById('sidebar-resizer');

const chatListContainer = document.getElementById('chat-list');
const searchInput = document.getElementById('input-search');
const msgContainer = document.getElementById('message-container');
const btnCloseChat = document.getElementById('btn-close-chat');
const btnSort = document.getElementById('btn-sort');
const sortMenu = document.getElementById('sort-menu');
const chatHeaderClickable = document.getElementById('chat-header-clickable');
const activeChatName = document.getElementById('active-chat-name');
const activeChatStatus = document.getElementById('active-chat-status');
const activeChatPic = document.getElementById('active-chat-pic');

const infoModal = document.getElementById('info-modal');
const btnCloseModal = document.getElementById('btn-close-modal');
const infoName = document.getElementById('info-name');
const infoPhone = document.getElementById('info-phone');
const infoAbout = document.getElementById('info-about');
const infoPic = document.getElementById('info-pic');

const contextMenu = document.getElementById('context-menu');
const ctxPin = document.getElementById('ctx-pin');
const ctxInfo = document.getElementById('ctx-info');

// Message context menu refs
const msgContextMenu = document.getElementById('msg-context-menu');
const msgCtxCopy = document.getElementById('msg-ctx-copy');

const statsBar = document.getElementById('stats-bar');

// New DOM refs for settings and export
const tabSettings = document.getElementById('tab-settings');
const settingsModal = document.getElementById('settings-modal');
const btnCloseSettings = document.getElementById('btn-close-settings');
const readerInfoModal = document.getElementById('reader-info-modal');
const btnCloseReaderInfo = document.getElementById('btn-close-reader-info');
const readerCurrentVersion = document.getElementById('reader-current-version');
const readerLatestVersion = document.getElementById('reader-latest-version');
const readerLatestDate = document.getElementById('reader-latest-date');
const readerLastChecked = document.getElementById('reader-last-checked');
const readerInstallType = document.getElementById('reader-install-type');
const readerUpdateStatus = document.getElementById('reader-update-status');
const readerPathStatus = document.getElementById('reader-path-status');
const btnCheckReaderUpdate = document.getElementById('btn-check-reader-update');
const btnInstallReaderUpdate = document.getElementById('btn-install-reader-update');
const btnOpenReaderRelease = document.getElementById('btn-open-reader-release');
const linkMayukProfile = document.getElementById('link-mayuk-profile');
const linkWarenRepo = document.getElementById('link-waren-repo');
const messageInfoModal = document.getElementById('message-info-modal');
const btnCloseMessageInfo = document.getElementById('btn-close-message-info');
const messageInfoBody = document.getElementById('message-info-body');
const messageEditModal = document.getElementById('message-edit-modal');
const btnCloseMessageEdit = document.getElementById('btn-close-message-edit');
const messageEditBody = document.getElementById('message-edit-body');
const reactionInfoModal = document.getElementById('reaction-info-modal');
const btnCloseReactionInfo = document.getElementById('btn-close-reaction-info');
const reactionInfoBody = document.getElementById('reaction-info-body');
const albumInfoModal = document.getElementById('album-info-modal');
const btnCloseAlbumInfo = document.getElementById('btn-close-album-info');
const albumInfoTitle = document.getElementById('album-info-title');
const albumInfoBody = document.getElementById('album-info-body');
const btnExportChat = document.getElementById('btn-export-chat');
const regionalTimeSelect = document.getElementById('setting-regional-time');
const scrollArea = document.querySelector('.message-scroll-area');

// Auto-inject Scroll to Bottom Button
const chatView = document.querySelector('.chat-view') || document.body;
const scrollBtn = document.createElement('div');
scrollBtn.className = 'scroll-bottom-btn';
scrollBtn.innerHTML = '<svg viewBox="0 0 24 24" width="24" height="24"><path fill="currentColor" d="M11 4v12.2l-5.3-5.3-1.4 1.4L12 20l7.7-7.7-1.4-1.4L13 16.2V4z"/></svg>';
chatView.appendChild(scrollBtn);

if (scrollArea) {
    scrollArea.addEventListener('scroll', () => {
        const distFromBottom = scrollArea.scrollHeight - scrollArea.scrollTop - scrollArea.clientHeight;
        if (distFromBottom > 150) {
            scrollBtn.classList.add('visible');
        } else {
            scrollBtn.classList.remove('visible');
        }
    });
}
scrollBtn.addEventListener('click', async () => {
    if (scrollArea) {
        if (activeChatId && !pagination.allNewerLoaded) {
            const fullChat = allChats.find(c => c.chat_jid === activeChatId) || { chat_jid: activeChatId };
            await openChat(fullChat, chatItemForJid(activeChatId));
        } else {
            scrollArea.scrollTo({ top: scrollArea.scrollHeight, behavior: 'smooth' });
        }
    }
});

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let allChats = [];
let activeChatId = null;
let contextChatId = null;
let currentSort = 'time';
let currentFilter = 'personal'; // personal, group, channel
let pinnedChats = [];
let extractionInfo = null;
let currentDbPath = null; // track loaded DB for scoping localStorage
let mediaItems = [];
let mediaSummary = null;
let mediaLoaded = false;
let mediaFilter = 'all';
let mediaQuery = '';
let mediaPaging = createMediaPagingState();
let mediaItemByRowid = new Map();
let mediaLoadRunId = 0;
let mediaSearchTimer = null;
let contactItems = [];
let contactSummary = null;
let contactsLoaded = false;
let contactFilter = 'all';
let contactQuery = '';
let callItems = [];
let callSummary = null;
let callsLoaded = false;
let callFilter = 'all';
let callQuery = '';
const SIDEBAR_WIDTH_KEY = 'waren6_sidebar_width';
const SIDEBAR_MIN_WIDTH = 260;
const SIDEBAR_MAX_WIDTH = 560;
const READER_UPDATE_LAST_CHECK_KEY = 'waren6_reader_update_last_check';
let readerAppInfo = null;
let readerUpdateInfo = null;
let readerUpdateState = 'idle';
let readerUpdateCheckPromise = null;

// ---------------------------------------------------------------------------
// Tracks per-chat virtual scroll position for paginated loading.
// ---------------------------------------------------------------------------

const PAGE_SIZE = 50; // messages per batch
const TARGET_WINDOW_BEFORE = 45;
const TARGET_WINDOW_AFTER = 45;
const MAX_RENDERED_MESSAGES = 180;
const DEBUG_UI = false;
let searchRunId = 0;
let suppressScrollPaging = false;
let scrollPagingTimer = null;

let pagination = {
    chatJid: null,
    oldestRowid: null,
    newestRowid: null,
    allLoaded: false,
    allNewerLoaded: true,
    isLoading: false,
};

let quoteCache = {
    chatJid: null,
    byStanza: new Map(),
};

let participantNameCache = new Map();
let messageStatusCache = new Map();
let messageMentionCache = new Map();
let messageReactionCache = new Map();
let groupParticipantMentionCache = new Map();
let currentAlbumGroups = new Map();

function chatItemForJid(jid) {
    return Array.from(document.querySelectorAll('.chat-item[data-jid]'))
        .find(el => el.dataset.jid === jid) || null;
}

// ---------------------------------------------------------------------------
// Sender color palette for group chats (WhatsApp-like hashed color)
// ---------------------------------------------------------------------------
const SENDER_COLORS = [
    '#25D366', '#00A884', '#53bdeb', '#7C8EF2', '#FF6B6B',
    '#FFA07A', '#DDA0DD', '#FBBF24', '#34D399', '#F472B6',
    '#60A5FA', '#A78BFA', '#F59E0B', '#10B981', '#EC4899'
];
function senderColor(jid) {
    if (!jid) return SENDER_COLORS[0];
    let hash = 0;
    for (let i = 0; i < jid.length; i++) hash = (hash * 31 + jid.charCodeAt(i)) | 0;
    return SENDER_COLORS[Math.abs(hash) % SENDER_COLORS.length];
}

// ── Pinned chats scoped to current DB path ───────────────────────────────────
function pinnedStorageKey() {
    if (!currentDbPath) return 'waren6_pinned';
    let h = 0;
    for (let i = 0; i < currentDbPath.length; i++) h = (h * 31 + currentDbPath.charCodeAt(i)) | 0;
    return `waren6_pinned_${Math.abs(h).toString(36)}`;
}
function loadPinnedChats() {
    pinnedChats = JSON.parse(localStorage.getItem(pinnedStorageKey()) || '[]');
}
function savePinnedChats() {
    localStorage.setItem(pinnedStorageKey(), JSON.stringify(pinnedChats));
}

function debugLog(...args) {
    if (DEBUG_UI) console.debug(...args);
}

function applySidebarWidth(width) {
    if (!viewChatsSection || !sidebar) return;
    const splitWidth = viewChatsSection.getBoundingClientRect().width || window.innerWidth;
    const maxWidth = Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, Math.floor(splitWidth * 0.48)));
    const nextWidth = clampNumber(Math.round(width), SIDEBAR_MIN_WIDTH, maxWidth);
    document.documentElement.style.setProperty('--sidebar-width', `${nextWidth}px`);
}

function persistSidebarWidth() {
    if (!sidebar) return;
    localStorage.setItem(SIDEBAR_WIDTH_KEY, String(Math.round(sidebar.getBoundingClientRect().width)));
}

function initSidebarResizer() {
    if (!sidebar || !sidebarResizer || !viewChatsSection) return;

    const savedWidth = Number(localStorage.getItem(SIDEBAR_WIDTH_KEY));
    if (Number.isFinite(savedWidth) && savedWidth > 0) applySidebarWidth(savedWidth);

    let startX = 0;
    let startWidth = 0;

    const stopResize = () => {
        document.body.classList.remove('is-resizing-sidebar');
        viewChatsSection.classList.remove('is-resizing');
        persistSidebarWidth();
        window.removeEventListener('pointermove', onPointerMove);
        window.removeEventListener('pointerup', stopResize);
        window.removeEventListener('pointercancel', stopResize);
    };

    const onPointerMove = (event) => {
        event.preventDefault();
        applySidebarWidth(startWidth + event.clientX - startX);
    };

    sidebarResizer.addEventListener('pointerdown', (event) => {
        if (event.button !== 0) return;
        event.preventDefault();
        startX = event.clientX;
        startWidth = sidebar.getBoundingClientRect().width;
        document.body.classList.add('is-resizing-sidebar');
        viewChatsSection.classList.add('is-resizing');
        sidebarResizer.setPointerCapture?.(event.pointerId);
        window.addEventListener('pointermove', onPointerMove);
        window.addEventListener('pointerup', stopResize);
        window.addEventListener('pointercancel', stopResize);
    });

    sidebarResizer.addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();

        const currentWidth = sidebar.getBoundingClientRect().width;
        if (event.key === 'ArrowLeft') applySidebarWidth(currentWidth - 24);
        if (event.key === 'ArrowRight') applySidebarWidth(currentWidth + 24);
        if (event.key === 'Home') applySidebarWidth(SIDEBAR_MIN_WIDTH);
        if (event.key === 'End') applySidebarWidth(SIDEBAR_MAX_WIDTH);
        persistSidebarWidth();
    });

    window.addEventListener('resize', () => {
        applySidebarWidth(sidebar.getBoundingClientRect().width);
    });
}

initSidebarResizer();

function resetConversationState() {
    activeChatId = null;
    contextChatId = null;
    btnCloseChat.style.display = 'none';
    if (btnExportChat) btnExportChat.style.display = 'none';
    activeChatName.textContent = 'Select a chat';
    activeChatStatus.textContent = '';
    activeChatPic.src = '';
    activeChatPic.removeAttribute('data-initials');
    msgContainer.innerHTML = '<div class="empty-state">Select a conversation to start reading.</div>';
    document.querySelectorAll('.chat-item').forEach(el => el.classList.remove('active'));
    pagination = {
        chatJid: null,
        oldestRowid: null,
        newestRowid: null,
        allLoaded: false,
        allNewerLoaded: true,
        isLoading: false,
    };
    quoteCache = { chatJid: null, byStanza: new Map() };
    participantNameCache = new Map();
    messageStatusCache = new Map();
    messageMentionCache = new Map();
    messageReactionCache = new Map();
    groupParticipantMentionCache = new Map();
    currentAlbumGroups = new Map();
    window.currentChatMessages = [];
    window.searchResultsCache = [];
    window.messageWindowMode = false;
}

function resetUiForDatabaseSwitch() {
    resetConversationState();
    searchRunId++;
    if (searchInput) searchInput.value = '';
    if (mediaGrid) mediaGrid.innerHTML = '';
    if (mediaSearchInput) mediaSearchInput.value = '';
    if (contactsList) contactsList.innerHTML = '';
    if (contactsSearchInput) contactsSearchInput.value = '';
    if (callsList) callsList.innerHTML = '';
    if (callsSearchInput) callsSearchInput.value = '';
    mediaItems = [];
    mediaSummary = null;
    mediaLoaded = false;
    mediaFilter = 'all';
    mediaQuery = '';
    mediaPaging = createMediaPagingState();
    mediaItemByRowid = new Map();
    mediaLoadRunId++;
    contactItems = [];
    contactSummary = null;
    contactsLoaded = false;
    contactFilter = 'all';
    contactQuery = '';
    callItems = [];
    callSummary = null;
    callsLoaded = false;
    callFilter = 'all';
    callQuery = '';
    contextMenu.classList.add('hidden');
    msgContextMenu.classList.add('hidden');
    sortMenu.parentElement.classList.remove('active');
    switchTab('chats');
}

function normalizeDbPath(dbPath) {
    if (!dbPath) return dbPath;
    if (dbPath.endsWith('unified_whatsapp.db') === false && !dbPath.includes('.db')) {
        return dbPath.replace(/[\\\/]$/, '') + '\\unified_whatsapp.db';
    }
    return dbPath;
}

function dbFileName(dbPath) {
    return (dbPath || '').split(/[\\\/]/).pop() || 'database';
}

async function loadDatabasePath(dbPath, { fromSetup = false } = {}) {
    const nextPath = normalizeDbPath(dbPath);
    await invoke('set_db_path', { path: nextPath });
    extractionInfo = await invoke('validate_db');
    currentDbPath = nextPath;
    loadPinnedChats();
    await fetchChats();

    setupScreen.classList.add('hidden');
    appScreen.classList.remove('hidden');
    if (!fromSetup) showToast(`Opened ${dbFileName(nextPath)}`, 'success');
}

async function pickAndLoadDatabase({ fromSetup = false } = {}) {
    const previousPath = currentDbPath;
    const dbPath = await invoke('pick_db_file');
    if (!dbPath) return false;
    if (!fromSetup) {
        resetUiForDatabaseSwitch();
        chatListContainer.innerHTML = '<div class="empty-state loading-state"><div class="spinner"></div><div>Opening database...</div></div>';
    }
    try {
        await loadDatabasePath(dbPath, { fromSetup });
    } catch (err) {
        if (!fromSetup && previousPath) {
            await invoke('set_db_path', { path: previousPath });
            extractionInfo = await invoke('validate_db');
            currentDbPath = previousPath;
            loadPinnedChats();
            await fetchChats();
        }
        throw err;
    }
    return true;
}

// Filter tabs logic
document.querySelectorAll('.filter-tab').forEach(btn => {
    btn.addEventListener('click', e => {
        document.querySelectorAll('.filter-tab').forEach(b => b.classList.remove('active'));
        e.target.classList.add('active');
        currentFilter = e.target.getAttribute('data-filter');
        renderChatList(searchInput.value.trim());
    });
});

// ---------------------------------------------------------------------------
// Setup — open unified_whatsapp.db
// ---------------------------------------------------------------------------
btnSelectDb.addEventListener('click', async () => {
    try {
        setupError.textContent = '';
        btnSelectDb.disabled = true;
        btnSelectDb.textContent = 'Opening…';

        setupError.textContent = 'Validating database…';
        const opened = await pickAndLoadDatabase({ fromSetup: true });
        if (!opened) setupError.textContent = '';

    } catch (err) {
        setupError.textContent = '✗ ' + err;
    } finally {
        btnSelectDb.disabled = false;
        btnSelectDb.textContent = 'Open unified_whatsapp.db';
    }
});

// ---------------------------------------------------------------------------
// Tab switching
// ---------------------------------------------------------------------------
function switchTab(tab) {
    const activeTab = ['chats', 'media', 'contacts', 'calls'].includes(tab) ? tab : 'chats';
    tabChats.classList.toggle('active', activeTab === 'chats');
    tabMedia.classList.toggle('active', activeTab === 'media');
    tabContacts?.classList.toggle('active', activeTab === 'contacts');
    tabCalls?.classList.toggle('active', activeTab === 'calls');
    viewChatsSection.classList.toggle('hidden', activeTab !== 'chats');
    viewMediaSection.classList.toggle('hidden', activeTab !== 'media');
    viewContactsSection?.classList.toggle('hidden', activeTab !== 'contacts');
    viewCallsSection?.classList.toggle('hidden', activeTab !== 'calls');
    if (activeTab === 'media') {
        ensureMediaLoaded();
    }
    if (activeTab === 'contacts') {
        ensureContactsLoaded();
    }
    if (activeTab === 'calls') {
        ensureCallsLoaded();
    }
}
tabChats.addEventListener('click', () => switchTab('chats'));
tabMedia.addEventListener('click', () => switchTab('media'));
tabContacts?.addEventListener('click', () => switchTab('contacts'));
tabCalls?.addEventListener('click', () => switchTab('calls'));
if (btnSwitchDb) {
    btnSwitchDb.addEventListener('click', async () => {
        btnSwitchDb.disabled = true;
        try {
            await pickAndLoadDatabase({ fromSetup: false });
        } catch (err) {
            showToast('Failed to open database: ' + err, 'error');
            renderChatList();
        } finally {
            btnSwitchDb.disabled = false;
        }
    });
}

// ---------------------------------------------------------------------------
// Chat list
// ---------------------------------------------------------------------------
async function fetchChats() {
    allChats = await invoke('get_chats');
    renderChatList();
}

function formatTs(epochSeconds) {
    return formatChatPreviewTime(epochSeconds, settings.regionalTime);
}

// ---------------------------------------------------------------------------
// The DB can expose sentinel placeholders like '[Image]' when the latest
// message is media-only. Convert those labels to compact chat-list previews.
// ---------------------------------------------------------------------------

// Sentinel labels returned by the SQL CASE expression.
const MEDIA_PREVIEW_LABELS = {
    '[Image]': '🖼️ Image',
    '[Video]': '🎥 Video',
    '[Voice message]': '🎤 Voice message',
    '[Audio]': '🎵 Audio',
    '[Sticker]': '🎭 Sticker',
    '[Document]': '📄 Document',
};

function lastMsgPreview(chat) {
    const lm = chat.last_msg;

    if (!lm) {
        debugLog(
            `last_msg is null for chat ${chat.chat_jid}` +
            ` (${chatDisplayName(chat)}) - rendering media fallback.` +
            ` last_msg_ts=${chat.last_msg_ts}, msg_count=${chat.message_count}`
        );
        return '<span class="preview-media">📎 Media</span>';
    }

    const trimmed = lm.replace(/\s+/g, ' ').trim();

    if (!trimmed) {
        debugLog(`last_msg trimmed to empty for chat ${chat.chat_jid}`);
        return '<span class="preview-media">📎 Media</span>';
    }

    if (MEDIA_PREVIEW_LABELS[trimmed]) {
        const label = MEDIA_PREVIEW_LABELS[trimmed];
        debugLog(`Sentinel label "${trimmed}" -> "${label}" for ${chat.chat_jid}`);
        return `<span class="preview-media">${label}</span>`;
    }

    debugLog(`last_msg OK for ${chat.chat_jid}: "${trimmed.slice(0, 60)}"`);
    return escapeHtml(trimmed.length > 55 ? trimmed.slice(0, 55) + '…' : trimmed);
}


function escapeHtml(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function escapeAttr(s) {
    return escapeHtml(String(s || '')).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ── Linkify URLs — converts plain-text URLs to clickable <a> tags ────────────
function linkify(html) {
    return html.replace(
        /(https?:\/\/[^\s<>"'&]+(?:&amp;[^\s<>"'&]+)*)/gi,
        '<a href="$1" class="msg-link" target="_blank" rel="noopener noreferrer">$1</a>'
    );
}

function renderChatList(filterQuery = '') {
    chatListContainer.innerHTML = '';

    let list = allChats.filter(c => {
        return chatMatchesListFilter(c, currentFilter);
    });

    if (filterQuery) {
        const q = filterQuery.toLowerCase();
        list = list.filter(c => chatDisplayName(c).toLowerCase().includes(q) || c.chat_jid.includes(q));
    }

    list.sort((a, b) => {
        const aPin = pinnedChats.includes(a.chat_jid);
        const bPin = pinnedChats.includes(b.chat_jid);
        if (aPin !== bPin) return aPin ? -1 : 1;

        if (currentSort === 'name') {
            const aName = chatDisplayName(a);
            const bName = chatDisplayName(b);
            const aIsNum = /^\+?[\d\s]+$/.test(aName);
            const bIsNum = /^\+?[\d\s]+$/.test(bName);

            if (!aIsNum && bIsNum) return -1;
            if (aIsNum && !bIsNum) return 1;

            if (aIsNum && bIsNum) {
                return b.message_count - a.message_count;
            }

            const nameComp = aName.localeCompare(bName, 'en', { sensitivity: 'base' });
            if (nameComp !== 0) return nameComp;

            return a.chat_jid.localeCompare(b.chat_jid);
        }
        if (currentSort === 'count') return b.message_count - a.message_count;
        return b.last_msg_ts - a.last_msg_ts; // default: newest first
    });

    if (list.length === 0) {
        chatListContainer.innerHTML = '<div class="empty-state">No chats found in this category.</div>';
        return;
    }

    for (const chat of list) {
        const isPinned = pinnedChats.includes(chat.chat_jid);
        const isActive = chat.chat_jid === activeChatId;

        const div = document.createElement('div');
        div.className = `chat-item${isActive ? ' active' : ''}${isPinned ? ' pinned' : ''}`;
        div.dataset.jid = chat.chat_jid;

        const name = chatDisplayName(chat);
        const initials = name.slice(0, 2).toUpperCase();
        const safeInitials = escapeAttr(initials);
        const safeChatJid = escapeAttr(chat.chat_jid);
        const timeStr = formatTs(chat.last_msg_ts);
        const preview = lastMsgPreview(chat);
        const groupTag = chat.is_group && currentFilter !== 'group' ? '<span class="chat-group-tag">Group</span>' : '';

        const badgeHtml = chat.message_count > 0
            ? `<span class="chat-badge">${chat.message_count}</span>` : '';

        div.innerHTML = `
            <div class="avatar" data-initials="${safeInitials}">
                <img class="profile-pic" src="" data-jid="${safeChatJid}" alt="${safeInitials}" />
            </div>
            <div class="chat-preview">
                <div class="chat-name-row">
                    <span class="chat-name">${escapeHtml(name)} ${groupTag}</span>
                    <span class="chat-time">${timeStr}</span>
                </div>
                <div class="chat-msg-row">
                    <span class="chat-last-msg">${preview}</span>
                    ${badgeHtml}
                </div>
            </div>
        `;

        chatListContainer.appendChild(div);
    }
}

chatListContainer.addEventListener('click', async (e) => {
    const searchContact = e.target.closest('.search-contact-item[data-contact-jid]');
    if (searchContact) {
        const chatJid = searchContact.dataset.contactJid;
        const fullChat = allChats.find(c => c.chat_jid === chatJid) || {
            chat_jid: chatJid,
            chat_name: searchContact.dataset.contactName || chatJid,
            is_group: searchContact.dataset.isGroup === '1',
            message_count: 0,
            sent_count: 0,
            recv_count: 0,
        };
        openChat(fullChat, chatItemForJid(chatJid));
        return;
    }

    const searchMsg = e.target.closest('.chat-item[data-search-rowid]');
    if (searchMsg) {
        await jumpToMessageInChat(searchMsg.dataset.searchChatJid, Number(searchMsg.dataset.searchRowid), searchMsg.dataset.searchKeyword || '');
        return;
    }

    const chatItem = e.target.closest('.chat-item[data-jid]');
    if (!chatItem) return;
    const chat = allChats.find(c => c.chat_jid === chatItem.dataset.jid);
    if (chat) openChat(chat, chatItem);
});

chatListContainer.addEventListener('contextmenu', (e) => {
    const chatItem = e.target.closest('.chat-item[data-jid]');
    if (!chatItem) return;
    e.preventDefault();
    contextChatId = chatItem.dataset.jid;
    const isPinned = pinnedChats.includes(contextChatId);
    ctxPin.textContent = isPinned ? 'Unpin' : 'Pin';
    contextMenu.style.top = `${e.clientY}px`;
    contextMenu.style.left = `${e.clientX}px`;
    contextMenu.classList.remove('hidden');
});

// ---------------------------------------------------------------------------
// Sort & Search
// ---------------------------------------------------------------------------
btnSort.addEventListener('click', e => {
    e.stopPropagation();
    sortMenu.parentElement.classList.toggle('active');
});

document.querySelectorAll('#sort-menu a').forEach(el => {
    el.addEventListener('click', e => {
        e.preventDefault();
        currentSort = e.target.getAttribute('data-sort');
        sortMenu.parentElement.classList.remove('active');
        renderChatList(searchInput.value.trim());
    });
});

document.addEventListener('click', e => {
    sortMenu.parentElement.classList.remove('active');
    if (!contextMenu.contains(e.target)) contextMenu.classList.add('hidden');
});

let debounce = null;
searchInput.addEventListener('input', e => {
    const q = e.target.value.trim();
    clearTimeout(debounce);
    if (!q) {
        searchRunId++;
        renderChatList();
        return;
    }
    debounce = setTimeout(async () => {
        if (q.length >= 2) {
            await runGlobalSearch(q);
        } else {
            renderChatList(q);
        }
    }, 350);
});

async function runGlobalSearch(q) {
    const runId = ++searchRunId;
    chatListContainer.innerHTML = '<div class="empty-state loading-state"><div class="spinner"></div><div>Searching...</div></div>';
    try {
        const [contactResults, msgResults] = await Promise.all([
            invoke('search_contacts', { query: q }).catch(() => []),
            invoke('search_messages', { query: q })
        ]);
        if (runId !== searchRunId || searchInput.value.trim() !== q) return;
        window.searchResultsCache = msgResults;

        chatListContainer.innerHTML = '';
        const fragment = document.createDocumentFragment();

        // ── Section 1: Contacts/Groups ──
        const contactHeader = document.createElement('div');
        contactHeader.className = 'search-section-header';
        contactHeader.innerHTML = `<svg viewBox="0 0 24 24"><path fill="currentColor" d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg> Contacts / Groups`;
        fragment.appendChild(contactHeader);

        if (contactResults.length > 0) {
            contactResults.forEach(cr => {
                const div = document.createElement('div');
                div.className = 'search-contact-item';
                div.dataset.contactJid = cr.chat_jid;
                div.dataset.contactName = cr.display_name || '';
                div.dataset.isGroup = cr.is_group ? '1' : '0';
                const initials = (cr.display_name || '?').slice(0, 2).toUpperCase();
                div.innerHTML = `
                    <div class="search-contact-avatar${cr.is_group ? ' is-group' : ''}">${escapeHtml(initials)}</div>
                    <div class="search-contact-details">
                        <div class="search-contact-name">${escapeHtml(cr.display_name)}</div>
                        ${cr.phone ? `<div class="search-contact-phone">${escapeHtml(formatPhoneNumber(cr.phone) || `+${cr.phone}`)}</div>` : ''}
                    </div>
                `;
                fragment.appendChild(div);
            });
        } else {
            const noContacts = document.createElement('div');
            noContacts.className = 'search-no-results';
            noContacts.textContent = 'No matching contacts or groups';
            fragment.appendChild(noContacts);
        }

        // ── Section 2: Messages ──
        const msgHeader = document.createElement('div');
        msgHeader.className = 'search-section-header';
        msgHeader.innerHTML = `<svg viewBox="0 0 24 24"><path fill="currentColor" d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/></svg> Messages <span style="opacity:0.6;margin-left:4px;font-weight:400;">(${msgResults.length})</span>`;
        fragment.appendChild(msgHeader);

        if (msgResults.length === 0) {
            const noMsgs = document.createElement('div');
            noMsgs.className = 'search-no-results';
            noMsgs.textContent = 'No matching messages';
            fragment.appendChild(noMsgs);
        } else {
            const highlightRegex = new RegExp("(" + q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ")", "gi");

            msgResults.forEach(res => {
                const msg = res.msg;
                const chatName = res.chat_name || msg.chat_jid.split('@')[0];
                const ts = formatTs(msg.timestamp);

                let snippet = msg.text || '';
                if (snippet.length > 80) {
                    const idx = snippet.toLowerCase().indexOf(q.toLowerCase());
                    if (idx > 20) {
                        snippet = '…' + snippet.substring(idx - 20, idx + 60);
                    } else {
                        snippet = snippet.substring(0, 80) + '…';
                    }
                }
                snippet = escapeHtml(snippet).replace(highlightRegex, '<span class="search-txt-hl">$1</span>');

                const div = document.createElement('div');
                div.className = 'chat-item search-message-item';
                div.dataset.searchChatJid = msg.chat_jid;
                div.dataset.searchRowid = msg.rowid;
                div.dataset.searchKeyword = q;
                div.innerHTML = `
                    <div class="chat-preview">
                        <div class="chat-name-row">
                            <span class="chat-name">${escapeHtml(chatName)}</span>
                            <span class="chat-time">${ts}</span>
                        </div>
                        <div class="chat-msg-row">
                            <span class="chat-last-msg">
                                ${msg.from_me ? '<span style="color:var(--accent);">✓</span> ' : ''}${snippet}
                            </span>
                        </div>
                    </div>
                `;
                fragment.appendChild(div);
            });
        }

        chatListContainer.appendChild(fragment);
    } catch (e) {
        if (runId !== searchRunId) return;
        chatListContainer.innerHTML = `<div class="empty-state error">Search error: ${escapeHtml(String(e))}</div>`;
    }
}

// ---------------------------------------------------------------------------
// Context menu
// ---------------------------------------------------------------------------
ctxPin.addEventListener('click', () => {
    if (!contextChatId) return;
    if (pinnedChats.includes(contextChatId))
        pinnedChats = pinnedChats.filter(id => id !== contextChatId);
    else
        pinnedChats.push(contextChatId);
    savePinnedChats();
    renderChatList(searchInput.value.trim());
    contextMenu.classList.add('hidden');
});

ctxInfo.addEventListener('click', () => {
    contextMenu.classList.add('hidden');
    if (contextChatId) openContactInfo(contextChatId);
});

// ---------------------------------------------------------------------------
// Message context menu clipboard handling. Try the modern Clipboard API first,
// then fall back to document.execCommand('copy') for restricted contexts.
// ---------------------------------------------------------------------------
let contextMsgData = null;
const messageHighlightTimers = new WeakMap();

function clampNumber(value, min, max) {
    return Math.min(Math.max(value, min), max);
}

function centerElementInMessagePane(targetEl, smooth = false) {
    if (!scrollArea || !targetEl) return;

    const areaRect = scrollArea.getBoundingClientRect();
    const targetRect = targetEl.getBoundingClientRect();
    const targetTop = scrollArea.scrollTop + targetRect.top - areaRect.top;
    const centeredTop = targetTop - Math.max(16, (scrollArea.clientHeight - targetRect.height) / 2);
    const maxTop = Math.max(0, scrollArea.scrollHeight - scrollArea.clientHeight);

    scrollArea.scrollTo({
        top: clampNumber(centeredTop, 0, maxTop),
        behavior: smooth ? 'smooth' : 'auto',
    });
}

function centerMessageByRowid(rowid, smooth = false) {
    const targetEl = document.querySelector(
        `.msg-bubble[data-rowid="${rowid}"], .msg-album-tile[data-rowid="${rowid}"]`
    );
    if (!targetEl) return null;
    centerElementInMessagePane(targetEl.closest('.msg-bubble') || targetEl, smooth);
    return targetEl;
}

function holdScrollPaging(ms = 180) {
    suppressScrollPaging = true;
    if (scrollPagingTimer) clearTimeout(scrollPagingTimer);
    scrollPagingTimer = setTimeout(() => {
        suppressScrollPaging = false;
        scrollPagingTimer = null;
    }, ms);
}

function captureScrollAnchor() {
    if (!scrollArea) return null;

    const areaRect = scrollArea.getBoundingClientRect();
    const candidates = Array.from(msgContainer.querySelectorAll('.msg-bubble'));
    const el = candidates.find(node => node.getBoundingClientRect().bottom > areaRect.top + 8)
        || candidates[0]
        || null;

    return el ? { el, top: el.getBoundingClientRect().top } : null;
}

function restoreScrollAnchor(anchor) {
    if (!scrollArea || !anchor?.el?.isConnected) return false;
    const nextTop = anchoredScrollTop({
        currentScrollTop: scrollArea.scrollTop,
        anchorTopBefore: anchor.top,
        anchorTopAfter: anchor.el.getBoundingClientRect().top,
        maxScrollTop: Math.max(0, scrollArea.scrollHeight - scrollArea.clientHeight),
    });
    if (nextTop !== scrollArea.scrollTop) scrollArea.scrollTop = nextTop;
    return true;
}

function createPaginationLoadingIndicator(text = 'Loading messages...') {
    const el = document.createElement('div');
    el.className = 'pagination-loading pagination-loading-overlay';
    el.innerHTML = `<span class="spinner"></span><span>${escapeHtml(text)}</span>`;
    return el;
}

function restoreScrollAnchorOrOffset(anchor, fallbackTop = null) {
    if (restoreScrollAnchor(anchor)) return true;
    if (!scrollArea || fallbackTop === null) return false;

    scrollArea.scrollTop = clampNumber(
        fallbackTop,
        0,
        Math.max(0, scrollArea.scrollHeight - scrollArea.clientHeight)
    );
    return true;
}

function nextAnimationFrame() {
    return new Promise(resolve => requestAnimationFrame(resolve));
}

async function settleScrollAnchor(anchor, fallbackTop = null, frames = 2) {
    for (let i = 0; i < frames; i += 1) {
        restoreScrollAnchorOrOffset(anchor, fallbackTop);
        await nextAnimationFrame();
    }
    restoreScrollAnchorOrOffset(anchor, fallbackTop);
}

function flashMessageHighlight(targetEl) {
    if (!targetEl) return;

    const oldTimer = messageHighlightTimers.get(targetEl);
    if (oldTimer) clearTimeout(oldTimer);

    targetEl.classList.remove('highlight-msg');
    void targetEl.offsetWidth;
    targetEl.classList.add('highlight-msg');

    const timer = setTimeout(() => {
        targetEl.classList.remove('highlight-msg');
        messageHighlightTimers.delete(targetEl);
    }, 3000);
    messageHighlightTimers.set(targetEl, timer);
}

function openOverlay(el) {
    if (!el) return;
    el.classList.remove('hidden', 'is-closing');
}

function closeOverlay(el) {
    if (!el || el.classList.contains('hidden')) return;
    el.classList.add('is-closing');
    setTimeout(() => {
        el.classList.add('hidden');
        el.classList.remove('is-closing');
    }, settings.motion === 'reduced' ? 1 : 160);
}

function formatReaderDate(value) {
    if (!value) return 'Not checked';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString();
}

function readerInstallTypeLabel(value) {
    if (value === 'installed') return 'Installed';
    if (value === 'portable') return 'Portable';
    return 'Unknown';
}

async function openExternalUrl(url) {
    const openUrl = window.__TAURI__?.opener?.openUrl;
    if (typeof openUrl === 'function') {
        await openUrl(url);
        return;
    }
    window.open(url, '_blank', 'noopener,noreferrer');
}

function renderReaderInfo() {
    if (readerCurrentVersion) readerCurrentVersion.textContent = readerAppInfo?.version || CURRENT_READER_VERSION;
    if (readerLatestVersion) readerLatestVersion.textContent = readerUpdateInfo?.latestVersion || 'Not checked';
    if (readerLatestDate) readerLatestDate.textContent = formatReaderDate(readerUpdateInfo?.latestDate);
    if (readerLastChecked) readerLastChecked.textContent = formatReaderDate(localStorage.getItem(READER_UPDATE_LAST_CHECK_KEY));
    if (readerInstallType) readerInstallType.textContent = readerInstallTypeLabel(readerAppInfo?.install_type);

    if (readerPathStatus) {
        if (readerAppInfo?.install_type === 'portable' && !readerAppInfo?.exe_path_is_safe) {
            readerPathStatus.textContent = readerAppInfo.exe_path_status || 'Portable EXE cannot be replaced automatically.';
        } else if (readerAppInfo?.install_type === 'portable') {
            readerPathStatus.textContent = 'Portable EXE can be updated in place.';
        } else if (readerAppInfo?.install_type === 'installed') {
            readerPathStatus.textContent = 'Installed build uses signed Tauri updates.';
        } else {
            readerPathStatus.textContent = 'Install type has not been detected yet.';
        }
    }

    if (readerUpdateStatus) {
        const statusText = readerUpdateState === 'idle' ? 'Not checked yet.' : updateStatusText(readerUpdateState);
        const detail = readerUpdateInfo?.error ? ` ${readerUpdateInfo.error}` : '';
        readerUpdateStatus.textContent = `${statusText}${detail}`;
    }

    const busy = readerUpdateState === 'checking' || readerUpdateState === 'installing';
    if (btnCheckReaderUpdate) btnCheckReaderUpdate.disabled = busy;
    if (btnInstallReaderUpdate) {
        const updateAvailable = readerUpdateInfo?.status === 'available';
        const portableBlocked = readerAppInfo?.install_type === 'portable' && !readerAppInfo?.exe_path_is_safe;
        btnInstallReaderUpdate.disabled = busy || !updateAvailable || portableBlocked;
        btnInstallReaderUpdate.textContent = readerAppInfo?.install_type === 'portable' ? 'Update portable' : 'Install update';
    }
}

async function refreshReaderAppInfo() {
    try {
        readerAppInfo = await invoke('get_app_info');
    } catch (error) {
        readerAppInfo = {
            version: CURRENT_READER_VERSION,
            install_type: 'unknown',
            exe_path_is_safe: false,
            exe_path_status: error instanceof Error ? error.message : String(error),
            app_identifier: 'com.mayukxt.waren6.reader',
        };
    }
    renderReaderInfo();
}

async function checkReaderUpdates({ force = false } = {}) {
    if (readerUpdateCheckPromise) return readerUpdateCheckPromise;
    if (!force && readerUpdateInfo?.status) return readerUpdateInfo;

    readerUpdateCheckPromise = (async () => {
        readerUpdateState = 'checking';
        renderReaderInfo();
        readerUpdateInfo = await checkForReaderUpdate({
            currentVersion: readerAppInfo?.version || CURRENT_READER_VERSION,
        });
        try {
            localStorage.setItem(READER_UPDATE_LAST_CHECK_KEY, new Date().toISOString());
        } catch {
            // Update checks should still work if localStorage is unavailable.
        }
        readerUpdateState = readerUpdateInfo.status;
        renderReaderInfo();
        return readerUpdateInfo;
    })();

    try {
        return await readerUpdateCheckPromise;
    } finally {
        readerUpdateCheckPromise = null;
    }
}

async function runReaderUpdate() {
    if (!readerUpdateInfo?.manifest) {
        await checkReaderUpdates();
    }
    if (readerUpdateInfo?.status !== 'available') return;

    try {
        readerUpdateState = 'installing';
        renderReaderInfo();
        if (readerAppInfo?.install_type === 'portable') {
            await installPortableUpdate(invoke, readerUpdateInfo.manifest);
            readerUpdateState = 'portable';
        } else {
            await installInstalledUpdate(invoke);
            readerUpdateState = 'installed';
        }
    } catch (error) {
        readerUpdateInfo = {
            ...(readerUpdateInfo || {}),
            status: 'failed',
            error: error instanceof Error ? error.message : String(error),
        };
        readerUpdateState = 'failed';
        showToast(readerUpdateInfo.error || 'Reader update failed.', 'error');
    }
    renderReaderInfo();
}

function initReaderInfoPanel() {
    refreshReaderAppInfo().then(() => checkReaderUpdates());

    btnReaderInfo?.addEventListener('click', async () => {
        await refreshReaderAppInfo();
        openOverlay(readerInfoModal);
        checkReaderUpdates({ force: true });
    });
    btnCloseReaderInfo?.addEventListener('click', () => closeOverlay(readerInfoModal));
    readerInfoModal?.addEventListener('click', event => {
        if (event.target === readerInfoModal) closeOverlay(readerInfoModal);
    });
    btnCheckReaderUpdate?.addEventListener('click', () => {
        checkReaderUpdates({ force: true });
    });
    btnInstallReaderUpdate?.addEventListener('click', () => {
        runReaderUpdate();
    });
    btnOpenReaderRelease?.addEventListener('click', () => openReleasePage());
    linkMayukProfile?.addEventListener('click', event => {
        event.preventDefault();
        openExternalUrl('https://github.com/MayukXT');
    });
    linkWarenRepo?.addEventListener('click', event => {
        event.preventDefault();
        openExternalUrl('https://github.com/MayukXT/WAren6');
    });
}

initReaderInfoPanel();

function positionMessageContextMenu(bubble) {
    bubble.appendChild(msgContextMenu);
    msgContextMenu.style.position = 'absolute';
    msgContextMenu.style.top = '-38px';
    msgContextMenu.style.right = '0px';
    msgContextMenu.style.left = 'auto';
    msgContextMenu.style.bottom = 'auto';

    msgContextMenu.classList.remove('hidden');
    msgContextMenu.style.visibility = '';
}

msgContainer.addEventListener('contextmenu', (e) => {
    const bubble = e.target.closest('.msg-bubble');
    if (!bubble) return;
    e.preventDefault();

    const rowid = Math.floor(parseFloat(bubble.getAttribute('data-rowid')));
    contextMsgData = (window.currentChatMessages || []).find(
        m => Math.floor(parseFloat(m.rowid)) === rowid
    ) || null;

    if (!contextMsgData) {
        const textEl = bubble.querySelector('.msg-text');
        const rawText = textEl ? textEl.innerText.trim() : '';
        if (rawText) {
            contextMsgData = { rowid, text: rawText, _fromDom: true };
        }
    }

    contextMenu.classList.add('hidden');
    positionMessageContextMenu(bubble);
});

document.addEventListener('click', (e) => {
    if (!msgContextMenu.contains(e.target)) {
        msgContextMenu.classList.add('hidden');
    }
});

/**
 * Write text to clipboard using the modern Clipboard API with a
 * document.execCommand fallback for restricted browser environments
 * (e.g., http origins in Tauri webview).
 */
async function writeToClipboard(text) {
    // Method 1: Modern async Clipboard API (preferred)
    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (clipErr) {
            console.warn('Clipboard API failed, trying execCommand fallback:', clipErr);
        }
    }

    // Method 2: execCommand fallback (works in Tauri and legacy contexts)
    try {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.cssText = 'position:fixed;top:-9999px;left:-9999px;opacity:0;';
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        const ok = document.execCommand('copy');
        document.body.removeChild(textarea);
        if (!ok) throw new Error('execCommand returned false');
        return true;
    } catch (cmdErr) {
        console.error('execCommand fallback also failed:', cmdErr);
        return false;
    }
}

msgCtxCopy.addEventListener('click', async () => {
    msgContextMenu.classList.add('hidden');

    if (!contextMsgData) {
        showToast('Could not find message data', 'error');
        return;
    }

    const textToCopy = contextMsgData.text || '';
    if (!textToCopy) {
        showToast('No text to copy (media message)', 'info');
        return;
    }

    const ok = await writeToClipboard(textToCopy);
    showToast(
        ok ? 'Copied to clipboard' : 'Could not access clipboard',
        ok ? 'success' : 'error'
    );
});

// ---------------------------------------------------------------------------
// Infinite-scroll upward loads older messages on scroll-up.
// ---------------------------------------------------------------------------
if (scrollArea) {
    scrollArea.addEventListener('scroll', async () => {
        if (suppressScrollPaging || pagination.isLoading || !pagination.chatJid) return;

        if (scrollArea.scrollTop < 120 && !pagination.allLoaded && pagination.oldestRowid !== null) {
            await loadOlderMessages();
            return;
        }

        const distFromBottom = scrollArea.scrollHeight - scrollArea.scrollTop - scrollArea.clientHeight;
        if (distFromBottom < 120 && !pagination.allNewerLoaded && pagination.newestRowid !== null) {
            await loadNewerMessages();
            return;
        }
    });
}

function cleanupStrayDateSeparators() {
    const children = Array.from(msgContainer.children);
    for (const child of children) {
        if (!child.classList.contains('date-separator')) continue;
        let next = child.nextElementSibling;
        while (next && !next.classList.contains('msg-bubble') && !next.classList.contains('date-separator')) {
            next = next.nextElementSibling;
        }
        if (!next || next.classList.contains('date-separator')) {
            child.remove();
        }
    }
}

function suppressFragmentEnterAnimation(fragment) {
    fragment.querySelectorAll('.msg-bubble, .date-separator').forEach(el => {
        el.classList.add('no-enter-animation');
    });
}

function trimRenderedMessages(edge) {
    const messages = window.currentChatMessages || [];
    if (messages.length <= MAX_RENDERED_MESSAGES) return;

    const toRemove = messages.length - MAX_RENDERED_MESSAGES;
    const bubbles = Array.from(msgContainer.querySelectorAll('.msg-bubble'));

    if (edge === 'start') {
        bubbles.slice(0, toRemove).forEach(el => el.remove());
        window.currentChatMessages = messages.slice(toRemove);
        pagination.oldestRowid = window.currentChatMessages[0]?.rowid ?? null;
        pagination.allLoaded = false;
    } else {
        bubbles.slice(-toRemove).forEach(el => el.remove());
        window.currentChatMessages = messages.slice(0, MAX_RENDERED_MESSAGES);
        pagination.newestRowid = window.currentChatMessages[window.currentChatMessages.length - 1]?.rowid ?? null;
        pagination.allNewerLoaded = false;
    }

    cleanupStrayDateSeparators();
}

async function loadOlderMessages() {
    pagination.isLoading = true;
    holdScrollPaging(1200);
    const loadingIndicator = createPaginationLoadingIndicator('Loading messages...');
    chatView.appendChild(loadingIndicator);

    try {
        const older = await invoke('get_messages_paginated', {
            chatJid: pagination.chatJid,
            limit: PAGE_SIZE,
            beforeRowid: pagination.oldestRowid,
        });
        if (older.length < PAGE_SIZE) pagination.allLoaded = true;

        if (older.length === 0) {
            const anchor = captureScrollAnchor();
            const fallbackTop = Math.max(0, scrollArea.scrollTop);
            pagination.allLoaded = true;
            const topMarker = document.createElement('div');
            topMarker.className = 'chat-top-marker';
            topMarker.textContent = '- Beginning of conversation -';
            topMarker.style.cssText = 'text-align:center;padding:12px;font-size:0.78rem;color:var(--text-muted,#8696a0);';
            msgContainer.insertBefore(topMarker, msgContainer.firstChild);
            await settleScrollAnchor(anchor, fallbackTop, 1);
        } else {
            const seenRowids = new Set((window.currentChatMessages || []).map(m => m.rowid));
            const deduped = older.filter(m => !seenRowids.has(m.rowid));

            if (deduped.length > 0) {
                const anchor = captureScrollAnchor();
                const prevScrollHeight = scrollArea.scrollHeight;
                const fallbackTop = Math.max(0, scrollArea.scrollTop);

                pagination.oldestRowid = deduped[0].rowid;
                window.currentChatMessages = [...deduped, ...window.currentChatMessages];
                await hydrateQuoteCache(deduped, pagination.chatJid);
                await hydrateParticipantNameCache(deduped);
                await hydrateMessageMentions(deduped, pagination.chatJid);
                await hydrateMessageReactions(deduped);
                await hydrateMessageStatuses(deduped);
                const frag = buildMessageFragment(deduped);
                suppressFragmentEnterAnimation(frag);
                msgContainer.insertBefore(frag, msgContainer.firstChild);

                trimRenderedMessages('end');

                await settleScrollAnchor(anchor, Math.max(0, fallbackTop + scrollArea.scrollHeight - prevScrollHeight), 1);
            }
        }
    } catch (err) {
        if (loadingIndicator.isConnected) loadingIndicator.remove();
        showToast('Failed to load older messages: ' + err, 'error');
    } finally {
        if (loadingIndicator.isConnected) loadingIndicator.remove();
        pagination.isLoading = false;
        holdScrollPaging(240);
    }
}

async function loadNewerMessages() {
    pagination.isLoading = true;
    holdScrollPaging(700);
    const distanceFromBottom = scrollArea
        ? scrollArea.scrollHeight - scrollArea.scrollTop - scrollArea.clientHeight
        : 0;

    try {
        const newer = await invoke('get_messages_after_rowid', {
            chatJid: pagination.chatJid,
            limit: PAGE_SIZE,
            afterRowid: pagination.newestRowid,
        });

        if (newer.length < PAGE_SIZE) pagination.allNewerLoaded = true;

        if (newer.length > 0) {
            const seenRowids = new Set((window.currentChatMessages || []).map(m => m.rowid));
            const deduped = newer.filter(m => !seenRowids.has(m.rowid));

            if (deduped.length > 0) {
                pagination.newestRowid = deduped[deduped.length - 1].rowid;
                window.currentChatMessages = [...window.currentChatMessages, ...deduped];
                await hydrateQuoteCache(deduped, pagination.chatJid);
                await hydrateParticipantNameCache(deduped);
                await hydrateMessageMentions(deduped, pagination.chatJid);
                await hydrateMessageReactions(deduped);
                await hydrateMessageStatuses(deduped);
                const frag = buildMessageFragment(deduped);
                msgContainer.appendChild(frag);

                trimRenderedMessages('start');
                if (scrollArea) {
                    const targetTop = scrollTopForBottomDistance({
                        scrollHeight: scrollArea.scrollHeight,
                        clientHeight: scrollArea.clientHeight,
                        distanceFromBottom,
                    });
                    scrollArea.scrollTop = targetTop;
                    await nextAnimationFrame();
                    scrollArea.scrollTop = scrollTopForBottomDistance({
                        scrollHeight: scrollArea.scrollHeight,
                        clientHeight: scrollArea.clientHeight,
                        distanceFromBottom,
                    });
                }
            }
        } else {
            pagination.allNewerLoaded = true;
        }
    } catch (err) {
        showToast('Failed to load newer messages: ' + err, 'error');
    } finally {
        pagination.isLoading = false;
        holdScrollPaging(180);
    }
}

// ---------------------------------------------------------------------------
// Messages
// ---------------------------------------------------------------------------

/**
 * Open a chat using paginated loading:
 *  - Loads only the last PAGE_SIZE messages initially.
 *  - Older messages are loaded on scroll-up via loadOlderMessages().
 *  - For search jumps that need a specific message, pass forceFullLoad=true.
 */
async function openChat(chat, divEl, skipScroll = false, targetRowid = null) {
    document.querySelectorAll('.chat-item').forEach(el => el.classList.remove('active'));
    if (divEl) divEl.classList.add('active');

    activeChatId = chat.chat_jid;
    btnCloseChat.style.display = 'block';
    if (btnExportChat) btnExportChat.style.display = 'block';

    const name = chatDisplayName(chat);
    activeChatName.textContent = name;
    activeChatStatus.textContent = chat.is_group
        ? `Group · ${chat.message_count} messages`
        : `${chat.message_count} messages · ${chat.sent_count} sent · ${chat.recv_count} received`;

    const initials = name.slice(0, 2).toUpperCase();
    activeChatPic.setAttribute('data-initials', initials);
    activeChatPic.src = '';
    loadProfilePic(chat.chat_jid, activeChatPic);

    msgContainer.innerHTML = '<div class="empty-state" style="flex-direction:column;"><div class="spinner"></div><div style="margin-top:12px;color:var(--text-muted);">Loading conversation...</div></div>';

    pagination = {
        chatJid: chat.chat_jid,
        oldestRowid: null,
        newestRowid: null,
        allLoaded: false,
        allNewerLoaded: true,
        isLoading: false,
    };
    window.messageWindowMode = false;
    quoteCache = { chatJid: chat.chat_jid, byStanza: new Map() };
    messageStatusCache = new Map();
    messageMentionCache = new Map();
    messageReactionCache = new Map();
    currentAlbumGroups = new Map();

    try {
        let messages;

        if (targetRowid) {
            const win = await invoke('get_messages_around_rowid', {
                chatJid: chat.chat_jid,
                rowid: targetRowid,
                before: TARGET_WINDOW_BEFORE,
                after: TARGET_WINDOW_AFTER,
            });
            messages = win.messages || [];
            window.messageWindowMode = true;

            pagination.allLoaded = !win.has_older;
            pagination.allNewerLoaded = !win.has_newer;

            if (messages.length > 0) {
                pagination.oldestRowid = messages[0].rowid;
                pagination.newestRowid = messages[messages.length - 1].rowid;
            }
        } else {
            messages = await invoke('get_messages_paginated', {
                chatJid: chat.chat_jid,
                limit: PAGE_SIZE,
                beforeRowid: null,
            });

            if (messages.length < PAGE_SIZE) pagination.allLoaded = true;
            if (messages.length > 0) {
                pagination.oldestRowid = messages[0].rowid;
                pagination.newestRowid = messages[messages.length - 1].rowid;
            }
        }

        const deduped = deduplicateMessages(messages);
        window.currentChatMessages = deduped;
        await hydrateQuoteCache(deduped, chat.chat_jid);
        await hydrateParticipantNameCache(deduped);
        await hydrateMessageMentions(deduped, chat.chat_jid);
        await hydrateMessageReactions(deduped);
        await hydrateMessageStatuses(deduped);

        if (pagination.allLoaded && !targetRowid) {
            const topMarker = document.createElement('div');
            topMarker.className = 'chat-top-marker';
            topMarker.textContent = '— Beginning of conversation —';
            topMarker.style.cssText = 'text-align:center;padding:12px;font-size:0.78rem;color:var(--text-muted,#8696a0);';
            msgContainer.innerHTML = '';
            msgContainer.appendChild(topMarker);
            const frag = buildMessageFragment(deduped);
            msgContainer.appendChild(frag);
        } else {
            await renderMessages(deduped, false, null, skipScroll);
        }

        if (targetRowid) {
            holdScrollPaging(350);
            centerMessageByRowid(targetRowid, false);
        }

    } catch (e) {
        msgContainer.innerHTML = `<div class="empty-state error">Error: ${escapeHtml(String(e))}</div>`;
    }
}

btnCloseChat.addEventListener('click', e => {
    e.stopPropagation();
    activeChatId = null;
    btnCloseChat.style.display = 'none';
    if (btnExportChat) btnExportChat.style.display = 'none';
    activeChatName.textContent = 'Select a chat';
    activeChatStatus.textContent = '';
    activeChatPic.src = '';
    activeChatPic.removeAttribute('data-initials');
    msgContainer.innerHTML = '<div class="empty-state">Select a conversation to start reading.</div>';
    document.querySelectorAll('.chat-item').forEach(el => el.classList.remove('active'));
    pagination = { chatJid: null, oldestRowid: null, newestRowid: null, allLoaded: false, allNewerLoaded: true, isLoading: false };
    quoteCache = { chatJid: null, byStanza: new Map() };
    messageStatusCache = new Map();
    messageMentionCache = new Map();
    messageReactionCache = new Map();
    currentAlbumGroups = new Map();
    window.currentChatMessages = [];
    window.messageWindowMode = false;
});

chatHeaderClickable.addEventListener('click', () => {
    if (activeChatId) openContactInfo(activeChatId);
});

// ---------------------------------------------------------------------------
// Scroll a target message into centered view.
// Search-result jumps load a bounded message window around the target rowid,
// then wait until the target bubble is painted before measuring its scroll
// position. This avoids both full-chat loads and misplaced native scrolls.
// ---------------------------------------------------------------------------
async function jumpToMessageInChat(chatJid, tgtRowid, keyword = null) {
    const targetSelector = `.msg-bubble[data-rowid="${tgtRowid}"], .msg-album-tile[data-rowid="${tgtRowid}"]`;
    const chatAlreadyOpen = (activeChatId === chatJid);
    let loadedTargetWindow = false;

    if (!chatAlreadyOpen || !document.querySelector(targetSelector)) {
        const fullChat = allChats.find(c => c.chat_jid === chatJid) || { chat_jid: chatJid };
        const sidebarItem = chatItemForJid(chatJid);
        await openChat(fullChat, sidebarItem, true, tgtRowid);
        loadedTargetWindow = true;
    }

    const doHighlightAndScroll = () => {
        const targetEl = document.querySelector(targetSelector);
        if (!targetEl) {
            console.warn(`[Jump] Target message rowid=${tgtRowid} not found in DOM after load.`);
            return;
        }

        // Newly loaded target windows are centered synchronously by openChat().
        // Keep that path immediate so reply jumps do not visibly overshoot above
        // the message before settling back onto the target.
        const highlightEl = targetEl.closest('.msg-bubble') || targetEl;
        centerElementInMessagePane(highlightEl, !loadedTargetWindow);
        flashMessageHighlight(highlightEl);
    };

    // If already rendered, run immediately after two animation frames
    if (document.querySelector(targetSelector)) {
        requestAnimationFrame(() => requestAnimationFrame(doHighlightAndScroll));
        return;
    }

    // Otherwise wait for the DOM to receive the bubble via MutationObserver
    const observer = new MutationObserver(() => {
        if (document.querySelector(targetSelector)) {
            observer.disconnect();
            clearTimeout(fallbackTimer);
            requestAnimationFrame(() => requestAnimationFrame(doHighlightAndScroll));
        }
    });
    observer.observe(msgContainer, { childList: true, subtree: true });
    const fallbackTimer = setTimeout(() => { observer.disconnect(); doHighlightAndScroll(); }, 3500);
}

// ---------------------------------------------------------------------------
// Deduplicate message records by rowid before rendering.
// Removes duplicate message records that may arise from the FTS + IndexedDB
// merge in waren6.py (e.g., fuzzy ±2s timestamp matching can sometimes
// insert the same message twice with different rowids).
// ---------------------------------------------------------------------------
function deduplicateMessages(messages) {
    const seen = new Set();
    return messages.filter(m => {
        if (seen.has(m.rowid)) {
            debugLog(`Deduplicated message rowid=${m.rowid} ts=${m.timestamp} text="${(m.text || '').slice(0, 30)}"`);
            return false;
        }
        seen.add(m.rowid);
        return true;
    });
}

// ── Read More Helper ────────────────────────────────────────────────────────
function renderMessageText(fullText, msg = null) {
    return renderWhatsAppText(fullText, {
        contactLinks: true,
        contactResolver: resolveContactToken,
        mentions: msg ? mentionsForMessage(msg) : [],
    });
}

function formatLongText(fullText, chunkCount, rowid, msg = null) {
    const limit = chunkCount * 700;
    if (fullText.length <= limit) {
        return renderMessageText(fullText, msg);
    } else {
        let cutIndex = limit;
        while (cutIndex > limit - 50 && fullText[cutIndex] !== ' ' && fullText[cutIndex] !== '\n') {
            cutIndex--;
        }
        if (cutIndex <= limit - 50) cutIndex = limit;

        const chunk = fullText.slice(0, cutIndex);
        return renderMessageText(chunk, msg) +
            `<span class="read-more-dots">... </span><div style="margin-top:2px"><span class="read-more-text-btn" data-rowid="${rowid}" data-chunks="${chunkCount + 1}">Read more</span></div>`;
    }
}

async function openMessageInfo(msgKey) {
    if (!msgKey || !messageInfoModal || !messageInfoBody) return;
    messageInfoBody.innerHTML = '<div class="message-info-empty">Loading message info...</div>';
    openOverlay(messageInfoModal);
    try {
        const receipts = await invoke('get_message_receipts', { msgKey });
        messageInfoBody.innerHTML = renderMessageInfoContent(receipts || [], {
            formatTime: formatReceiptDateTime,
            selfPhone: extractionInfo?.self_phone,
        });
    } catch (err) {
        messageInfoBody.innerHTML = `<div class="message-info-empty error">Could not load message info: ${escapeHtml(String(err))}</div>`;
    }
}

async function openMessageEditInfo(msgKey) {
    if (!msgKey || !messageEditModal || !messageEditBody) return;
    messageEditBody.innerHTML = '<div class="message-info-empty">Loading edit evidence...</div>';
    openOverlay(messageEditModal);
    try {
        const history = await invoke('get_message_edit_history', { msgKey });
        messageEditBody.innerHTML = renderEditHistoryContent(history || {}, {
            formatTime: formatReceiptDateTime,
        });
    } catch (err) {
        messageEditBody.innerHTML = `<div class="message-info-empty error">Could not load edit evidence: ${escapeHtml(String(err))}</div>`;
    }
}

function openReactionInfo(msgKey) {
    if (!msgKey || !reactionInfoModal || !reactionInfoBody) return;
    const reactions = messageReactionCache.get(msgKey) || [];
    reactionInfoBody.innerHTML = renderReactionDetailsContent(reactions, {
        formatTime: formatReceiptDateTime,
        selfPhone: extractionInfo?.self_phone,
    });
    openOverlay(reactionInfoModal);
}

// Global click delegation for expanding Read More + reply quote scroll
document.addEventListener('click', async e => {
    const editInfoBtn = e.target.closest('.msg-edit-info-btn[data-message-edit-key]');
    if (editInfoBtn) {
        e.preventDefault();
        e.stopPropagation();
        await openMessageEditInfo(editInfoBtn.dataset.messageEditKey);
        return;
    }

    const messageInfoTick = e.target.closest('.msg-tick[data-message-info-key]');
    if (messageInfoTick) {
        e.preventDefault();
        e.stopPropagation();
        await openMessageInfo(messageInfoTick.dataset.messageInfoKey);
        return;
    }

    const reactionSummary = e.target.closest('.msg-reactions[data-reaction-msg-key], .album-reaction-chip[data-reaction-msg-key]');
    if (reactionSummary) {
        e.preventDefault();
        e.stopPropagation();
        openReactionInfo(reactionSummary.dataset.reactionMsgKey);
        return;
    }

    const albumCard = e.target.closest('.msg-album-card[data-album-id]');
    if (albumCard) {
        e.preventDefault();
        e.stopPropagation();
        openAlbumInfo(albumCard.dataset.albumId);
        return;
    }

    const contactLink = e.target.closest('.msg-contact-link[data-contact-jid]');
    if (contactLink) {
        e.preventDefault();
        e.stopPropagation();
        await openContactInfo(contactLink.dataset.contactJid);
        return;
    }

    // ── Reply quote box click → scroll to original message ───────────────
    const quoteBox = e.target.closest('.msg-reply-box[data-quote-rowid]');
    if (quoteBox) {
        e.preventDefault();
        e.stopPropagation();

        const targetRowid = Number(quoteBox.getAttribute('data-quote-rowid'));
        if (activeChatId && Number.isFinite(targetRowid)) {
            await jumpToMessageInChat(activeChatId, targetRowid);
        }
        return;
    }

    if (e.target.classList.contains('read-more-text-btn')) {
        const rowid = parseInt(e.target.getAttribute('data-rowid'));
        const chunks = parseInt(e.target.getAttribute('data-chunks'));

        let msg = (window.currentChatMessages || []).find(m => m.rowid === rowid);
        if (!msg && window.searchResultsCache) {
            let r = window.searchResultsCache.find(r => r.msg.rowid === rowid);
            if (r) msg = r.msg;
        }

        if (msg && msg.text) {
            const targetEl = document.getElementById(`msg-text-${rowid}`);
            if (targetEl) {
                targetEl.innerHTML = formatLongText(msg.text.trim(), chunks, rowid, msg);
            }
        }
    }
});

document.addEventListener('keydown', async e => {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    const editInfoBtn = e.target.closest?.('.msg-edit-info-btn[data-message-edit-key]');
    if (editInfoBtn) {
        e.preventDefault();
        await openMessageEditInfo(editInfoBtn.dataset.messageEditKey);
        return;
    }

    const messageInfoTick = e.target.closest?.('.msg-tick[data-message-info-key]');
    if (messageInfoTick) {
        e.preventDefault();
        await openMessageInfo(messageInfoTick.dataset.messageInfoKey);
        return;
    }

    const reactionSummary = e.target.closest?.('.msg-reactions[data-reaction-msg-key], .album-reaction-chip[data-reaction-msg-key]');
    if (reactionSummary) {
        e.preventDefault();
        openReactionInfo(reactionSummary.dataset.reactionMsgKey);
        return;
    }

    const albumCard = e.target.closest?.('.msg-album-card[data-album-id]');
    if (albumCard) {
        e.preventDefault();
        openAlbumInfo(albumCard.dataset.albumId);
        return;
    }

    const contactLink = e.target.closest?.('.msg-contact-link[data-contact-jid]');
    if (!contactLink) return;
    e.preventDefault();
    await openContactInfo(contactLink.dataset.contactJid);
});

btnCloseMessageInfo?.addEventListener('click', () => closeOverlay(messageInfoModal));
messageInfoModal?.addEventListener('click', e => {
    if (e.target === messageInfoModal) closeOverlay(messageInfoModal);
});

btnCloseMessageEdit?.addEventListener('click', () => closeOverlay(messageEditModal));
messageEditModal?.addEventListener('click', e => {
    if (e.target === messageEditModal) closeOverlay(messageEditModal);
});

btnCloseReactionInfo?.addEventListener('click', () => closeOverlay(reactionInfoModal));
reactionInfoModal?.addEventListener('click', e => {
    if (e.target === reactionInfoModal) closeOverlay(reactionInfoModal);
});

btnCloseAlbumInfo?.addEventListener('click', () => closeOverlay(albumInfoModal));
albumInfoModal?.addEventListener('click', e => {
    if (e.target === albumInfoModal) closeOverlay(albumInfoModal);
});

function isMediaMsg(msg) {
    return isMediaMessage(msg);
}

function mediaIcon(msgType) {
    return ({
        image: '🖼️',
        video: '🎥',
        sticker: '🎭',
        ptt: '🎤',
        audio: '🎵',
        ptv: '🎥',
        document: '📄',
        album: '🖼️',
    })[msgType] || '📎';
}

function mediaTypeLabel(msgType) {
    return ({
        image: 'Image',
        video: 'Video',
        sticker: 'Sticker',
        ptt: 'Voice message',
        audio: 'Audio',
        ptv: 'Video note',
        document: 'Document',
        album: 'Album',
    })[msgType] || (msgType || 'Media');
}

function extensionFromMime(mimeType) {
    if (!mimeType || !mimeType.includes('/')) return '';
    const raw = mimeType.split('/').pop().split(';')[0].trim().toUpperCase();
    const normalized = {
        JPEG: 'JPG',
        MPEG: 'MP3',
        OGG: 'OGG',
        WEBP: 'WEBP',
        MP4: 'MP4',
        PDF: 'PDF',
        PLAIN: 'TXT',
    }[raw] || raw;
    return normalized.replace(/^X-/, '');
}

function isBase64MediaText(rawText) {
    const text = String(rawText || '').trim();
    return !!text && (
        /^[A-Za-z0-9+/]{120,}={0,2}$/.test(text) ||
        text.startsWith('/9j/') ||
        text.startsWith('iVBOR')
    );
}

function mediaAbsolutePath(msg) {
    const rel = msg?.media_case_path;
    if (!rel) return '';
    if (/^[A-Za-z]:[\\/]/.test(rel) || rel.startsWith('\\\\')) return rel;
    if (!currentDbPath) return rel;
    const base = currentDbPath.replace(/[\\/][^\\/]+$/, '');
    return `${base}\\${String(rel).replace(/\//g, '\\')}`;
}

function renderMediaCard(msg, rawText) {
    const msgType = mediaDisplayKind(msg);
    const icon = mediaIcon(msgType);
    const ext = extensionFromMime(msg.media_mime_type);
    const title = msg.media_filename || ext || mediaTypeLabel(msgType);
    const detailParts = [];

    if (!msg.media_filename && ext && ext !== title) detailParts.push(ext);
    if (msg.media_mime_type) detailParts.push(msg.media_mime_type);
    if (msg.media_size) detailParts.push(formatBytes(msg.media_size));
    if (msg.media_status && msg.media_status !== 'local_present') detailParts.push(msg.media_status.replace(/_/g, ' '));

    const detail = detailParts.filter(Boolean).join(' · ');
    const captionText = visibleMediaCaption(rawText);
    const titleHtml = escapeHtml(String(title || mediaTypeLabel(msgType)));
    const detailHtml = detail ? `<span class="msg-media-detail">${escapeHtml(detail)}</span>` : '';
    const absMediaPath = mediaAbsolutePath(msg);
    const canPreview = absMediaPath && msg.media_status === 'local_present';
    const previewUrl = canPreview ? convertFileSrc(absMediaPath) : '';
    const previewHtml = canPreview && msgType === 'image'
        ? `<img class="msg-media-preview" src="${escapeAttr(previewUrl)}" alt="">`
        : (canPreview && msgType === 'video'
            ? `<video class="msg-media-preview" src="${escapeAttr(previewUrl)}" controls preload="metadata"></video>`
            : '');
    const hashHtml = msg.media_sha256
        ? `<span class="msg-media-hash">SHA-256 ${escapeHtml(String(msg.media_sha256).slice(0, 16))}...</span>`
        : '';
    const pathHtml = absMediaPath
        ? `<span class="msg-media-path" title="${escapeAttr(absMediaPath)}">${escapeHtml(msg.media_case_path || absMediaPath)}</span>`
        : '';
    const captionHtml = captionText && !isBase64MediaText(captionText) && captionText.length < 50000
        ? `<div class="msg-text msg-media-caption" id="msg-text-${msg.rowid}">${formatLongText(captionText, 1, msg.rowid, msg)}</div>`
        : '';

    return `
        <div class="msg-media-card">
            ${previewHtml}
            <span class="msg-media-icon">${icon}</span>
            <span class="msg-media-copy">
                <span class="msg-media-title">${titleHtml}</span>
                ${detailHtml}
                ${hashHtml}
                ${pathHtml}
            </span>
        </div>
        ${captionHtml}
    `;
}

function mediaPreviewMarkup(msg, className, { controls = false, lazy = false } = {}) {
    const kind = mediaDisplayKind(msg);
    const absMediaPath = mediaAbsolutePath(msg);
    const canPreview = absMediaPath && msg.media_status === 'local_present';
    if (!canPreview) return '';

    const src = convertFileSrc(absMediaPath);
    const lazyAttr = lazy ? ' loading="lazy"' : '';
    if (kind === 'image' || kind === 'sticker') {
        return `<img class="${className}" src="${escapeAttr(src)}" alt=""${lazyAttr}>`;
    }
    if (kind === 'video' || kind === 'ptv') {
        return `<video class="${className}" src="${escapeAttr(src)}" ${controls ? 'controls' : ''} preload="metadata" muted></video>`;
    }
    return '';
}

function albumReactionChip(msg) {
    const msgKey = msg?.msg_key || '';
    if (!msgKey) return '';
    const summary = summarizeReactions(messageReactionCache.get(msgKey) || [], {
        selfPhone: extractionInfo?.self_phone,
    });
    if (!summary.length) return '';

    const total = summary.reduce((count, item) => count + item.count, 0);
    const first = summary[0];
    const label = summary.map(item => `${item.text}${item.count > 1 ? ` ${item.count}` : ''}`).join(', ');
    return `
        <button type="button" class="album-reaction-chip" data-reaction-msg-key="${escapeAttr(msgKey)}" title="${escapeAttr(label)}">
            <span>${escapeHtml(first.text)}</span>${total > 1 ? `<span>${total}</span>` : ''}
        </button>
    `;
}

function albumItemTitle(msg) {
    const kind = mediaDisplayKind(msg);
    return msg.media_filename || extensionFromMime(msg.media_mime_type) || mediaTypeLabel(kind);
}

function albumItemDetail(msg) {
    return [
        msg.media_mime_type,
        msg.media_size ? formatBytes(msg.media_size) : null,
        msg.timestamp ? formatChatClockTime(msg.timestamp) : null,
        msg.media_status && msg.media_status !== 'local_present' ? msg.media_status.replace(/_/g, ' ') : null,
    ].filter(Boolean).join(' · ');
}

function renderAlbumTile(msg, index, total, { detail = false } = {}) {
    const kind = mediaDisplayKind(msg);
    const preview = mediaPreviewMarkup(msg, detail ? 'album-detail-preview' : 'msg-album-preview', {
        controls: detail,
        lazy: true,
    });
    const overflowCount = !detail && index === 3 && total > 4 ? total - 4 : 0;
    const detailLine = albumItemDetail(msg);
    const title = albumItemTitle(msg);

    return `
        <div class="${detail ? 'album-detail-item' : 'msg-album-tile'} media-kind-${escapeAttr(kind)}"
             data-rowid="${escapeAttr(msg.rowid)}"
             data-msg-key="${escapeAttr(msg.msg_key || '')}">
            <div class="${detail ? 'album-detail-media' : 'msg-album-media'} ${preview ? 'has-preview' : ''}">
                ${preview || `<span class="msg-album-icon">${mediaIcon(kind)}</span>`}
                ${overflowCount ? `<span class="msg-album-overflow">+${overflowCount}</span>` : ''}
                ${albumReactionChip(msg)}
            </div>
            ${detail ? `
                <div class="album-detail-copy">
                    <span class="album-detail-title">${escapeHtml(title)}</span>
                    ${detailLine ? `<span class="album-detail-meta">${escapeHtml(detailLine)}</span>` : ''}
                </div>
            ` : ''}
        </div>
    `;
}

function renderAlbumBubble(albumGroup) {
    const messages = albumGroup.messages || [];
    const count = messages.length;
    currentAlbumGroups.set(albumGroup.id, albumGroup);

    return `
        <div class="msg-album-card" role="button" tabindex="0" data-album-id="${escapeAttr(albumGroup.id)}" title="Open album">
            <div class="msg-album-grid msg-album-count-${Math.min(count, 4)}">
                ${messages.slice(0, 4).map((item, index) => renderAlbumTile(item, index, count)).join('')}
            </div>
            <div class="msg-album-footer">
                <span>Album</span>
                <span>${count.toLocaleString()} ${count === 1 ? 'item' : 'items'}</span>
            </div>
        </div>
    `;
}

function renderAlbumDetailContent(albumGroup) {
    const messages = albumGroup?.messages || [];
    if (!messages.length) {
        return '<div class="reaction-detail-empty">No album media rows were found for this group.</div>';
    }

    const firstTs = messages[0]?.timestamp ? formatReceiptDateTime(messages[0].timestamp) : '';
    return `
        <div class="album-detail-summary">
            <span>${messages.length.toLocaleString()} ${messages.length === 1 ? 'item' : 'items'}</span>
            ${firstTs ? `<span>${escapeHtml(firstTs)}</span>` : ''}
        </div>
        <div class="album-detail-grid">
            ${messages.map((item, index) => renderAlbumTile(item, index, messages.length, { detail: true })).join('')}
        </div>
    `;
}

function openAlbumInfo(albumId) {
    const group = currentAlbumGroups.get(albumId);
    if (!group || !albumInfoModal || !albumInfoBody) return;
    const count = group.messages?.length || 0;
    if (albumInfoTitle) {
        albumInfoTitle.textContent = `Album · ${count.toLocaleString()} ${count === 1 ? 'item' : 'items'}`;
    }
    albumInfoBody.innerHTML = renderAlbumDetailContent(group);
    openOverlay(albumInfoModal);
}

function quoteSummaryForMessage(msg) {
    if (!msg) return null;
    const text = msg.text ? msg.text.replace(/\n/g, ' ').trim() : '';
    if (text) return escapeHtml(text.slice(0, 120));

    if (isMediaMsg(msg)) {
        const ext = extensionFromMime(msg.media_mime_type);
        const label = msg.media_filename || ext || mediaTypeLabel(msg.msg_type);
        const parts = [label, msg.media_mime_type, msg.media_size ? formatBytes(msg.media_size) : null]
            .filter(Boolean)
            .join(' · ');
        return `${mediaIcon(msg.msg_type)} ${escapeHtml(parts || mediaTypeLabel(msg.msg_type))}`;
    }

    return msg.msg_type && msg.msg_type !== 'chat'
        ? `[${escapeHtml(msg.msg_type)}]`
        : null;
}

function findLoadedQuote(stanzaId) {
    return (window.currentChatMessages || []).find(
        m => m.msg_id === stanzaId || m.msg_key === stanzaId
    ) || null;
}

function normalizePhoneLabel(value) {
    return formatPhoneNumber(value);
}

function cleanContactName(value) {
    const name = (value || '').trim();
    return name || null;
}

function cacheParticipantResolution(jid, resolved) {
    const payload = resolved
        ? {
            name: cleanContactName(resolved.name),
            phone: normalizePhoneLabel(resolved.phone),
            jid: resolved.jid || jid,
        }
        : null;

    const keys = new Set([
        ...participantCacheKeys(jid),
        ...participantCacheKeys(resolved?.jid),
        rawParticipantId(resolved?.phone),
    ].filter(Boolean));

    for (const key of keys) {
        participantNameCache.set(key, payload);
    }
}

async function hydrateParticipantNameCache(messages) {
    if (!Array.isArray(messages) || messages.length === 0) return;

    const participants = [...new Set(messages
        .flatMap(msg => [
            (msg.quoted_participant || '').trim(),
            msg.is_group ? (msg.sender_jid || '').trim() : '',
            ...participantCandidatesFromText(msg.text || ''),
        ])
        .filter(Boolean))];

    const missing = participants.filter(jid =>
        participantCacheKeys(jid).every(key => !participantNameCache.has(key))
    );
    if (!missing.length) return;

    try {
        const rows = await invoke('resolve_participant_names', { jids: missing });
        const returned = new Set();
        for (const row of rows || []) {
            const jid = row?.input_jid;
            if (!jid) continue;
            cacheParticipantResolution(jid, row.resolved || null);
            returned.add(jid);
        }
        for (const jid of missing) {
            if (!returned.has(jid)) cacheParticipantResolution(jid, null);
        }
    } catch (err) {
        for (const jid of missing) cacheParticipantResolution(jid, null);
        debugLog('Failed to resolve participants', err);
    }
}

function cachedParticipantLabel(jid) {
    for (const key of participantCacheKeys(jid)) {
        if (!participantNameCache.has(key)) continue;
        const cached = participantNameCache.get(key);
        if (cached?.name) return cached.name;
        if (cached?.phone) return cached.phone;
    }
    return null;
}

function cachedParticipantPayload(jid) {
    for (const key of participantCacheKeys(jid)) {
        if (!participantNameCache.has(key)) continue;
        return participantNameCache.get(key);
    }
    return null;
}

function fallbackParticipantLabel(jid) {
    const raw = rawParticipantId(jid);
    return /^\d+$/.test(raw) ? (formatPhoneNumber(raw) || `+${raw}`) : raw;
}

function resolveContactToken({ token, digits, jid }) {
    const candidateKeys = [
        jid,
        token.replace(/^@(?=\+?\d)/, ''),
        digits,
        `${digits}@lid`,
        `${digits}@c.us`,
        `${digits}@s.whatsapp.net`,
    ];

    for (const candidate of candidateKeys) {
        const payload = cachedParticipantPayload(candidate);
        if (payload?.name || payload?.phone) {
            return {
                jid: payload.jid || candidate,
                label: payload.name || payload.phone,
            };
        }
    }

    return null;
}

function quoteParticipantLabel(msg, origMsg) {
    const participant = msg.quoted_participant;
    if (!participant) return null;
    const qCachedMsg = quoteCache.byStanza.get(msg.quoted_stanza_id);

    if (participantMatchesSelf(participant, {
        selfPhone: extractionInfo?.self_phone,
        quotedOriginal: origMsg || qCachedMsg,
    })) {
        return 'You';
    }

    const qSenderMsg = (window.currentChatMessages || []).find(
        m => m.sender_jid === participant && cleanContactName(m.sender_name)
    );
    if (qSenderMsg?.sender_name) return cleanContactName(qSenderMsg.sender_name);

    if (qCachedMsg?.sender_name) return cleanContactName(qCachedMsg.sender_name);
    if (origMsg?.sender_jid === participant && origMsg?.sender_name) {
        return cleanContactName(origMsg.sender_name);
    }

    const qContact = allChats.find(c =>
        c.chat_jid === participant || rawParticipantId(c.chat_jid) === rawParticipantId(participant)
    );
    if (qContact?.chat_name) return cleanContactName(qContact.chat_name);

    const resolved = cachedParticipantLabel(participant);
    if (resolved) return resolved;

    const phoneMatch = (window.currentChatMessages || []).find(
        m => m.sender_jid === participant && m.sender_phone
    );
    return normalizePhoneLabel(phoneMatch?.sender_phone || qCachedMsg?.sender_phone)
        || fallbackParticipantLabel(participant);
}

function formatChatClockTime(epochSeconds) {
    return formatClockTime(epochSeconds, settings.regionalTime);
}

function formatReceiptDateTime(epochSeconds) {
    return formatExactDateTime(epochSeconds, settings.regionalTime);
}

function formatCallDuration(seconds) {
    const totalSeconds = Number(seconds) || 0;
    if (totalSeconds <= 0) return '';

    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const secs = totalSeconds % 60;

    if (hours > 0) return `${hours}h ${minutes}m`;
    if (minutes > 0) return `${minutes}m ${String(secs).padStart(2, '0')}s`;
    return `${secs}s`;
}

function callOutcomeMeta(msg) {
    const outcome = String(msg.call_outcome || '').toLowerCase();
    const missed = outcome.includes('missed') || outcome === '2' || outcome === 'missed_call';
    const declined = outcome.includes('rejected') || outcome.includes('declined') || outcome === '3';
    const answered = outcome.includes('accepted') || outcome.includes('answered') || outcome === '1' || Number(msg.call_duration) > 0;

    if (missed) return { label: 'Missed', tone: 'missed' };
    if (declined) return { label: 'Declined', tone: 'declined' };
    if (answered) return { label: 'Answered', tone: 'answered' };
    return { label: 'Call', tone: 'neutral' };
}

function renderCallLogContent(msg) {
    const isVideo = msg.is_video_call === 1 || msg.is_video_call === true || String(msg.is_video_call).toLowerCase() === 'true';
    const outcome = callOutcomeMeta(msg);
    const callType = isVideo ? 'Video call' : 'Voice call';
    const title = outcome.label === 'Call' ? callType : `${outcome.label} ${callType.toLowerCase()}`;
    const duration = formatCallDuration(msg.call_duration);
    const iconPath = isVideo
        ? '<path d="M4.5 6.5h8a2 2 0 0 1 2 2v4.2l4-2.4V15l-4-2.4v.9a2 2 0 0 1-2 2h-8a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2Z" fill="currentColor"/>'
        : '<path d="M6.6 4.2 8.4 8c.2.4.1.9-.3 1.2l-1.1.9a12.7 12.7 0 0 0 5 5l.9-1.1c.3-.4.8-.5 1.2-.3l3.8 1.8c.5.2.8.8.7 1.3l-.5 2.2c-.1.6-.6 1-1.2 1A14.8 14.8 0 0 1 2 5.1c0-.6.4-1.1 1-1.2l2.2-.5c.6-.1 1.1.2 1.4.8Z" fill="currentColor"/>';

    return `
        <div class="call-card call-${outcome.tone}">
            <span class="call-icon ${isVideo ? 'call-icon-video' : 'call-icon-voice'}" aria-hidden="true">
                <svg viewBox="0 0 22 22" width="17" height="17">${iconPath}</svg>
            </span>
            <span class="call-copy">
                <span class="call-title">${escapeHtml(title)}</span>
                ${duration ? `<span class="call-detail">Duration ${escapeHtml(duration)}</span>` : ''}
            </span>
        </div>
    `;
}

function renderSystemNotice(msgType, rawText) {
    const meta = systemNoticeMeta(msgType, rawText);
    return `
        <span class="system-notice-content system-${meta.icon}">
            <span class="system-icon" aria-hidden="true"></span>
            <span class="system-copy">
                <span class="system-title">${escapeHtml(meta.title)}</span>
                ${meta.detail && meta.detail !== meta.title ? `<span class="system-detail">${escapeHtml(meta.detail)}</span>` : ''}
            </span>
        </span>
    `;
}

function renderDeletedMessage(rawText) {
    const label = rawText || 'This message was deleted';
    return `
        <span class="deleted-message-content">
            <span class="deleted-message-icon" aria-hidden="true"></span>
            <span>${escapeHtml(label)}</span>
        </span>
    `;
}

async function hydrateQuoteCache(messages, chatJid = activeChatId) {
    if (!chatJid || !Array.isArray(messages) || messages.length === 0) return;

    if (quoteCache.chatJid !== chatJid) {
        quoteCache = { chatJid, byStanza: new Map() };
    }

    const missing = [];
    for (const msg of messages) {
        const stanzaId = (msg.quoted_stanza_id || '').trim();
        if (!stanzaId || quoteCache.byStanza.has(stanzaId)) continue;
        if (findLoadedQuote(stanzaId)) continue;
        missing.push(stanzaId);
    }

    const stanzaIds = [...new Set(missing)];
    if (!stanzaIds.length) return;

    try {
        const resolved = await invoke('get_messages_by_stanza_ids', {
            chatJid,
            stanzaIds,
        });
        const found = new Set();
        for (const msg of resolved || []) {
            if (msg.msg_id) {
                quoteCache.byStanza.set(msg.msg_id, msg);
                found.add(msg.msg_id);
            }
            if (msg.msg_key) {
                quoteCache.byStanza.set(msg.msg_key, msg);
                found.add(msg.msg_key);
            }
        }
        for (const stanzaId of stanzaIds) {
            if (!found.has(stanzaId) && !quoteCache.byStanza.has(stanzaId)) {
                quoteCache.byStanza.set(stanzaId, null);
            }
        }
    } catch (err) {
        console.warn('Failed to hydrate quoted messages:', err);
    }
}

async function hydrateMessageStatuses(messages) {
    if (!Array.isArray(messages) || messages.length === 0) return;

    const keys = [...new Set(messages
        .filter(msg => msg?.from_me === 1 && msg?.msg_key && String(msg.msg_type || '').toLowerCase() !== 'call_log')
        .map(msg => msg.msg_key))];
    const missing = keys.filter(key => !messageStatusCache.has(key));
    if (!missing.length) return;

    try {
        const statuses = await invoke('get_message_statuses', { msgKeys: missing });
        const returned = new Set();
        for (const item of statuses || []) {
            if (!item?.msg_key) continue;
            messageStatusCache.set(item.msg_key, item.status || 'sent');
            returned.add(item.msg_key);
        }
        for (const key of missing) {
            if (!returned.has(key)) messageStatusCache.set(key, 'sent');
        }
    } catch (err) {
        for (const key of missing) messageStatusCache.set(key, 'sent');
        console.warn('Failed to hydrate message receipt statuses:', err);
    }
}

async function groupParticipantsForMentions(chatJid) {
    if (!chatJid || !String(chatJid).includes('@g.us')) return [];
    if (groupParticipantMentionCache.has(chatJid)) {
        return groupParticipantMentionCache.get(chatJid) || [];
    }

    try {
        const participants = await invoke('get_group_participants', { groupJid: chatJid });
        const list = Array.isArray(participants) ? participants : [];
        groupParticipantMentionCache.set(chatJid, list);
        for (const participant of list) {
            const jid = participant.participant_lid || participant.participant_jid || participant.jid;
            if (jid) {
                cacheParticipantResolution(jid, {
                    name: participant.participant_name,
                    phone: participant.participant_phone,
                    jid,
                });
            }
            if (participant.participant_phone) {
                const phoneJid = `${String(participant.participant_phone).replace(/\D/g, '')}@c.us`;
                cacheParticipantResolution(phoneJid, {
                    name: participant.participant_name,
                    phone: participant.participant_phone,
                    jid: jid || phoneJid,
                });
            }
        }
        return list;
    } catch (err) {
        groupParticipantMentionCache.set(chatJid, []);
        debugLog('Failed to hydrate group participants for mentions', chatJid, err);
        return [];
    }
}

async function hydrateMessageMentions(messages, chatJid = activeChatId) {
    if (!Array.isArray(messages) || messages.length === 0) return;

    const keys = [...new Set(messages
        .map(msg => msg?.msg_key)
        .filter(Boolean))];
    const missing = keys.filter(key => !messageMentionCache.has(key));

    if (missing.length) {
        try {
            const rows = await invoke('get_message_mentions_for_messages', { msgKeys: missing });
            const grouped = new Map();
            for (const row of rows || []) {
                if (!row?.msg_key) continue;
                if (!grouped.has(row.msg_key)) grouped.set(row.msg_key, []);
                grouped.get(row.msg_key).push(row);
            }
            for (const key of missing) {
                messageMentionCache.set(key, grouped.get(key) || []);
            }
        } catch (err) {
            for (const key of missing) messageMentionCache.set(key, []);
            debugLog('Failed to hydrate message mentions:', err);
        }
    }

    if (String(chatJid || '').includes('@g.us') && messages.some(msg => String(msg?.text || '').includes('@'))) {
        await groupParticipantsForMentions(chatJid);
    }
}

async function hydrateMessageReactions(messages) {
    if (!Array.isArray(messages) || messages.length === 0) return;

    const keys = [...new Set(messages
        .map(msg => msg?.msg_key)
        .filter(Boolean))];
    const missing = keys.filter(key => !messageReactionCache.has(key));
    if (!missing.length) return;

    try {
        const rows = await invoke('get_reactions_for_messages', { msgKeys: missing });
        const grouped = new Map();
        for (const row of rows || []) {
            if (!row?.parent_msg_key) continue;
            if (!grouped.has(row.parent_msg_key)) grouped.set(row.parent_msg_key, []);
            grouped.get(row.parent_msg_key).push(row);
        }
        for (const key of missing) {
            messageReactionCache.set(key, grouped.get(key) || []);
        }
    } catch (err) {
        for (const key of missing) messageReactionCache.set(key, []);
        debugLog('Failed to hydrate message reactions:', err);
    }
}

function mentionsForMessage(msg) {
    const extracted = msg?.msg_key ? (messageMentionCache.get(msg.msg_key) || []) : [];
    if (extracted.length) return extracted;
    if (!msg?.is_group || !msg?.text || !String(msg.text).includes('@')) return [];
    const participants = groupParticipantMentionCache.get(msg.chat_jid || activeChatId) || [];
    return inferMentionsFromText(msg.text, participants);
}

// ---------------------------------------------------------------------------
// Shared renderer for both initial load and prepend.
// ---------------------------------------------------------------------------
function buildMessageFragment(messages) {
    const fragment = document.createDocumentFragment();
    let lastDateStr = '';

    // Gather date separators already in the DOM so we don't emit duplicates
    // when prepending (only relevant for the first prepend batch)
    const existingDates = new Set(
        Array.from(document.querySelectorAll('.date-separator')).map(el => el.textContent)
    );

    const renderItems = buildAlbumRenderItems(messages);

    renderItems.forEach(item => {
        const albumGroup = item.type === 'album' ? item : null;
        const msg = albumGroup
            ? (albumGroup.marker || albumGroup.messages[0] || albumGroup.sourceMessages?.[0])
            : item.message;
        const metaMsg = albumGroup
            ? (albumGroup.marker || albumGroup.messages[albumGroup.messages.length - 1] || msg)
            : msg;
        if (!msg) return;

        const dateStr = formatDateSeparator(msg.timestamp, settings.regionalTime);

        if (dateStr && dateStr !== lastDateStr && !existingDates.has(dateStr)) {
            const sep = document.createElement('div');
            sep.className = 'date-separator';
            sep.textContent = dateStr;
            fragment.appendChild(sep);
            lastDateStr = dateStr;
            existingDates.add(dateStr);
        } else if (dateStr) {
            lastDateStr = dateStr;
        }

        // Determine direction
        const fromMe = msg.from_me;
        const isSent = fromMe === 1;
        const isUnknown = fromMe === null || fromMe === undefined;
        const senderIsSelf = [
            msg.sender_phone,
            msg.sender_jid,
        ].some(value => participantMatchesSelf(value, { selfPhone: extractionInfo?.self_phone }));

        const senderDisplay = senderIsSelf ? 'You' : cleanContactName(msg.sender_name)
            || cachedParticipantLabel(msg.sender_jid)
            || (msg.sender_phone ? formatPhoneNumber(msg.sender_phone) : null)
            || (msg.sender_jid ? fallbackParticipantLabel(msg.sender_jid) : null);

        const msgType = albumGroup ? 'album' : (msg.msg_type || 'chat');
        const msgIsDeleted = isDeletedMessage(msg);
        const rawText = msg.text ? msg.text.trim() : null;
        let bodyHtml = '';

        if (albumGroup) {
            bodyHtml = renderAlbumBubble(albumGroup);

        } else if (msgType === 'call_log') {
            bodyHtml = renderCallLogContent(msg);

        } else if (msgIsDeleted) {
            bodyHtml = renderDeletedMessage(rawText);

        } else if (isCenteredSystemNoticeType(msgType)) {
            bodyHtml = renderSystemNotice(msgType, rawText);

        } else if (msgType === 'sticker') {
            // Stickers get a compact, distinct label — not a bulky file card
            bodyHtml = `<span class="msg-sticker-tag">🎭 Sticker</span>`;

        } else if (specialMessageMeta(msg) && !isMediaMsg(msg)) {
            bodyHtml = renderSpecialMessageContent(msg);

        } else if (isMediaMsg(msg)) {
            bodyHtml = renderMediaCard(msg, rawText);

        } else if (rawText) {
            const base64Marker = '/9j/4AAQSk';
            const b64Idx = rawText.indexOf(base64Marker);
            if (b64Idx > 0 && b64Idx < 300) {
                const prefix = rawText.substring(0, b64Idx).trim();
                const fnMatch = prefix.match(/[\w\-]+\.\w{2,5}/);
                if (fnMatch) {
                    bodyHtml = `<span class="msg-media-tag">📄 ${escapeHtml(fnMatch[0])}</span>`;
                } else {
                    bodyHtml = `<span class="msg-media-tag">📎 Document</span>`;
                }
            } else {
                bodyHtml = `<div class="msg-text" id="msg-text-${msg.rowid}">${formatLongText(rawText, 1, msg.rowid, msg)}</div>`;
            }
        } else {
            // No text — check if there's media metadata that indicates this is a media message
            // even if msg_type is 'chat' or null (common in older/FTS-only messages)
            if (msg.media_mime_type || msg.media_filename || msg.media_size) {
                // Has media metadata — render as a media card
                bodyHtml = renderMediaCard(msg, null);
            } else if (['image', 'video', 'sticker', 'ptt', 'audio', 'ptv', 'document', 'album'].includes(msgType)) {
                // Known media type but no metadata
                const fbIcon = mediaIcon(msgType);
                bodyHtml = `<span class="msg-media-tag">${fbIcon} ${mediaTypeLabel(msgType)}</span>`;
            } else if (['protocol', 'over_sized'].includes(msgType)) {
                // Protocol-level messages — suppress silently (empty placeholder)
                bodyHtml = `<span style="opacity:0;">·</span>`;
            } else {
                const missingLabel = missingMessageBodyLabel(msg);
                bodyHtml = `<span class="msg-missing-body">${escapeHtml(missingLabel)}</span>`;
            }
        }

        // ── Reply quote block ───────────────────────────────────────────────
        let replyHtml = '';
        if (msg.quoted_stanza_id) {
            const qType = msg.quoted_msg_type || '';
            let qBody = null;
            let qOriginalRowid = null;
            let origMsg = null;

            if (msg.quoted_msg_body) {
                qBody = escapeHtml(msg.quoted_msg_body).replace(/\n/g, ' ').slice(0, 120);
            }

            origMsg = findLoadedQuote(msg.quoted_stanza_id)
                || quoteCache.byStanza.get(msg.quoted_stanza_id)
                || null;
            if (origMsg) {
                qOriginalRowid = origMsg.rowid;
            }

            if (!qBody) {
                if (origMsg) {
                    qBody = quoteSummaryForMessage(origMsg);
                }
            }

            if (!qBody) {
                qBody = qType ? `[${escapeHtml(qType)}]` : '[message]';
            }

            let qSender = '';
            if (msg.quoted_participant) {
                const qLabel = quoteParticipantLabel(msg, origMsg);
                const qColor = senderColor(msg.quoted_participant);
                qSender = `<span class="quote-sender" style="color:${qColor}">${escapeHtml(qLabel)}</span>`;
            }

            const clickAttr = qOriginalRowid
                ? `data-quote-rowid="${qOriginalRowid}" style="cursor:pointer" title="Click to scroll to original message"`
                : '';
            replyHtml = `<div class="msg-reply-box" ${clickAttr}>${qSender}<span class="quote-body">${qBody}</span></div>`;
        }

        // Determine CSS class
        let bubbleClass = isSent ? 'msg-out' : isUnknown ? 'msg-unknown' : 'msg-in';
        let isSystemMsg = false;

        if (msgType === 'call_log') {
            bubbleClass = 'msg-call-log';
        } else if (msgIsDeleted) {
            bubbleClass += ' msg-deleted';
        } else if (isCenteredSystemNoticeType(msgType)) {
            bubbleClass = 'msg-system-notification';
            isSystemMsg = true;
        }

        const bubble = document.createElement('div');
        bubble.className = `msg-bubble ${bubbleClass}`;
        bubble.dataset.rowid = msg.rowid;

        let senderHtml = '';
        if (!isSent && msg.is_group && senderDisplay) {
            const sColor = senderColor(msg.sender_jid);
            const senderContactJid = msg.sender_jid || (msg.sender_phone ? `${compactPhoneNumber(msg.sender_phone)}@c.us` : '');
            const contactAttrs = senderContactJid
                ? ` role="button" tabindex="0" data-contact-jid="${escapeAttr(senderContactJid)}" title="View contact"`
                : '';
            const linkClass = senderContactJid ? ' msg-contact-link' : '';
            senderHtml = `<span class="msg-sender-name${linkClass}" style="color:${sColor}"${contactAttrs}>${escapeHtml(senderDisplay)}</span>`;
        }
        const timeStr = formatChatClockTime(metaMsg.timestamp);
        const reactions = !albumGroup && msg.msg_key ? (messageReactionCache.get(msg.msg_key) || []) : [];
        const reactionsHtml = renderReactionSummary(reactions, {
            msgKey: msg.msg_key || '',
            selfPhone: extractionInfo?.self_phone,
        });
        if (reactionsHtml) bubble.classList.add('has-reactions');
        if (albumGroup) {
            bubble.classList.add('msg-album-bubble');
            bubble.dataset.albumId = albumGroup.id;
            bubble.dataset.albumRowids = albumGroup.messages.map(albumMsg => albumMsg.rowid).join(',');
        }

        if (isSystemMsg) {
            // System messages are minimal centered cards
            bubble.innerHTML = `
                ${bodyHtml}
                <div class="msg-meta">
                    <span class="msg-time">${timeStr}</span>
                </div>
            `;
        } else {
            // Standard chat message
            const unknownTag = (isUnknown && msgType !== 'call_log') ? '<span class="msg-unknown-tag" title="Direction unknown">?</span>' : '';
            bubble.innerHTML = `
                ${senderHtml}
                ${replyHtml}
                ${bodyHtml}
                ${reactionsHtml}
                <div class="msg-meta">
                    ${unknownTag}
                    ${renderEditedMarker(metaMsg)}
                    <span class="msg-time">${timeStr}</span>
                    ${messageTickHtml(metaMsg, messageStatusCache)}
                </div>
            `;
        }

        fragment.appendChild(bubble);
    });

    return fragment;
}

async function renderMessages(messages, isSearch = false, searchResultsMeta = null, skipScrollToBottom = false) {
    msgContainer.innerHTML = '';

    if (!messages.length) {
        msgContainer.innerHTML = `<div class="empty-state">${isSearch ? 'No results.' : 'No messages in this chat.'}</div>`;
        return;
    }

    // Deduplicate before rendering.
    const unique = deduplicateMessages(messages);
    await hydrateQuoteCache(unique, activeChatId);
    await hydrateParticipantNameCache(unique);
    await hydrateMessageMentions(unique, activeChatId);
    await hydrateMessageReactions(unique);
    await hydrateMessageStatuses(unique);

    const fragment = buildMessageFragment(unique);
    msgContainer.appendChild(fragment);

    if (!isSearch && !skipScrollToBottom) {
        requestAnimationFrame(() => {
            if (scrollArea) scrollArea.scrollTop = scrollArea.scrollHeight;
        });
    }
}

// ---------------------------------------------------------------------------
// Contact Info Modal
// ---------------------------------------------------------------------------
function groupMemberPayload(participant) {
    const phone = participant.participant_phone ? formatPhoneNumber(participant.participant_phone) : '';
    const lid = participant.participant_lid || '';
    const jid = participant.participant_jid || participant.jid || '';
    const isSelfMember = [
        participant.participant_phone,
        participant.participant_lid,
        participant.participant_jid,
        participant.jid,
    ].some(value => participantMatchesSelf(value, { selfPhone: extractionInfo?.self_phone }));
    const name = isSelfMember ? 'You' : (participant.participant_name || phone || lid || 'Unknown');

    return {
        name,
        phone,
        lid,
        jid,
        isSelf: isSelfMember,
        isAdmin: Boolean(participant.is_admin),
        initials: name.slice(0, 1).toUpperCase(),
        searchText: memberSearchText({ name, phone, lid, jid }),
    };
}

function renderGroupMembers(participants) {
    const members = participants.map(groupMemberPayload);

    return `
        <div class="members-toolbar">
            <div>
                <h3 class="members-title">Members</h3>
                <span class="members-count"><span data-members-visible-count>${members.length}</span> members</span>
            </div>
            <label class="members-search">
                <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path fill="currentColor" d="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
                <input type="search" data-members-search placeholder="Search members" autocomplete="off" />
            </label>
        </div>
        <div class="members-list" data-members-list>
            ${members.map(member => {
        const adminTag = member.isAdmin ? '<span class="admin-tag">Admin</span>' : '';
        const phoneLine = member.phone ? `<span class="member-phone">${escapeHtml(member.phone)}</span>` : '';
        return `
                <div class="member-item" data-member-search="${escapeAttr(member.searchText)}">
                    <div class="member-avatar">${escapeHtml(member.initials)}</div>
                    <div class="member-details">
                        <span class="member-name">${escapeHtml(member.name)} ${adminTag}</span>
                        ${phoneLine}
                    </div>
                </div>
            `;
    }).join('')}
        </div>
        <div class="members-empty hidden" data-members-empty>No members found</div>
    `;
}

function wireGroupMemberSearch(membersSection) {
    const input = membersSection?.querySelector('[data-members-search]');
    const items = Array.from(membersSection?.querySelectorAll('[data-member-search]') || []);
    const emptyState = membersSection?.querySelector('[data-members-empty]');
    const visibleCount = membersSection?.querySelector('[data-members-visible-count]');
    if (!input || items.length === 0) return;

    const update = () => {
        let visible = 0;
        for (const item of items) {
            const isVisible = memberMatchesQuery(item.dataset.memberSearch, input.value);
            item.classList.toggle('hidden', !isVisible);
            if (isVisible) visible += 1;
        }
        if (emptyState) emptyState.classList.toggle('hidden', visible !== 0);
        if (visibleCount) visibleCount.textContent = input.value.trim() ? `${visible}/${items.length}` : String(items.length);
    };

    input.addEventListener('input', update);
    update();
}

async function openContactInfo(chatJid) {
    openOverlay(infoModal);
    infoName.textContent = 'Loading…';
    infoPhone.textContent = '';
    infoPhone.onclick = null;
    infoPhone.title = '';
    infoPhone.style.cursor = '';
    infoAbout.textContent = '';
    infoPic.src = '';
    infoPic.removeAttribute('data-initials');

    const membersSection = document.getElementById('info-members-section');
    if (membersSection) membersSection.innerHTML = '';

    const isGroup = chatJid.includes('@g.us');
    infoModal.classList.toggle('is-group-info', isGroup);

    try {
        if (isGroup) {
            const groupInfo = await invoke('get_group_info', { groupJid: chatJid }).catch(() => null);
            const participants = await invoke('get_group_participants', { groupJid: chatJid }).catch(() => []);

            const subject = groupInfo?.subject || chatJid.split('@')[0];
            infoName.textContent = subject;
            infoPhone.textContent = `${participants.length} members`;

            if (groupInfo?.description) {
                infoAbout.textContent = groupInfo.description;
            } else {
                infoAbout.textContent = 'Group chat';
            }

            const initials = subject.slice(0, 2).toUpperCase();
            const modalAvatar = infoModal.querySelector('.avatar');
            if (modalAvatar) modalAvatar.setAttribute('data-initials', initials);

            if (membersSection && participants.length > 0) {
                membersSection.innerHTML = renderGroupMembers(participants);
                wireGroupMemberSearch(membersSection);
            }
        } else {
            const info = await invoke('get_contact_info', { chatJid });

            if (!info) {
                const cached = cachedParticipantPayload(chatJid);
                const display = cached
                    ? contactInfoDisplay({
                        display_name: cached.name,
                        phone_number: compactPhoneNumber(cached.phone || ''),
                        phone_jid: cached.phone ? `${compactPhoneNumber(cached.phone)}@s.whatsapp.net` : '',
                        is_self: participantMatchesSelf(cached.phone || chatJid, { selfPhone: extractionInfo?.self_phone }),
                    }, chatJid)
                    : contactInfoDisplay(null, chatJid);
                infoName.textContent = display.name;
                infoPhone.textContent = display.phoneLine;
                infoAbout.textContent = display.about;
                return;
            }

            const display = contactInfoDisplay(info, chatJid);
            infoName.textContent = display.name;

            if (display.phoneLine) {
                infoPhone.textContent = display.phoneLine;
                infoPhone.title = 'Click to copy';
                infoPhone.style.cursor = 'pointer';
                infoPhone.onclick = async () => {
                    const ok = await writeToClipboard(display.copyPhone || display.phoneLine);
                    const orig = infoPhone.textContent;
                    infoPhone.textContent = ok ? 'Copied!' : 'Failed to copy';
                    setTimeout(() => infoPhone.textContent = orig, 1500);
                };
            } else {
                infoPhone.textContent = '';
            }

            infoAbout.textContent = display.about;

            const initials = display.name.slice(0, 2).toUpperCase();
            const modalAvatar = infoModal.querySelector('.avatar');
            if (modalAvatar) modalAvatar.setAttribute('data-initials', initials);
            const pic = await invoke('get_contact_picture', { chatJid });
            if (pic) infoPic.src = pic;
        }
    } catch (e) {
        infoName.textContent = '⚠ ' + e;
    }
}

btnCloseModal.addEventListener('click', () => closeOverlay(infoModal));
infoModal.addEventListener('click', e => { if (e.target === infoModal) closeOverlay(infoModal); });

// ---------------------------------------------------------------------------
// Profile pictures — initials fallback
// ---------------------------------------------------------------------------
async function loadProfilePic(jid, imgEl) {
    if (!imgEl) return;
    try {
        const b64 = await invoke('get_contact_picture', { chatJid: jid });
        if (b64) {
            imgEl.src = b64;
        }
    } catch (_) { }
}

// ---------------------------------------------------------------------------
// Media browser
// ---------------------------------------------------------------------------
function mediaSummaryLine(summary) {
    if (!summary) return 'Attachments extracted from WhatsApp Desktop';
    const parts = [
        `${Number(summary.total || 0).toLocaleString()} items`,
        `${Number(summary.available || 0).toLocaleString()} available`,
        `${Number(summary.missing || 0).toLocaleString()} missing`,
    ];
    return parts.join(' · ');
}

function mediaTilePreview(item, kind, absPath) {
    const canPreview = absPath && item.media_status === 'local_present';
    if (!canPreview) return '';
    const src = convertFileSrc(absPath);
    if (kind === 'image' || kind === 'sticker') {
        return `<img class="media-tile-preview" src="${escapeAttr(src)}" alt="" loading="lazy">`;
    }
    if (kind === 'video') {
        return `<video class="media-tile-preview" src="${escapeAttr(src)}" preload="metadata" muted></video>`;
    }
    return '';
}

function renderMediaTile(item) {
    const kind = item.media_kind || mediaDisplayKind(item);
    const absPath = mediaAbsolutePath(item);
    const preview = mediaTilePreview(item, kind, absPath);
    const title = item.media_filename || mediaTypeLabel(kind);
    const chat = item.chat_name || item.chat_jid || 'Unknown chat';
    const detail = [
        item.media_mime_type,
        item.media_size ? formatBytes(item.media_size) : null,
        item.timestamp ? formatClockTime(item.timestamp) : null,
    ].filter(Boolean).join(' · ');
    const status = mediaAvailabilityLabel(item);
    const statusClass = item.media_status === 'local_present' ? 'available' : 'missing';
    const revealButton = absPath && item.media_status === 'local_present'
        ? `<button class="media-reveal-btn" data-media-action="reveal" title="Show in folder">Open</button>`
        : '';

    return `
        <article class="media-tile media-kind-${escapeAttr(kind)}" data-rowid="${escapeAttr(item.rowid)}" data-chat-jid="${escapeAttr(item.chat_jid || '')}">
            <div class="media-thumb ${preview ? 'has-preview' : ''}">
                ${preview || `<span class="media-thumb-icon">${mediaIcon(kind)}</span>`}
                <span class="media-status-pill ${statusClass}">${escapeHtml(status)}</span>
            </div>
            <div class="media-tile-body">
                <div class="media-tile-title" title="${escapeAttr(title)}">${escapeHtml(title)}</div>
                <div class="media-tile-chat" title="${escapeAttr(chat)}">${escapeHtml(chat)}</div>
                ${detail ? `<div class="media-tile-detail">${escapeHtml(detail)}</div>` : ''}
                <div class="media-tile-actions">
                    <span>${mediaCanJumpToMessage(item) ? 'View message' : 'No message link'}</span>
                    ${revealButton}
                </div>
            </div>
        </article>
    `;
}

function renderMediaGrid() {
    if (!mediaGrid) return;
    const filtered = mediaItems
        .filter(item => mediaMatchesFilter(item, mediaFilter))
        .filter(item => mediaMatchesSearch(item, mediaQuery));

    if (mediaSummaryText) {
        const loaded = `${filtered.length.toLocaleString()} loaded${mediaPaging.hasMore ? ' so far' : ''}`;
        mediaSummaryText.textContent = `${mediaSummaryLine(mediaSummary)} · ${loaded}`;
    }

    if (!filtered.length && mediaPaging.loading) {
        mediaGrid.innerHTML = '<div class="media-placeholder"><div class="spinner"></div><p>Loading media...</p></div>';
        return;
    }

    if (!filtered.length) {
        mediaGrid.innerHTML = `
            <div class="media-placeholder">
                <div class="media-placeholder-icon">No media</div>
                <p>No media items match the current view.</p>
                <p class="media-placeholder-sub">Try another type filter or a shorter search.</p>
            </div>
        `;
        return;
    }

    const groups = new Map();
    for (const item of filtered) {
        const label = mediaMonthLabel(item);
        if (!groups.has(label)) groups.set(label, []);
        groups.get(label).push(item);
    }

    const pagingFooter = mediaPaging.loading
        ? '<div class="media-page-status"><span class="spinner"></span><span>Loading more media...</span></div>'
        : (mediaPaging.hasMore
            ? '<div class="media-page-status muted">Scroll to load more</div>'
            : '<div class="media-page-status muted">End of loaded media</div>');

    mediaGrid.innerHTML = Array.from(groups.entries()).map(([label, items]) => `
        <section class="media-month-group">
            <h3>${escapeHtml(label)}</h3>
            <div class="media-month-grid">
                ${items.map(renderMediaTile).join('')}
            </div>
        </section>
    `).join('') + pagingFooter;
}

function resetMediaPagingState() {
    mediaItems = [];
    mediaItemByRowid = new Map();
    mediaPaging = createMediaPagingState();
    mediaLoaded = false;
}

async function loadMediaPage({ reset = false } = {}) {
    if (!mediaGrid || !currentDbPath) return;
    if (mediaPaging.loading) return;
    if (!reset && !mediaPaging.hasMore) return;

    if (reset) {
        mediaLoadRunId++;
        resetMediaPagingState();
    }

    const runId = mediaLoadRunId;
    mediaPaging = { ...mediaPaging, loading: true };
    renderMediaGrid();

    try {
        const summaryPromise = mediaSummary ? Promise.resolve(mediaSummary) : invoke('get_media_summary');
        const [summary, items] = await Promise.all([
            summaryPromise,
            invoke('get_media_items', {
                filter: mediaFilter,
                query: mediaQuery,
                limit: mediaPaging.pageSize,
                offset: mediaPaging.offset,
            }),
        ]);

        if (runId !== mediaLoadRunId) return;

        mediaSummary = summary;
        mediaPaging = appendMediaPage(mediaPaging, items || []);
        mediaItems = mediaPaging.items;
        mediaItemByRowid = new Map(mediaItems.map(item => [String(item.rowid), item]));
        mediaLoaded = true;
        renderMediaGrid();
    } catch (err) {
        mediaPaging = { ...mediaPaging, loading: false };
        mediaGrid.innerHTML = `
            <div class="media-placeholder">
                <div class="media-placeholder-icon">Media unavailable</div>
                <p>Could not load media from this database.</p>
                <p class="media-placeholder-sub">${escapeHtml(String(err))}</p>
            </div>
        `;
    }
}

async function ensureMediaLoaded() {
    if (!mediaGrid || !currentDbPath) return;
    if (mediaLoaded) {
        renderMediaGrid();
        return;
    }
    await loadMediaPage({ reset: true });
}

if (mediaFilterTabs) {
    mediaFilterTabs.addEventListener('click', event => {
        const btn = event.target.closest('[data-media-filter]');
        if (!btn) return;
        mediaFilter = btn.dataset.mediaFilter || 'all';
        mediaFilterTabs.querySelectorAll('.media-filter').forEach(el => el.classList.toggle('active', el === btn));
        loadMediaPage({ reset: true });
    });
}

if (mediaSearchInput) {
    mediaSearchInput.addEventListener('input', event => {
        mediaQuery = event.target.value || '';
        if (mediaSearchTimer) clearTimeout(mediaSearchTimer);
        mediaSearchTimer = setTimeout(() => loadMediaPage({ reset: true }), 180);
    });
}

if (mediaGridContainer) {
    mediaGridContainer.addEventListener('scroll', () => {
        const distanceFromBottom = mediaGridContainer.scrollHeight - mediaGridContainer.scrollTop - mediaGridContainer.clientHeight;
        if (distanceFromBottom < 420) {
            loadMediaPage();
        }
    });
}

if (mediaGrid) {
    mediaGrid.addEventListener('click', async event => {
        const action = event.target.closest('[data-media-action]');
        const tile = event.target.closest('.media-tile');
        if (!tile) return;
        const item = mediaItemByRowid.get(String(tile.dataset.rowid));
        if (!item) return;

        if (action?.dataset.mediaAction === 'reveal') {
            event.stopPropagation();
            const path = item.media_case_path || mediaAbsolutePath(item);
            if (!path) return;
            try {
                await invoke('reveal_media_file', { path });
            } catch (err) {
                showToast('Could not open media location: ' + err, 'error');
            }
            return;
        }

        if (mediaCanJumpToMessage(item)) {
            switchTab('chats');
            await jumpToMessageInChat(item.chat_jid, Number(item.rowid));
        }
    });
}

// ---------------------------------------------------------------------------
// Contacts browser
// ---------------------------------------------------------------------------
function contactsSummaryLine(summary) {
    if (!summary) return 'Contacts extracted from WhatsApp Desktop';
    return [
        `${Number(summary.total || 0).toLocaleString()} contacts`,
        `${Number(summary.saved || 0).toLocaleString()} saved`,
        `${Number(summary.with_chats || 0).toLocaleString()} with chats`,
    ].join(' · ');
}

function renderContactItem(contact) {
    const name = contactDisplayName(contact);
    const subtitle = contactSubtitle(contact);
    const meta = contactMetaLine(contact);
    const targetJid = contact.chat_jid || contact.jid || '';
    const initials = contactInitials(contact);
    const time = contact.last_activity ? formatTs(contact.last_activity) : '';
    const viewChatButton = contact.chat_jid
        ? '<button class="contact-action-btn ghost" data-contact-action="view-chat">View chat</button>'
        : '';
    const badges = [
        contact.is_business ? 'Business' : null,
        contact.is_self ? 'You' : null,
    ].filter(Boolean);

    return `
        <article class="contact-row" data-contact-jid="${escapeAttr(targetJid)}">
            <div class="avatar contact-avatar" data-initials="${escapeAttr(initials)}"></div>
            <div class="contact-main">
                <div class="contact-topline">
                    <span class="contact-name" title="${escapeAttr(name)}">${escapeHtml(name)}</span>
                    ${time ? `<span class="contact-time">${escapeHtml(time)}</span>` : ''}
                </div>
                ${subtitle ? `<div class="contact-subtitle" title="${escapeAttr(subtitle)}">${escapeHtml(subtitle)}</div>` : ''}
                ${meta ? `<div class="contact-meta">${escapeHtml(meta)}</div>` : ''}
                ${badges.length ? `<div class="contact-badges">${badges.map(b => `<span>${escapeHtml(b)}</span>`).join('')}</div>` : ''}
            </div>
            <div class="contact-actions">
                <button class="contact-action-btn" data-contact-action="details">Details</button>
                ${viewChatButton}
            </div>
        </article>
    `;
}

function renderContactsList() {
    if (!contactsList) return;
    const filtered = contactItems
        .filter(item => contactMatchesFilter(item, contactFilter))
        .filter(item => contactMatchesSearch(item, contactQuery));

    if (contactsSummaryText) {
        contactsSummaryText.textContent = `${contactsSummaryLine(contactSummary)} · ${filtered.length.toLocaleString()} shown`;
    }

    if (!filtered.length) {
        contactsList.innerHTML = `
            <div class="browser-placeholder">
                <div class="browser-placeholder-icon">No contacts</div>
                <p>No contacts match the current view.</p>
            </div>
        `;
        return;
    }

    contactsList.innerHTML = filtered.map(renderContactItem).join('');
}

async function ensureContactsLoaded() {
    if (!contactsList || !currentDbPath || contactsLoaded) return;
    contactsList.innerHTML = '<div class="browser-placeholder"><div class="spinner"></div><p>Loading contacts...</p></div>';
    try {
        const [summary, items] = await Promise.all([
            invoke('get_contact_summary'),
            invoke('get_contact_items', { filter: 'all', query: '', limit: 20000, offset: 0 }),
        ]);
        contactSummary = summary;
        contactItems = items || [];
        contactsLoaded = true;
        renderContactsList();
    } catch (err) {
        contactsList.innerHTML = `
            <div class="browser-placeholder">
                <div class="browser-placeholder-icon">Contacts unavailable</div>
                <p>Could not load contacts from this database.</p>
                <p class="media-placeholder-sub">${escapeHtml(String(err))}</p>
            </div>
        `;
    }
}

if (contactsFilterTabs) {
    contactsFilterTabs.addEventListener('click', event => {
        const btn = event.target.closest('[data-contacts-filter]');
        if (!btn) return;
        contactFilter = btn.dataset.contactsFilter || 'all';
        contactsFilterTabs.querySelectorAll('.browser-filter').forEach(el => el.classList.toggle('active', el === btn));
        renderContactsList();
    });
}

if (contactsSearchInput) {
    contactsSearchInput.addEventListener('input', event => {
        contactQuery = event.target.value || '';
        renderContactsList();
    });
}

if (contactsList) {
    contactsList.addEventListener('click', async event => {
        const row = event.target.closest('.contact-row');
        if (!row) return;
        const item = contactItems.find(entry => String(entry.chat_jid || entry.jid) === String(row.dataset.contactJid));
        if (!item) return;
        const action = event.target.closest('[data-contact-action]')?.dataset.contactAction || 'details';
        const targetJid = item.chat_jid || item.jid;

        if (action !== 'view-chat' || !item.chat_jid) {
            await openContactInfo(targetJid);
            return;
        }

        const chat = allChats.find(c => c.chat_jid === item.chat_jid) || {
            chat_jid: item.chat_jid,
            chat_name: contactDisplayName(item),
            chat_phone: item.phone_number,
            is_group: item.is_group,
            message_count: item.message_count || 0,
            sent_count: item.sent_count || 0,
            recv_count: item.recv_count || 0,
        };
        switchTab('chats');
        const sidebarItem = Array.from(document.querySelectorAll('.chat-item'))
            .find(el => el.dataset.jid === item.chat_jid);
        await openChat(chat, sidebarItem);
    });
}

// ---------------------------------------------------------------------------
// Call history browser
// ---------------------------------------------------------------------------
function callsSummaryLine(summary) {
    if (!summary) return 'Call events extracted from WhatsApp Desktop';
    return [
        `${Number(summary.total || 0).toLocaleString()} calls`,
        `${Number(summary.missed || 0).toLocaleString()} missed`,
        `${Number(summary.answered || 0).toLocaleString()} answered`,
        `${Number(summary.video || 0).toLocaleString()} video`,
    ].join(' · ');
}

function callIconSvg(call) {
    const isVideo = call.is_video_call === 1 || call.is_video_call === true || String(call.is_video_call).toLowerCase() === 'true';
    const path = isVideo
        ? '<path d="M4.5 6.5h8a2 2 0 0 1 2 2v4.2l4-2.4V15l-4-2.4v.9a2 2 0 0 1-2 2h-8a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2Z" fill="currentColor"/>'
        : '<path d="M6.6 4.2 8.4 8c.2.4.1.9-.3 1.2l-1.1.9a12.7 12.7 0 0 0 5 5l.9-1.1c.3-.4.8-.5 1.2-.3l3.8 1.8c.5.2.8.8.7 1.3l-.5 2.2c-.1.6-.6 1-1.2 1A14.8 14.8 0 0 1 2 5.1c0-.6.4-1.1 1-1.2l2.2-.5c.6-.1 1.1.2 1.4.8Z" fill="currentColor"/>';
    return `<svg viewBox="0 0 22 22" width="18" height="18">${path}</svg>`;
}

function renderCallItem(call) {
    const name = call.chat_name || call.sender_name || formatPhoneNumber(call.phone || call.sender_phone) || call.chat_jid;
    const subtitle = formatPhoneNumber(call.phone || call.sender_phone) || call.chat_jid;
    const outcome = browserCallOutcomeMeta(call);
    const direction = callDirectionMeta(call);
    const duration = formatCallDuration(call.call_duration);
    const time = call.timestamp ? formatClockTime(call.timestamp, settings.regionalTime) : '';
    const detail = [
        direction.label,
        duration ? `Duration ${duration}` : null,
    ].filter(Boolean).join(' · ');

    return `
        <article class="call-row call-row-${escapeAttr(outcome.tone)}" data-call-rowid="${escapeAttr(call.rowid)}">
            <div class="call-row-icon ${outcome.tone}">${callIconSvg(call)}</div>
            <div class="call-row-main">
                <div class="call-row-topline">
                    <span class="call-row-name" title="${escapeAttr(name)}">${escapeHtml(name || 'Unknown')}</span>
                    <span class="call-row-time">${escapeHtml(time)}</span>
                </div>
                <div class="call-row-title">${escapeHtml(callTitle(call))}</div>
                <div class="call-row-detail">${escapeHtml(detail)}</div>
                ${subtitle && subtitle !== name ? `<div class="call-row-phone">${escapeHtml(subtitle)}</div>` : ''}
            </div>
            <button class="contact-action-btn ghost" data-call-action="jump">${callCanJumpToMessage(call) ? 'View' : 'Open'}</button>
        </article>
    `;
}

function renderCallsList() {
    if (!callsList) return;
    const filtered = callItems
        .filter(item => callMatchesFilter(item, callFilter))
        .filter(item => callMatchesSearch(item, callQuery));

    if (callsSummaryText) {
        callsSummaryText.textContent = `${callsSummaryLine(callSummary)} · ${filtered.length.toLocaleString()} shown`;
    }

    if (!filtered.length) {
        callsList.innerHTML = `
            <div class="browser-placeholder">
                <div class="browser-placeholder-icon">No calls</div>
                <p>No calls match the current view.</p>
            </div>
        `;
        return;
    }

    const groups = new Map();
    for (const call of filtered) {
        const label = callDayLabel(call);
        if (!groups.has(label)) groups.set(label, []);
        groups.get(label).push(call);
    }

    callsList.innerHTML = Array.from(groups.entries()).map(([label, items]) => `
        <section class="calls-day-group">
            <h3>${escapeHtml(label)}</h3>
            ${items.map(renderCallItem).join('')}
        </section>
    `).join('');
}

async function ensureCallsLoaded() {
    if (!callsList || !currentDbPath || callsLoaded) return;
    callsList.innerHTML = '<div class="browser-placeholder"><div class="spinner"></div><p>Loading calls...</p></div>';
    try {
        const [summary, items] = await Promise.all([
            invoke('get_call_summary'),
            invoke('get_call_items', { filter: 'all', query: '', limit: 10000, offset: 0 }),
        ]);
        callSummary = summary;
        callItems = items || [];
        callsLoaded = true;
        renderCallsList();
    } catch (err) {
        callsList.innerHTML = `
            <div class="browser-placeholder">
                <div class="browser-placeholder-icon">Calls unavailable</div>
                <p>Could not load call history from this database.</p>
                <p class="media-placeholder-sub">${escapeHtml(String(err))}</p>
            </div>
        `;
    }
}

if (callsFilterTabs) {
    callsFilterTabs.addEventListener('click', event => {
        const btn = event.target.closest('[data-calls-filter]');
        if (!btn) return;
        callFilter = btn.dataset.callsFilter || 'all';
        callsFilterTabs.querySelectorAll('.browser-filter').forEach(el => el.classList.toggle('active', el === btn));
        renderCallsList();
    });
}

if (callsSearchInput) {
    callsSearchInput.addEventListener('input', event => {
        callQuery = event.target.value || '';
        renderCallsList();
    });
}

if (callsList) {
    callsList.addEventListener('click', async event => {
        const row = event.target.closest('.call-row');
        if (!row) return;
        const item = callItems.find(entry => String(entry.rowid) === String(row.dataset.callRowid));
        if (!item) return;
        if (callCanJumpToMessage(item)) {
            switchTab('chats');
            await jumpToMessageInChat(item.chat_jid, Number(item.rowid));
        }
    });
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------
const SETTINGS_KEY = 'waren6_settings';
const DEFAULT_SETTINGS = {
    theme: 'forensic-dark',
    uiScale: DEFAULT_UI_SCALE,
    scaleBaselineVersion: SCALE_BASELINE_VERSION,
    fontFamily: 'Aptos',
    density: 'comfortable',
    motion: 'subtle',
    regionalTime: 'local',
};
let settings = migrateSettings(JSON.parse(localStorage.getItem(SETTINGS_KEY) || JSON.stringify(DEFAULT_SETTINGS)));

function migrateSettings(raw) {
    const scaleSettings = migrateUiScaleSetting(raw || {});
    const next = { ...DEFAULT_SETTINGS, ...(raw || {}), ...scaleSettings };
    if (next.theme === 'dark') next.theme = 'forensic-dark';
    if (next.theme === 'light') next.theme = 'evidence-light';
    if (!['system', 'forensic-dark', 'evidence-light', 'high-contrast'].includes(next.theme)) next.theme = DEFAULT_SETTINGS.theme;
    if (!['comfortable', 'compact'].includes(next.density)) next.density = DEFAULT_SETTINGS.density;
    if (!['subtle', 'reduced'].includes(next.motion)) next.motion = DEFAULT_SETTINGS.motion;
    next.regionalTime = normalizeRegionalTime(next.regionalTime);
    return next;
}

function resolvedTheme() {
    if (settings.theme === 'evidence-light') return 'light';
    if (settings.theme === 'system') {
        return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'forensic-dark';
    }
    return settings.theme;
}

function applySettings() {
    document.documentElement.setAttribute('data-theme', resolvedTheme());
    document.documentElement.setAttribute('data-theme-choice', settings.theme);
    document.documentElement.setAttribute('data-density', settings.density);
    document.documentElement.setAttribute('data-motion', settings.motion);

    document.documentElement.style.setProperty('--ui-scale', effectiveUiScale(settings.uiScale));
    document.documentElement.style.setProperty('--font', `"${settings.fontFamily}", "Segoe UI", system-ui, sans-serif`);

    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
}
applySettings();
const systemThemeQuery = window.matchMedia('(prefers-color-scheme: light)');
const handleSystemThemeChange = () => {
    if (settings.theme === 'system') applySettings();
};
if (systemThemeQuery.addEventListener) {
    systemThemeQuery.addEventListener('change', handleSystemThemeChange);
} else if (systemThemeQuery.addListener) {
    systemThemeQuery.addListener(handleSystemThemeChange);
}

if (tabSettings) {
    tabSettings.addEventListener('click', () => {
        openOverlay(settingsModal);
    });
}
if (btnCloseSettings) {
    btnCloseSettings.addEventListener('click', () => {
        closeOverlay(settingsModal);
    });
}
if (settingsModal) {
    settingsModal.addEventListener('click', e => {
        if (e.target === settingsModal) closeOverlay(settingsModal);
    });
}

function initSettingsControls() {
    const themeSelect = document.getElementById('setting-theme');
    if (themeSelect) {
        themeSelect.value = settings.theme;
        themeSelect.addEventListener('change', e => {
            settings.theme = e.target.value;
            applySettings();
        });
    }

    const densitySelect = document.getElementById('setting-density');
    if (densitySelect) {
        densitySelect.value = settings.density;
        densitySelect.addEventListener('change', e => {
            settings.density = e.target.value;
            applySettings();
        });
    }

    const motionSelect = document.getElementById('setting-motion');
    if (motionSelect) {
        motionSelect.value = settings.motion;
        motionSelect.addEventListener('change', e => {
            settings.motion = e.target.value;
            applySettings();
        });
    }

    const scaleSlider = document.getElementById('setting-scale-slider');
    const scaleInput = document.getElementById('setting-scale-input');
    if (scaleSlider && scaleInput) {
        scaleSlider.value = settings.uiScale;
        scaleInput.value = settings.uiScale;
        scaleSlider.addEventListener('input', e => {
            const v = clampUiScale(e.target.value);
            settings.uiScale = v;
            scaleInput.value = v;
            applySettings();
        });
        scaleInput.addEventListener('change', e => {
            const v = clampUiScale(e.target.value);
            settings.uiScale = v;
            scaleSlider.value = v;
            scaleInput.value = v;
            applySettings();
        });
    }

    const fontSelect = document.getElementById('setting-font');
    if (fontSelect) {
        fontSelect.value = settings.fontFamily;
        fontSelect.addEventListener('change', e => {
            settings.fontFamily = e.target.value;
            applySettings();
        });
    }

    if (regionalTimeSelect) {
        regionalTimeSelect.innerHTML = '';
        for (const zone of supportedRegionalTimes()) {
            const option = document.createElement('option');
            option.value = zone.value;
            option.textContent = zone.label;
            regionalTimeSelect.appendChild(option);
        }
        regionalTimeSelect.value = settings.regionalTime;
        regionalTimeSelect.addEventListener('change', e => {
            settings.regionalTime = normalizeRegionalTime(e.target.value);
            applySettings();
            renderChatList();
            if (activeChatId) {
                const fullChat = allChats.find(c => c.chat_jid === activeChatId) || { chat_jid: activeChatId };
                openChat(fullChat, chatItemForJid(activeChatId));
            }
        });
    }
}
initSettingsControls();

// ---------------------------------------------------------------------------
// Export chat to HTML
// ---------------------------------------------------------------------------
if (btnExportChat) {
    btnExportChat.addEventListener('click', async (e) => {
        e.stopPropagation();
        if (!activeChatId) return;

        try {
            const messages = await invoke('get_messages', { chatJid: activeChatId });
            const chatName = activeChatName.textContent || activeChatId;
            const selfPhone = formatPhoneNumber(extractionInfo?.self_phone) || 'unknown';

            let html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Chat - ${escapeHtml(chatName)}</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', Inter, sans-serif; background: #0d1117; color: #e6edf3; padding: 20px; }
.header { text-align: center; padding: 20px; border-bottom: 1px solid #333; margin-bottom: 20px; }
.header h1 { color: #00c6a0; font-size: 1.5rem; }
.header p { color: #8b949e; font-size: 0.85rem; margin-top: 4px; }
.msgs { max-width: 800px; margin: 0 auto; display: flex; flex-direction: column; gap: 4px; }
.date-sep { text-align: center; color: #484f58; font-size: 0.75rem; padding: 14px 0 6px; }
.bubble { max-width: 72%; padding: 8px 12px; border-radius: 14px; font-size: 0.9rem; line-height: 1.5; word-break: break-word; }
.sent { background: #005c4b; color: #e0ffe8; align-self: flex-end; border-bottom-right-radius: 4px; }
.recv { background: #1e2a35; color: #e6edf3; align-self: flex-start; border-bottom-left-radius: 4px; }
.unknown { background: #2a2a2a; color: #8b949e; align-self: center; border-left: 2px solid #484f58; }
.call-log { background: #1a1a2e; color: #8b949e; align-self: center; border: 1px solid #333; }
.sender { font-size: 0.73rem; font-weight: 600; color: #00c6a0; margin-bottom: 2px; }
.meta { display: flex; justify-content: flex-end; gap: 4px; margin-top: 3px; font-size: 0.68rem; color: rgba(255,255,255,0.35); }
.footer { text-align: center; color: #484f58; font-size: 0.75rem; padding: 30px 0 10px; border-top: 1px solid #333; margin-top: 20px; }
</style>
</head>
<body>
<div class="header">
    <h1>Chat: ${escapeHtml(chatName)}</h1>
    <p>Exported by WAren6 &middot; ${new Date().toLocaleString()} &middot; Timezone: ${escapeHtml(settings.regionalTime)} &middot; Self: ${selfPhone}</p>
    <p>${messages.length} messages</p>
</div>
<div class="msgs">\n`;

            let lastDateStr = '';
            for (const msg of messages) {
                const dateStr = formatDateSeparator(msg.timestamp, settings.regionalTime);

                if (dateStr && dateStr !== lastDateStr) {
                    html += `<div class="date-sep">${dateStr}</div>\n`;
                    lastDateStr = dateStr;
                }

                const mtype = msg.msg_type || 'chat';
                let cls = msg.from_me === 1 ? 'sent' : msg.from_me === 0 ? 'recv' : 'unknown';
                if (mtype === 'call_log') cls = 'call-log';

                let bodyHtml;
                if (mtype === 'call_log') {
                    const icon = (msg.is_video_call === 1 || msg.is_video_call === true || String(msg.is_video_call).toLowerCase() === 'true') ? 'Video call' : 'Voice call';
                    const dur = formatCallDuration(msg.call_duration);
                    bodyHtml = `<em>${icon}${dur ? ` · ${dur}` : ''}</em>`;
                } else if (isDeletedMessage(msg)) {
                    bodyHtml = `<em>${escapeHtml(msg.text || 'This message was deleted')}</em>`;
                } else if (msg.text) {
                    bodyHtml = escapeHtml(msg.text).replace(/\n/g, '<br>');
                } else {
                    const icons = { image: '🖼️', video: '🎥', sticker: '🎭', ptt: '🎤', audio: '🎵', document: '📄', album: '🖼️' };
                    bodyHtml = `<em>${icons[mtype] || '📎'} ${msg.media_filename || mtype}${msg.media_size ? ' · ' + formatBytes(msg.media_size) : ''}</em>`;
                }

                const timeStr = formatClockTime(msg.timestamp, settings.regionalTime);

                let senderLine = '';
                if (msg.from_me !== 1 && msg.is_group) {
                    const senderIsSelf = [
                        msg.sender_phone,
                        msg.sender_jid,
                    ].some(value => participantMatchesSelf(value, { selfPhone: extractionInfo?.self_phone }));
                    const senderLabel = senderIsSelf
                        ? 'You'
                        : (msg.sender_name || (msg.sender_phone ? formatPhoneNumber(msg.sender_phone) : null) || (msg.sender_jid ? msg.sender_jid.split('@')[0] : ''));
                    if (senderLabel) senderLine = `<div class="sender">${escapeHtml(senderLabel)}</div>`;
                }

                html += `<div class="bubble ${cls}">${senderLine}${bodyHtml}<div class="meta">${timeStr}${msg.from_me === 1 ? ' ✓✓' : ''}</div></div>\n`;
            }

            html += `</div>\n<div class="footer">Generated by WAren6 — WhatsApp Forensic Viewer</div>\n</body>\n</html>`;

            const filename = `${chatName.replace(/[^a-zA-Z0-9]/g, '_')}_export.html`;
            const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            showToast(`Chat exported as "${filename}" and saved to your Downloads folder.`, 'success');

        } catch (err) {
            console.error('Export failed:', err);
            showToast('Export failed: ' + err, 'error');
        }
    });
}

// ---------------------------------------------------------------------------
// Utility helpers
// ---------------------------------------------------------------------------
function formatBytes(bytes) {
    if (!bytes || bytes <= 0) return '';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function showToast(message, type = 'success') {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('visible'));
    setTimeout(() => {
        toast.classList.remove('visible');
        setTimeout(() => toast.remove(), 400);
    }, 4000);
}
