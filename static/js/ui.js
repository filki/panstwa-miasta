function addLog(content, typeClass, isRawHtml = true) {
    const logsDiv = document.getElementById('logs');
    if (!logsDiv) return;
    const entry = document.createElement('div');
    entry.className = `log-entry ${typeClass}`;
    if (content instanceof HTMLElement) {
        entry.appendChild(content);
    } else if (isRawHtml) {
        entry.innerHTML = content;
    } else {
        entry.textContent = content;
    }
    logsDiv.appendChild(entry);
    logsDiv.scrollTop = logsDiv.scrollHeight;
}

function updateScoreboard(scores, hostName) {
    const sb = document.getElementById('scoreboard');
    if (!sb) return;
    sb.innerHTML = '';
    // Sortujemy malejąco po wynikach
    const sorted = Object.entries(scores).sort((a, b) => b[1] - a[1]);
    
    sorted.forEach(([player, score]) => {
        const div = document.createElement('div');
        div.className = 'score-item';
        if (player === hostName) div.classList.add('is-host');
        
        const nameSpan = document.createElement('span');
        if (player === hostName) {
            const crown = document.createElement('span');
            crown.className = 'crown';
            crown.textContent = '👑';
            nameSpan.appendChild(crown);
        }
        nameSpan.appendChild(document.createTextNode(player));
        
        const scoreStrong = document.createElement('strong');
        scoreStrong.textContent = ` ${score} pkt`;
        
        div.appendChild(nameSpan);
        div.appendChild(scoreStrong);
        sb.appendChild(div);
    });
}

function showJoinInputs() {
    document.getElementById('join-inputs').style.display = 'block';
}

function createRoom() {
    const nickname = document.getElementById('nickname').value.trim();
    if (!nickname) return alert('Proszę najpierw podać swój nick!');
    
    document.getElementById('buttons-grid').style.display = 'none';
    document.getElementById('create-settings').style.display = 'block';
}

function doCreateRoom() {
    const array = new Uint32Array(1);
    globalThis.crypto.getRandomValues(array);
    const randomCode = (1000 + (array[0] % 9000)).toString();
    document.getElementById('room_id').value = randomCode;
    globalThis.roomRounds = document.getElementById('rounds-input').value || 5;
    globalThis.roomLimit = document.getElementById('limit-input').value || 90;
    connect();
}

function sendChat() {
    const input = document.getElementById('message-input');
    if (input.value.trim()) {
        sendJson({ type: "chat", text: input.value.trim() });
        input.value = '';
    }
}
async function loadActiveRooms() {
    try {
        const response = await fetch('/api/active-rooms');
        const rooms = await response.json();
        
        const section = document.getElementById('active-rooms-section');
        const list = document.getElementById('rooms-list');
        
        if (!rooms || rooms.length === 0) {
            section.style.display = 'none';
            return;
        }
        
        section.style.display = 'block';
        list.innerHTML = '';
        
        rooms.forEach(room => {
            const card = document.createElement('div');
            card.className = 'room-card';
            card.onclick = () => {
                document.getElementById('room_id').value = room.id;
                showJoinInputs();
                document.getElementById('buttons-grid').style.display = 'none';
                globalThis.scrollTo({ top: 0, behavior: 'smooth' });
            };
            
            const info = document.createElement('div');
            info.className = 'room-info';
            const h4 = document.createElement('h4');
            h4.textContent = `Pokój #${room.id}`;
            const p = document.createElement('p');
            p.textContent = `Host: `;
            const strongHost = document.createElement('strong');
            strongHost.textContent = room.host;
            p.appendChild(strongHost);
            p.appendChild(document.createTextNode(` | Runda: ${room.round}`));
            info.appendChild(h4);
            info.appendChild(p);

            const count = document.createElement('div');
            count.className = 'player-count';
            const dot = document.createElement('div');
            dot.className = 'live-dot';
            count.appendChild(dot);
            count.appendChild(document.createTextNode(` ${room.players} graczy`));

            card.appendChild(info);
            card.appendChild(count);
            list.appendChild(card);
        });
    } catch (err) {
        console.error("Błąd podczas ładowania pokoi:", err);
    }
}

if (typeof module !== 'undefined') {
    module.exports = {
        addLog,
        updateScoreboard,
        showJoinInputs,
        createRoom,
        doCreateRoom,
        sendChat,
        loadActiveRooms
    };
}
