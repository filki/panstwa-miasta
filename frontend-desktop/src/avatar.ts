export const AVATAR_OPTIONS = [
  '/static/img/avatars/avatar-01.png',
  '/static/img/avatars/avatar-02.png',
  '/static/img/avatars/avatar-03.png',
  '/static/img/avatars/avatar-04.png',
];

export function getAvatarSrc(id: number): string {
  const i = Number.isInteger(id) && id >= 0 && id < AVATAR_OPTIONS.length ? id : 0;
  return AVATAR_OPTIONS[i];
}

export function avatarIdForPlayer(name: string, viewerNick = ''): number {
  const viewer = String(viewerNick || '').trim();
  if (viewer && name === viewer) {
    return Number(localStorage.getItem('pm_avatar') || 0) % AVATAR_OPTIONS.length;
  }
  let hash = 0;
  for (const ch of String(name)) {
    hash = (hash + (ch.codePointAt(0) ?? 0)) % AVATAR_OPTIONS.length;
  }
  return hash;
}
