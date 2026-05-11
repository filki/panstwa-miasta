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

function sendChat() {
    const input = document.getElementById('message-input');
    if (input && input.value.trim()) {
        sendJson({ type: "chat", text: input.value.trim() });
        input.value = '';
    }
}

// Modal Management
function showJoinModal() {
    const modal = document.getElementById('join-modal');
    if (modal) modal.style.display = 'flex';
}

function showCreateModal() {
    const modal = document.getElementById('create-modal');
    if (modal) modal.style.display = 'flex';
}

function hideModals() {
    const joinModal = document.getElementById('join-modal');
    const createModal = document.getElementById('create-modal');
    if (joinModal) joinModal.style.display = 'none';
    if (createModal) createModal.style.display = 'none';
}

async function loadActiveRooms() {
    try {
        const response = await fetch('/api/active-rooms');
        const rooms = await response.json();
        
        const section = document.getElementById('active-rooms-section');
        const list = document.getElementById('rooms-list');
        
        if (!rooms || rooms.length === 0) {
            if (section) section.style.display = 'none';
            return;
        }
        
        if (section) section.style.display = 'block';
        if (list) {
            list.innerHTML = '';
            rooms.forEach(room => {
                const card = document.createElement('div');
                card.className = 'room-card';
                card.onclick = () => {
                    const roomIdInput = document.getElementById('room_id');
                    if (roomIdInput) roomIdInput.value = room.id;
                    showJoinModal();
                };
                
                const info = document.createElement('div');
                info.className = 'room-info';
                const h4 = document.createElement('h4');
                h4.textContent = `Pokój #${room.id}`;
                const p = document.createElement('p');
                p.innerHTML = `Host: <strong>${room.host}</strong> | Runda: ${room.round}/${room.max_rounds}`;
                info.appendChild(h4);
                info.appendChild(p);

                const count = document.createElement('div');
                count.className = 'player-count';
                count.innerHTML = `<div class="live-dot"></div> ${room.players} graczy`;

                card.appendChild(info);
                card.appendChild(count);
                list.appendChild(card);
            });
        }
    } catch (err) {
        console.error("Błąd podczas ładowania pokoi:", err);
    }
}

globalThis.window.onload = () => {
    const savedNick = localStorage.getItem('pm_nickname');
    if (savedNick && document.getElementById('nickname')) {
        document.getElementById('nickname').value = savedNick;
    }

    // Obsługa wejścia z linku /room/ID
    const pathParts = globalThis.location.pathname.split('/');
    if (pathParts.length >= 3 && pathParts[1] === 'room') {
        const roomId = pathParts[2];
        const roomIdInput = document.getElementById('room_id');
        if (roomIdInput) {
            roomIdInput.value = roomId;
            showJoinModal();
        }
    }
    
    // Załaduj aktywne pokoje na starcie
    loadActiveRooms();
    // Odświeżaj co 10 sekund
    setInterval(loadActiveRooms, 10000);

    // Obsługa Entera na czacie
    const msgInput = document.getElementById('message-input');
    if (msgInput) {
        msgInput.addEventListener('keypress', e => {
            if (e.key === 'Enter') sendChat();
        });
    }

    // Dynamiczna obsługa inputów kategorii (Enter przechodzi do następnego)
    const catInputs = document.querySelectorAll('#categories input');
    catInputs.forEach((inp, i) => {
        inp.addEventListener('keypress', e => {
            if (e.key === 'Enter') {
                if (i < catInputs.length - 1) {
                    catInputs[i + 1].focus();
                } else {
                    const stopBtn = document.getElementById('btn-stop');
                    if (stopBtn && !stopBtn.disabled) stopGame();
                }
            }
        });
    });
};

if (typeof module !== 'undefined') {
    module.exports = {
        addLog,
        updateScoreboard,
        sendChat,
        loadActiveRooms,
        showJoinModal,
        showCreateModal,
        hideModals
    };
}
