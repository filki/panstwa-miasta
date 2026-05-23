import { GemElement, html, customElement, connectStore, property, css, adoptedStyle } from '@mantou/gem';
import { pageStore, connectionStore, roomStore, roundStore, overlayStore, resultsStore, chatStore, nickStore, activeRoomsStore, GAME_CATEGORIES } from './store';
import * as sock from './socket';
import { getAvatarSrc, avatarIdForPlayer } from './avatar';

const appStyle = css`
  :host { display:flex; flex-direction:column; height:100%; overflow:hidden; }
  .navbar { display:flex; align-items:center; justify-content:space-between; padding:8px 16px; gap:8px; background:var(--card-bg); border-bottom:1px solid var(--border); flex-shrink:0; }
  .nav-left { display:flex; align-items:center; gap:8px; }
  .logo { font-family:Outfit,sans-serif; font-weight:900; font-size:1.1rem; color:var(--primary); text-decoration:none; cursor:pointer; }
  .logo span { color:var(--text); }
  .nav-room-info { font-size:.85rem; color:var(--text-secondary); }
  .nav-room-info strong { color:var(--text); font-weight:700; font-size:1.1rem; }
  .nav-status { width:8px;height:8px;border-radius:50%;flex-shrink:0 }
  .nav-status--connected { background:var(--success) }
  .nav-status--reconnecting { background:var(--accent); animation:pulse .8s infinite }
  .nav-status--disconnected { background:var(--danger) }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
  .main { flex:1;overflow-y:auto;overflow-x:hidden;-webkit-overflow-scrolling:touch;padding:16px; }
  button { border:none;cursor:pointer;border-radius:var(--radius);padding:8px 16px;font-weight:600;font-size:.9rem;display:inline-flex;align-items:center;justify-content:center;gap:6px;transition:background .15s; }
  .btn-primary { background:var(--primary);color:#fff; }
  .btn-primary:hover { background:var(--primary-hover); }
  .btn-secondary { background:var(--border);color:var(--text); }
  .btn-danger { background:var(--danger);color:#fff; }
  .btn-accent { background:var(--accent);color:#fff; }
  .btn-sm { padding:6px 12px;font-size:.8rem; }
  .card { background:var(--card-bg);border-radius:var(--radius-lg);padding:20px;box-shadow:var(--shadow); }
  .flex-center { display:flex;align-items:center;justify-content:center;flex-direction:column;gap:12px; }
  h1,h2,h3 { font-family:Outfit,sans-serif; }
  h1 { font-size:1.8rem; }
  h2 { font-size:1.4rem; }
  h3 { font-size:1.1rem; }
  input, select { border:1px solid var(--border);border-radius:var(--radius);padding:10px 14px;font-size:.95rem;width:100%;background:var(--card-bg);color:var(--text);outline:none; }
  input:focus, select:focus { border-color:var(--primary);box-shadow:0 0 0 2px rgba(79,70,229,.15); }
  .tag { display:inline-block;padding:2px 8px;border-radius:6px;font-size:.75rem;font-weight:600; }
  .tag--public { background:#d1fae5;color:#065f46; }
  .tag--private { background:#fee2e2;color:#991b1b; }
`;

function avatarUrl(name: string, viewerNick: string): string {
  const id = avatarIdForPlayer(name, viewerNick);
  return getAvatarSrc(id);
}

function esc(s: string): string {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

// ── Root App ────────────────────────────────────────────────────────────────
@customElement('pm-app')
@adoptedStyle(appStyle)
@connectStore(pageStore)
@connectStore(connectionStore)
@connectStore(roomStore)
export class PmApp extends GemElement {
  render() {
    const { page } = pageStore;
    const { connected, reconnecting } = connectionStore;
    const inRoom = page === 'room';
    const roomId = roomStore.room_id;
    let statusClass = 'nav-status--disconnected';
    let statusTitle = 'Rozłączono';
    if (connected) { statusClass = 'nav-status--connected'; statusTitle = 'Połączono'; }
    else if (reconnecting) { statusClass = 'nav-status--reconnecting'; statusTitle = 'Ponowne łączenie…'; }

    return html`
      ${inRoom ? html`
        <nav class="navbar">
          <div class="nav-left">
            <span class="logo" @click=${() => sock.leaveRoom()}>Państwa<span>Miasta</span></span>
            ${roomId ? html`<span class="nav-room-info">Pokój <strong>${String(roomId)}</strong></span>` : null}
          </div>
          <div style="display:flex;align-items:center;gap:8px">
            <span class="nav-status ${statusClass}" title=${statusTitle}></span>
            <button class="btn-danger btn-sm" @click=${() => sock.leaveRoom()}>Wyjdź</button>
          </div>
        </nav>
      ` : ''}
      <main class="main">
        ${page === 'landing' ? html`<pm-landing></pm-landing>` : html`<pm-room></pm-room>`}
      </main>
      <pm-lottery-overlay></pm-lottery-overlay>
      <pm-countdown-overlay></pm-countdown-overlay>
      <pm-results-overlay></pm-results-overlay>
    `;
  }
}

// ── Landing Page ────────────────────────────────────────────────────────────
const landingStyle = css`
  :host { display:flex;flex-direction:column;align-items:center;padding:20px;gap:24px;max-width:480px;margin:0 auto;width:100%; }
  .hero { text-align:center; }
  .hero h1 { font-size:2rem;margin-bottom:8px; }
  .hero p { color:var(--text-secondary);font-size:.95rem; }
  .actions { display:flex;flex-direction:column;gap:12px;width:100%; }
  .avatar-block { display:flex;align-items:center;gap:12px;justify-content:center; }
  .avatar-frame { width:72px;height:72px;border-radius:50%;overflow:hidden;border:3px solid var(--primary);flex-shrink:0; }
  .avatar-frame img { width:100%;height:100%;object-fit:cover; }
  .nick-row { display:flex;align-items:center;gap:8px;flex:1; }
  .nick-reroll { background:none;border:none;font-size:1.4rem;padding:4px;cursor:pointer;color:var(--text-secondary);min-height:auto;min-width:auto; }
  .join-row { display:flex;gap:8px;align-items:center; }
  .rooms-section { width:100%; }
  .rooms-title { display:flex;align-items:center;justify-content:space-between;margin-bottom:12px; }
  .room-card { display:flex;align-items:center;justify-content:space-between;padding:12px 16px;background:var(--card-bg);border-radius:var(--radius);box-shadow:var(--shadow);margin-bottom:8px;cursor:pointer; }
  .room-card-left { display:flex;flex-direction:column;gap:2px; }
  .room-card-code { font-weight:700;font-size:.95rem; }
  .room-card-meta { font-size:.8rem;color:var(--text-secondary); }
  .empty-state { text-align:center;padding:32px 16px;color:var(--text-secondary); }
  .support-link { color:var(--text-secondary);font-size:.85rem;text-align:center;display:block;margin-top:8px; }
`;

@customElement('pm-landing')
@adoptedStyle(landingStyle)
@connectStore(nickStore)
@connectStore(activeRoomsStore)
export class PmLanding extends GemElement {
  #view: 'start' | 'join' = 'start';

  mounted() {
    const stored = localStorage.getItem('pm_nick');
    if (stored) nickStore({ nick: stored });
    sock.loadActiveRooms().then(r => activeRoomsStore({ rooms: r, loading: false }));
    const rid = sock.detectRoomId();
    if (rid) sock.connect(rid);
  }

  #getNick() { return nickStore.nick || localStorage.getItem('pm_nick') || ''; }
  #getAvatar(): string {
    const id = Number(localStorage.getItem('pm_avatar') || 0) % 4;
    return `/static/img/avatars/avatar-0${id + 1}.png`;
  }
  #setNick(v: string) { nickStore({ nick: v }); localStorage.setItem('pm_nick', v); }
  #rerollNick() {
    const a = ['Szybki','Cichy','Wesoły','Bystry','Odważny','Sprytny','Miły','Zwinny'];
    const b = ['Wilk','Lis','Sokół','Bóbr','Żubr','Ryś','Orzeł','Kot'];
    this.#setNick(a[Math.trunc(Math.random()*8)] + b[Math.trunc(Math.random()*8)]);
  }
  #rerollAvatar() {
    const cur = Number(localStorage.getItem('pm_avatar')||0);
    const rand = Math.trunc(Math.random() * 4);
    const n = rand === cur % 4 ? (rand + 1) % 4 : rand;
    localStorage.setItem('pm_avatar', String(n)); this.update();
  }
  #ensureNick() { const n = this.#getNick() || 'Gracz'; this.#setNick(n); return n; }
  async #quickJoin() { const n = this.#ensureNick(); const rid = await sock.quickJoin(); if (rid) sock.connect(rid); }
  async #createRoom() { const n = this.#ensureNick(); const rid = await sock.createRoom(5,90,'public'); if (rid) sock.connect(rid,5,90,'public'); }
  #connectWithCode() {
    const el = this.shadowRoot?.getElementById('landing-code') as HTMLInputElement;
    const code = el?.value.trim(); if (!code) return;
    this.#ensureNick(); sock.connect(code);
  }

  render() {
    const nick = this.#getNick() || '';
    const avatar = this.#getAvatar();
    const { rooms } = activeRoomsStore;

    return html`
      <div class="hero"><h1>Państwa<span style="color:var(--accent)">Miasta</span></h1><p>Graj ze znajomymi online — bez konta.</p></div>
      ${this.#view === 'start' ? html`
        <div class="actions">
          <div class="avatar-block">
            <div class="avatar-frame"><img src=${avatar} alt="Awatar" /></div>
            <div class="nick-row">
              <input .value=${nick} @input=${(e: Event) => this.#setNick((e.target as HTMLInputElement).value.slice(0,16))} placeholder="Pseudonim" maxlength="16" style="flex:1" />
              <button class="nick-reroll" @click=${this.#rerollNick}>🎲</button>
              <button class="nick-reroll" @click=${this.#rerollAvatar}>↻</button>
            </div>
          </div>
          <button class="btn-primary" @click=${this.#createRoom}>🎮 Stwórz pokój</button>
          <button class="btn-secondary" @click=${() => { this.#view='join'; this.update(); }}>🔗 Dołącz do pokoju</button>
          <button class="btn-secondary" @click=${this.#quickJoin}>⚡ Szybka gra</button>
        </div>
      ` : html`
        <div class="actions">
          <div style="display:flex;align-items:center;gap:8px"><button class="btn-secondary btn-sm" @click=${() => { this.#view='start'; this.update(); }}>‹ Wróć</button><span style="font-weight:700">Kod pokoju</span></div>
          <div class="join-row"><input id="landing-code" placeholder="np. 4821" maxlength="12" style="flex:1" @keypress=${(e: KeyboardEvent) => e.key==='Enter' && this.#connectWithCode()} /><button class="btn-primary" @click=${this.#connectWithCode}>▶ Dołącz</button></div>
          <p style="font-size:.8rem;color:var(--text-secondary)">Pseudonim: ${nick}</p>
        </div>
      `}
      <div class="rooms-section">
        <div class="rooms-title"><h3>Aktywne pokoje</h3></div>
        ${rooms.length === 0 ? html`<div class="empty-state">Brak aktywnych pokoi. Stwórz pierwszy!</div>` :
          rooms.map((r: any) => html`
            <div class="room-card" @click=${() => { this.#ensureNick(); sock.connect(r.room_id); }}>
              <div class="room-card-left"><span class="room-card-code">${r.room_id}</span><span class="room-card-meta">${r.host_name} · ${r.player_count} graczy · ${r.rounds} rund</span></div>
              <span class="tag ${r.visibility==='public'?'tag--public':'tag--private'}">${r.visibility==='public'?'Publiczny':'Prywatny'}</span>
            </div>
          `)}
      </div>
      <a class="support-link" href="https://buycoffee.to/filki" target="_blank" rel="noopener">☕ Wesprzyj serwer</a>
    `;
  }
}

// ── Room Page ───────────────────────────────────────────────────────────────
const roomStyle = css`
  :host { display:flex;flex-direction:column;height:100%;gap:16px; }
  .room-meta { display:flex;gap:16px;flex-wrap:wrap;font-size:.85rem; }
  .room-meta dt { color:var(--text-secondary); }
  .room-meta dd { font-weight:600; }
  .game-layout { display:grid;grid-template-columns:1fr 260px;gap:16px;flex:1;min-height:0; }
  @media (max-width:700px) { .game-layout { grid-template-columns:1fr; } }
  .game-main { display:flex;flex-direction:column;gap:12px; }
  .hud { display:flex;align-items:center;justify-content:space-between;padding:12px 16px;background:var(--card-bg);border-radius:var(--radius);box-shadow:var(--shadow); }
  .hud-letter { font-family:Outfit,sans-serif;font-size:3rem;font-weight:900;color:var(--accent);line-height:1; }
  .hud-timer { font-family:Outfit,sans-serif;font-size:2rem;font-weight:700; }
  .hud-timer--urgent { color:var(--danger);animation:pulse .5s infinite; }
  .categories { display:grid;grid-template-columns:1fr;gap:8px; }
  @media (min-width:480px) { .categories { grid-template-columns:1fr 1fr; } }
  .cat-row { display:flex;align-items:center;gap:8px; }
  .cat-icon { font-size:1.2rem;width:28px;text-align:center; }
  .cat-label { font-size:.85rem;color:var(--text-secondary);width:80px;flex-shrink:0; }
  .cat-input { flex:1; }
  .cat-input input { padding:8px 12px; }
  .roster { display:flex;flex-direction:column;gap:4px; }
  .roster-item { display:flex;align-items:center;gap:8px;padding:8px 12px;border-radius:var(--radius); }
  .roster-item--host { background:rgba(79,70,229,.08); }
  .roster-avatar { width:32px;height:32px;border-radius:50%;flex-shrink:0;object-fit:cover; }
  .roster-name { font-weight:600;font-size:.9rem;flex:1; }
  .roster-score { font-weight:700;font-size:.9rem;color:var(--primary); }
  .roster-status { font-size:.75rem;color:var(--text-secondary); }
  .roster-status--ready { color:var(--success); }
  .postgame { display:flex;flex-direction:column;gap:16px;align-items:center;padding:20px; }
  .scoreboard { display:flex;flex-direction:column;gap:8px;width:100%;max-width:400px; }
  .score-row { display:flex;align-items:center;gap:12px;padding:12px 16px;background:var(--card-bg);border-radius:var(--radius);box-shadow:var(--shadow); }
  .score-row--me { border:2px solid var(--primary); }
  .score-rank { font-family:Outfit,sans-serif;font-size:1.2rem;font-weight:900;width:28px;text-align:center;color:var(--text-secondary); }
  .score-rank--gold { color:var(--accent); }
  .score-avatar { width:40px;height:40px;border-radius:50%;object-fit:cover; }
  .score-name { flex:1;font-weight:600; }
  .score-pts { font-family:Outfit,sans-serif;font-weight:900;font-size:1.2rem;color:var(--primary); }
`;

@customElement('pm-room')
@adoptedStyle(roomStyle)
@connectStore(roomStore)
@connectStore(roundStore)
@connectStore(chatStore)
@connectStore(nickStore)
export class PmRoom extends GemElement {
  #chatInput = '';

  #toggleReady() { sock.toggleReady(); }
  #sendStop() { sock.sendStop(); }
  #sendChat() { if (!this.#chatInput.trim()) return; sock.sendChat(this.#chatInput.trim()); this.#chatInput = ''; this.update(); }
  #getViewer() { return nickStore.nick; }

  #allFilled(): boolean {
    return GAME_CATEGORIES.every(c => {
      const e = this.shadowRoot?.getElementById('inp-'+c.id) as HTMLInputElement;
      return e?.value.trim().length > 0;
    });
  }

  #handleInputKey(e: KeyboardEvent, idx: number) {
    if (e.key === 'Enter') {
      if (idx < GAME_CATEGORIES.length - 1)
        (this.shadowRoot?.getElementById('inp-'+GAME_CATEGORIES[idx+1].id) as HTMLInputElement)?.focus();
      else if (!roundStore.stopped) this.#sendStop();
    }
  }

  render() {
    const { is_playing, game_over, scores, host_name, ready_players, connected_players, disconnected_players, room_id } = roomStore;
    const { letter, time_left, stopped } = roundStore;
    const { messages } = chatStore;
    const viewer = this.#getViewer();
    const discoSet = new Set(disconnected_players || []);
    const readySet = new Set(ready_players || []);
    const allFilled = roundStore.round_active ? this.#allFilled() : false;
    const sorted = Object.entries(scores || {}).sort((a,b) => (b[1] as number) - (a[1] as number));

    if (room_id == null || room_id === '') return html`<div class="flex-center" style="height:100%"><p>Łączenie z pokojem…</p></div>`;

    if (is_playing && game_over === false) return html`
      <div class="hud">
        <span class="hud-letter">${letter}</span>
        <span class="hud-timer ${time_left <= 10 ? 'hud-timer--urgent' : ''}">${time_left}s</span>
        <div class="room-meta"><dl><dt>Pokój</dt><dd>${room_id}</dd></dl></div>
      </div>
      <div class="game-layout">
        <div class="game-main">
          <div class="categories">
            ${GAME_CATEGORIES.map((cat,i) => html`
              <div class="cat-row"><span class="cat-icon">${cat.icon}</span><span class="cat-label">${cat.label}</span><span class="cat-input"><input id="inp-${cat.id}" .disabled=${stopped} placeholder="${cat.label} na ${letter}…" @keypress=${(e: KeyboardEvent) => this.#handleInputKey(e,i)} /></span></div>
            `)}
          </div>
          <div style="text-align:center"><button class="btn-accent" style="padding:12px 24px;font-size:1.1rem" .disabled=${stopped||!allFilled} @click=${this.#sendStop}>🛑 STOP!</button></div>
        </div>
        <pm-chat-panel .messages=${messages} .chatInput=${this.#chatInput} @chatinput=${(e: CustomEvent) => { this.#chatInput = e.detail; }} @chatsend=${() => this.#sendChat()}></pm-chat-panel>
      </div>
    `;

    if (game_over) return html`
      <div class="postgame">
        <h2>🏆 Koniec gry!</h2>
        <div class="scoreboard">
          ${sorted.map(([name, pts], i) => html`
            <div class="score-row ${name===viewer?'score-row--me':''}">
              <span class="score-rank ${i===0?'score-rank--gold':''}">${i+1}</span>
              <img class="score-avatar" src=${avatarUrl(name, viewer)} alt="" />
              <span class="score-name">${esc(name)}${name===host_name?' 👑':''}</span>
              <span class="score-pts">${pts}p</span>
            </div>
          `)}
        </div>
        <pm-chat-panel .messages=${messages} .chatInput=${this.#chatInput} @chatinput=${(e: CustomEvent) => { this.#chatInput = e.detail; }} @chatsend=${() => this.#sendChat()}></pm-chat-panel>
      </div>
    `;

    return html`
      <div class="game-layout">
        <div class="game-main">
          <div class="card">
            <div class="room-meta" style="margin-bottom:12px">
              <dl><dt>Pokój</dt><dd>${room_id}</dd></dl>
              <dl><dt>Host</dt><dd>${esc(host_name||'—')}</dd></dl>
              <dl><dt>Gracze</dt><dd>${(connected_players||[]).length}${discoSet.size>0?` (${discoSet.size} rozł.)`:''}</dd></dl>
            </div>
            <h3 style="margin-bottom:8px">Gracze w lobby</h3>
            <div class="roster">
              ${(connected_players||[]).map(name => html`
                <div class="roster-item ${name===host_name?'roster-item--host':''}">
                  <img class="roster-avatar" src=${avatarUrl(name, viewer)} alt="" />
                  <span class="roster-name">${esc(name)}${name===host_name?' 👑':''}</span>
                  ${(() => { const ready = readySet.has(name); const disco = discoSet.has(name); const label = ready ? '✓ Gotowy' : (disco ? 'Rozłączony' : '—'); return html`<span class="roster-status ${ready?'roster-status--ready':''}">${label}</span>`})() }
                  ${scores?.[name] !== undefined ? html`<span class="roster-score">${String(scores[name])}p</span>` : null}
                </div>
              `)}
              ${(disconnected_players||[]).filter(n => (connected_players||[]).includes(n) === false).map(name => html`
                <div class="roster-item" style="opacity:.5"><span class="roster-name">${esc(name)}</span><span class="roster-status">Rozłączony</span></div>
              `)}
            </div>
            <div style="display:flex;gap:8px;margin-top:12px;justify-content:center">
              <button class="btn-primary" @click=${this.#toggleReady}>${readySet.has(viewer)?'⏳ Czekamy…':'👍 Gotowy'}</button>
              ${viewer===host_name?html`<button class="btn-danger btn-sm" @click=${()=>{if(confirm('Rozwiązać pokój?'))sock.dissolveRoom();}}>Rozwiąż</button>`:''}
            </div>
          </div>
        </div>
        <pm-chat-panel .messages=${messages} .chatInput=${this.#chatInput} @chatinput=${(e: CustomEvent) => { this.#chatInput = e.detail; }} @chatsend=${() => this.#sendChat()}></pm-chat-panel>
      </div>
    `;
  }
}

// ── Chat Panel ──────────────────────────────────────────────────────────────
@customElement('pm-chat-panel')
@adoptedStyle(css`
  :host { display:flex;flex-direction:column;background:var(--card-bg);border-radius:var(--radius-lg);box-shadow:var(--shadow);overflow:hidden;min-height:200px; }
  .ch { padding:12px 16px;font-weight:700;border-bottom:1px solid var(--border);font-size:.9rem; }
  .cm { flex:1;overflow-y:auto;padding:8px;font-size:.85rem;max-height:300px; }
  .msg { margin-bottom:4px;line-height:1.4; }
  .ms { font-weight:700;color:var(--primary); }
  .my { color:var(--text-secondary);font-style:italic; }
  .cr { display:flex;gap:4px;padding:8px;border-top:1px solid var(--border); }
`)
export class PmChatPanel extends GemElement {
  @property messages?: any[];
  @property chatInput?: string;

  render() {
    const msgs = (this.messages || []).slice(-50);
    return html`
      <div class="ch">💬 Czat</div>
      <div class="cm">${msgs.map(m => { const system = m.type==='system'; const text = m.text; return system ? html`<span class="my">${text}</span>` : html`<span class="ms">${m.sender}:</span> ${text}`; })}</div>
      <div class="cr">
        <input .value=${this.chatInput||''} placeholder="Napisz…" maxlength="200" @input=${(e:Event)=>this.dispatchEvent(new CustomEvent('chatinput',{detail:(e.target as HTMLInputElement).value}))} @keypress=${(e:KeyboardEvent)=>e.key==='Enter'&&this.dispatchEvent(new CustomEvent('chatsend'))} />
        <button class="btn-primary btn-sm" @click=${()=>this.dispatchEvent(new CustomEvent('chatsend'))}>Wyślij</button>
      </div>
    `;
  }
}

// ── Lottery Overlay ─────────────────────────────────────────────────────────
@customElement('pm-lottery-overlay')
@adoptedStyle(css`
  :host { position:fixed;inset:0;z-index:100;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.7); }
  :host([hidden]) { display:none; }
  .letter { font-family:Outfit,sans-serif;font-size:8rem;font-weight:900;color:var(--accent);text-shadow:0 0 40px rgba(245,158,11,.5); }
`)
@connectStore(overlayStore)
export class PmLotteryOverlay extends GemElement {
  render() {
    const { lottery, lotteryLetter } = overlayStore;
    this.hidden = !lottery;
    return html`<span class="letter">${lotteryLetter}</span>`;
  }
}

// ── Countdown Overlay ───────────────────────────────────────────────────────
@customElement('pm-countdown-overlay')
@adoptedStyle(css`
  :host { position:fixed;inset:0;z-index:99;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.6); }
  :host([hidden]) { display:none; }
  .num { font-family:Outfit,sans-serif;font-size:6rem;font-weight:900;color:#fff; }
`)
@connectStore(overlayStore)
export class PmCountdownOverlay extends GemElement {
  render() {
    const { roundCountdown, roundCountdownNum } = overlayStore;
    this.hidden = !roundCountdown;
    return html`<span class="num">${roundCountdownNum}</span>`;
  }
}

// ── Results Overlay ─────────────────────────────────────────────────────────
@customElement('pm-results-overlay')
@adoptedStyle(css`
  :host { position:fixed;inset:0;z-index:90;display:flex;align-items:center;justify-content:center; }
  :host([hidden]) { display:none; }
  .backdrop { position:absolute;inset:0;background:rgba(0,0,0,.5); }
  .modal { position:relative;background:var(--card-bg);border-radius:var(--radius-lg);padding:24px;max-width:600px;width:95%;max-height:85vh;overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,.3); }
  .head { display:flex;align-items:center;justify-content:space-between;margin-bottom:16px; }
  .title { font-family:Outfit,sans-serif;font-size:1.3rem;font-weight:700; }
  .letter-tag { display:inline-block;padding:4px 12px;background:var(--accent);color:#fff;border-radius:8px;font-weight:700;font-size:.9rem; }
  .pc { background:var(--bg);border-radius:var(--radius);padding:12px;margin-bottom:8px; }
  .pc--me { border:2px solid var(--primary); }
  .ph { display:flex;align-items:center;gap:8px;margin-bottom:8px; }
  .pa { width:28px;height:28px;border-radius:50%; }
  .pn { font-weight:600;flex:1; }
  .pt { font-weight:700;color:var(--primary); }
  .pans { display:flex;flex-direction:column;gap:2px;font-size:.85rem;padding-left:36px; }
  .ar { display:flex;justify-content:space-between; }
  .ac { color:var(--text-secondary); }
  .aw { font-weight:500; }
  .ap { font-weight:700;min-width:24px;text-align:right; }
`)
@connectStore(resultsStore)
@connectStore(overlayStore)
@connectStore(nickStore)
export class PmResultsOverlay extends GemElement {
  render() {
    const { roundResults } = overlayStore;
    const { round_scores, answers, letter, round_number } = resultsStore;
    if (!roundResults || !answers || !round_scores) { this.hidden = true; return html``; }
    this.hidden = false;
    const viewer = nickStore.nick;
    const players = Object.keys(round_scores).sort((a,b) => round_scores[b] - round_scores[a]);

    return html`
      <div class="backdrop" @click=${() => overlayStore({ roundResults: false })}></div>
      <div class="modal">
        <div class="head"><span class="title">Wyniki rundy ${round_number||''} <span class="letter-tag">${letter||''}</span></span><button class="btn-secondary btn-sm" @click=${() => overlayStore({ roundResults: false })}>✕</button></div>
        ${players.map(name => html`
          <div class="pc ${name===viewer?'pc--me':''}">
            <div class="ph"><img class="pa" src=${avatarUrl(name, viewer)} alt="" /><span class="pn">${esc(name)}</span><span class="pt">${round_scores[name]||0}p</span></div>
            <div class="pans">
              ${GAME_CATEGORIES.map(cat => html`
                <div class="ar"><span class="ac">${cat.icon} ${cat.label}</span><span class="aw">${esc(String(answers[name]?.[cat.id]||'—'))}</span></div>
              `)}
            </div>
          </div>
        `)}
        <button class="btn-primary" style="margin-top:16px;width:100%" @click=${() => overlayStore({ roundResults: false })}>Zamknij</button>
      </div>
    `;
  }
}
