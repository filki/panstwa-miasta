/**
 * @jest-environment jsdom
 */

const {
    normalizeAvatarId,
    persistAvatarId,
    randomAvatarId,
    rerollPlayerAvatar,
    initAvatarSelection,
    PM_AVATAR_KEY,
    AVATAR_OPTIONS,
} = require('../static/js/avatar.js');

describe('avatar assets', () => {
    beforeEach(() => {
        document.body.innerHTML = '<img id="landing-anon-avatar" alt="">';
        localStorage.clear();
    });

    test('normalizeAvatarId accepts valid index', () => {
        expect(normalizeAvatarId('1')).toBe(1);
        expect(normalizeAvatarId(0)).toBe(0);
        expect(normalizeAvatarId(AVATAR_OPTIONS.length)).toBeNull();
    });

    test('persistAvatarId stores value in localStorage', () => {
        persistAvatarId(1);
        expect(localStorage.getItem(PM_AVATAR_KEY)).toBe('1');
    });

    test('randomAvatarId avoids current id when possible', () => {
        globalThis.crypto = {
            getRandomValues: (arr) => {
                arr[0] = 0;
                return arr;
            },
        };
        const picked = randomAvatarId(0);
        expect(picked).toBeGreaterThanOrEqual(0);
        expect(picked).toBeLessThan(AVATAR_OPTIONS.length);
        expect(picked).not.toBe(0);
    });

    test('initAvatarSelection sets preview src', () => {
        initAvatarSelection();
        const img = document.getElementById('landing-anon-avatar');
        expect(img.src).toContain(AVATAR_OPTIONS[0]);
    });

    test('rerollPlayerAvatar switches preview', () => {
        globalThis.crypto = {
            getRandomValues: (arr) => {
                arr[0] = 0;
                return arr;
            },
        };
        persistAvatarId(0);
        rerollPlayerAvatar();
        const img = document.getElementById('landing-anon-avatar');
        expect(img.src).not.toContain(AVATAR_OPTIONS[0]);
    });
});
