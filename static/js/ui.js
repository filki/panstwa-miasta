function addLog(htmlContent, typeClass) {
    const logsDiv = document.getElementById('logs');
    if (!logsDiv) return;
    const entry = document.createElement('div');
    entry.className = `log-entry ${typeClass}`;
    entry.innerHTML = htmlContent;
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
        
        const crown = player === hostName ? '<span class="crown">👑</span>' : '';
        div.innerHTML = `<span>${crown}${player}</span> <strong>${score} pkt</strong>`;
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
    const randomCode = Math.floor(1000 + Math.random() * 9000).toString();
    document.getElementById('room_id').value = randomCode;
    window.roomRounds = document.getElementById('rounds-input').value || 5;
    window.roomLimit = document.getElementById('limit-input').value || 90;
    connect();
}

function sendChat() {
    const input = document.getElementById('message-input');
    if (input.value.trim()) {
        sendJson({ type: "chat", text: input.value.trim() });
        input.value = '';
    }
}
