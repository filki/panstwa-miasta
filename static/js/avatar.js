const PM_AVATAR_KEY = 'pm_avatar_id';

const AVATAR_OPTIONS = [
    '/static/img/avatars/avatar-01.png',
    '/static/img/avatars/avatar-02.png',
];

function normalizeAvatarId(raw) {
    const id = Number(raw);
    if (!Number.isInteger(id) || id < 0 || id >= AVATAR_OPTIONS.length) return null;
    return id;
}

function readStoredAvatarId() {
    return normalizeAvatarId(localStorage.getItem(PM_AVATAR_KEY));
}

function persistAvatarId(id) {
    const normalized = normalizeAvatarId(id);
    if (normalized === null) return null;
    localStorage.setItem(PM_AVATAR_KEY, String(normalized));
    return normalized;
}

function randomAvatarId(exclude = null) {
    if (AVATAR_OPTIONS.length === 0) return 0;
    if (AVATAR_OPTIONS.length === 1) return 0;
    const array = new Uint32Array(1);
    globalThis.crypto.getRandomValues(array);
    let next = array[0] % AVATAR_OPTIONS.length;
    if (exclude === null || exclude !== next) return next;
    return (next + 1) % AVATAR_OPTIONS.length;
}

function getAvatarSrc(id) {
    const normalized = normalizeAvatarId(id);
    if (normalized === null) return AVATAR_OPTIONS[0];
    return AVATAR_OPTIONS[normalized];
}

function avatarIdForPlayer(name, viewerNick = '') {
    const viewer = String(viewerNick || globalThis.myNick || '').trim();
    if (viewer && name === viewer && typeof getCurrentAvatarId === 'function') {
        return getCurrentAvatarId();
    }
    let hash = 0;
    for (const ch of String(name)) hash = (hash + ch.charCodeAt(0)) % AVATAR_OPTIONS.length;
    return hash;
}

function applyAvatarPreview(id) {
    const img = document.getElementById('landing-anon-avatar');
    if (!img) return null;
    const normalized = normalizeAvatarId(id);
    if (normalized === null) return null;
    img.src = getAvatarSrc(normalized);
    img.alt = `Awatar ${normalized + 1}`;
    return normalized;
}

function getCurrentAvatarId() {
    return readStoredAvatarId() ?? randomAvatarId();
}

function initAvatarSelection() {
    const img = document.getElementById('landing-anon-avatar');
    if (!img) return null;
    const id = getCurrentAvatarId();
    persistAvatarId(id);
    return applyAvatarPreview(id);
}

function rerollPlayerAvatar() {
    const current = readStoredAvatarId();
    const next = randomAvatarId(current);
    persistAvatarId(next);
    return applyAvatarPreview(next);
}

globalThis.PM_AVATAR_KEY = PM_AVATAR_KEY;
globalThis.AVATAR_OPTIONS = AVATAR_OPTIONS;
globalThis.initAvatarSelection = initAvatarSelection;
globalThis.rerollPlayerAvatar = rerollPlayerAvatar;
globalThis.getCurrentAvatarId = getCurrentAvatarId;
globalThis.getAvatarSrc = getAvatarSrc;
globalThis.avatarIdForPlayer = avatarIdForPlayer;

if (typeof module !== 'undefined') {
    module.exports = {
        PM_AVATAR_KEY,
        AVATAR_OPTIONS,
        normalizeAvatarId,
        readStoredAvatarId,
        persistAvatarId,
        randomAvatarId,
        getAvatarSrc,
        avatarIdForPlayer,
        initAvatarSelection,
        rerollPlayerAvatar,
    };
}
