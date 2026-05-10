let ws;
let myNick = "";

function sendJson(obj) {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}

function connect() {
    initAudio();
    myNick = document.getElementById('nickname').value.trim();
    const roomId = document.getElementById('room_id').value.trim();

    if (!myNick || !roomId) return alert('Proszę podać nick i upewnić się, że masz ID pokoju.');

    // Zapisz na przyszłość
    localStorage.setItem('pm_nickname', myNick);
    
    // Podmień URL żeby łatwo było go skopiować i wysłać znajomym!
    window.history.replaceState(null, '', `?room=${roomId}`);

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    let wsUrl = `${protocol}//${window.location.host}/ws/${roomId}/${myNick}`;
    
    if (window.roomRounds && window.roomLimit) {
        wsUrl += `?rounds=${window.roomRounds}&limit=${window.roomLimit}`;
    }
    
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        document.getElementById('join-section').style.display = 'none';
        document.getElementById('chat-section').style.display = 'block';
        document.getElementById('btn-leave').style.display = 'block';
        document.getElementById('current-room').textContent = roomId;
    };

    ws.onclose = (e) => {
        if (e.code === 1008) {
            alert('Nick jest już zajęty lub nieprawidłowy!');
            return;
        }
        
        // Automatyczny reconnect (np. po wyjściu z Safari/Chrome na telefonie)
        addLog(`<em>Utracono połączenie. Próba wznowienia za 2 sekundy...</em>`, "system-msg");
        setTimeout(() => {
            // Ponawiamy próbę łączenia bez resetowania wpisanych haseł
            if (document.getElementById('chat-section').style.display !== 'none') {
                connect();
            }
        }, 2000);
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        
        if (msg.type === "system") {
            addLog(`<em>${msg.message}</em>`, "system-msg");
        } 
        else if (msg.type === "score_update") {
            updateScoreboard(msg.scores, msg.host_name);
        }
        else if (msg.type === "chat") {
            addLog(`<div class="sender">${msg.sender}</div><div>${msg.text}</div>`, "");
        }
        else if (msg.type === "round_started") {
            window.currentLetter = msg.letter;
            
            // Animacja losowania!
            runLetterLottery(msg.letter, () => {
                document.getElementById("current-letter").textContent = msg.letter;
                
                // Reset statusu przycisku po starcie
                const btn = document.getElementById("btn-draw");
                btn.classList.remove('ready');
                btn.style.display = 'none';
                
                addLog(`<em>Gra rozpoczęta! Litera: <strong>${msg.letter}</strong> (Runda ${msg.current_round}/${msg.max_rounds}). Limit czasu: ${msg.time_limit}s</em>`, "system-msg");
                enableInputs();
                
                // Włącz globalny timer
                let timeLeft = msg.time_limit;
                document.getElementById("round-timer").textContent = timeLeft + "s";
                document.getElementById("round-timer").style.display = "block";
                
                if (window.globalRoundTimer) clearInterval(window.globalRoundTimer);
                window.globalRoundTimer = setInterval(() => {
                    timeLeft--;
                    if (timeLeft >= 0) {
                        document.getElementById("round-timer").textContent = timeLeft + "s";
                    }
                }, 1000);
            });
        }
        else if (msg.type === "stop_round") {
            playGong();
            if (window.globalRoundTimer) clearInterval(window.globalRoundTimer);
            document.getElementById("round-timer").style.display = "none";
            
            addLog(`<em>🚨 <strong>${msg.sender} zatrzymał rundę!</strong> Oczekiwanie na przesłanie odpowiedzi... Masz 10 sekund!</em>`, "system-msg");
            
            // Zablokuj przycisk STOP dla wszystkich
            const btnStop = document.getElementById('btn-stop');
            btnStop.disabled = true;
            
            // Pokazujemy fixed banner na górze (idealne na mobilki)
            const stickyTimer = document.getElementById('sticky-timer');
            const stickyTime = document.getElementById('sticky-time');
            if (stickyTimer) {
                stickyTimer.style.display = 'block';
                stickyTime.innerText = '10';
            }
            
            // Pokazujemy wielki odliczacz na środku ekranu oraz na przycisku STOP
            document.getElementById('current-letter').innerHTML = `<span style="color:var(--danger)">10s</span>`;
            btnStop.innerHTML = `⏳ 10s`;
            
            let timeLeft = 10;
            const countdownInterval = setInterval(() => {
                timeLeft--;
                if(timeLeft > 0) {
                    document.getElementById('current-letter').innerHTML = `<span style="color:var(--danger)">${timeLeft}s</span>`;
                    btnStop.innerHTML = `⏳ ${timeLeft}s`;
                    if (stickyTime) stickyTime.innerText = timeLeft;
                    playTick();
                } else {
                    clearInterval(countdownInterval);
                    btnStop.innerHTML = `WYSYŁANIE...`;
                    if (stickyTimer) stickyTimer.style.display = 'none';
                    disableAndSubmit();
                }
            }, 1000);
            
            // Zapisujemy ID intervalu do window, żeby można go było wyczyścić przy ew. ręcznym wyjściu
            window.currentCountdown = countdownInterval;
        }
        else if (msg.type === "round_results") {
            if(window.currentCountdown) clearInterval(window.currentCountdown);
            if(window.globalRoundTimer) clearInterval(window.globalRoundTimer);
            document.getElementById("round-timer").style.display = "none";
            
            // UKRYWAMY BANER STOP, który Cię wkurzał :)
            const stickyTimer = document.getElementById('sticky-timer');
            if (stickyTimer) stickyTimer.style.display = 'none';
            
            // Przywracamy literę lub czyścimy odliczanie
            document.getElementById('current-letter').innerHTML = window.currentLetter || '?';
            
            // Resetujemy przycisk STOP
            const btnStop = document.getElementById('btn-stop');
            btnStop.innerHTML = '🛑 STOP!';
            btnStop.disabled = true;
            
            let html = `<div class="sender">Wyniki Rundy:</div>`;
            
            // Pokazujemy ile kto dostał punktów w tej rundzie
            for (const [player, rScore] of Object.entries(msg.round_scores)) {
                html += `<div style="margin-bottom: 0.5rem"><strong>${player}: +${rScore.total} pkt</strong><br>`;
                const pAnswers = msg.answers[player] || {};
                for (const [cat, val] of Object.entries(pAnswers)) {
                    if(val) {
                        const pts = rScore.details[cat] || 0;
                        let color = "var(--text-muted)";
                        if (pts === 10) color = "var(--accent)";
                        else if (pts === 5) color = "var(--warning)";
                        else color = "var(--danger)";
                        html += `<span style="font-size:0.8em; color:${color};">${cat}:</span> ${val} `;
                    }
                }
                html += `</div>`;
                
                // Kolorowanie własnych inputów
                if (player === myNick) {
                    const inputs = document.querySelectorAll('#categories input');
                    inputs.forEach(inp => {
                        const cat = inp.dataset.category;
                        const pts = rScore.details[cat];
                        inp.classList.remove('success-10', 'warning-5', 'error-0');
                        if(pts === 10) inp.classList.add('success-10');
                        else if(pts === 5) inp.classList.add('warning-5');
                        else inp.classList.add('error-0');
                    });
                }
            }
            
            addLog(html, "results-msg");
            updateScoreboard(msg.total_scores, msg.host_name);
            
            if (msg.game_over) {
                html += `<div style="margin-top:1rem; font-weight:800; color:var(--danger); text-align:center;">🏁 Koniec Gry! Zwycięzca został wyłoniony!</div>`;
                document.getElementById('btn-draw').style.display = 'none';
                document.getElementById('restart-settings').style.display = 'block';
                
                // Pokazujemy przyciski hosta tylko hostowi
                if (myNick === msg.host_name) {
                    document.getElementById('btn-restart-game').style.display = 'block';
                    document.getElementById('btn-dissolve').style.display = 'block';
                }

                confetti({ particleCount: 150, spread: 100, origin: { y: 0.3 } });
                setTimeout(() => confetti({ particleCount: 150, spread: 120, origin: { y: 0.4 } }), 1000);
            } else {
                const btn = document.getElementById('btn-draw');
                btn.classList.remove('ready');
                btn.innerHTML = '👍 Gotowy do rundy';
                btn.style.backgroundColor = 'var(--primary)';
                btn.style.display = 'block';
            }
        }
        else if (msg.type === "game_restarted") {
            document.getElementById('restart-settings').style.display = 'none';
            const btn = document.getElementById('btn-draw');
            btn.style.display = 'inline-block';
            btn.classList.remove('ready');
            btn.innerHTML = '👍 Gotowy do rundy';
            btn.style.backgroundColor = 'var(--primary)';
            
            document.getElementById('current-letter').innerHTML = '?';
            updateScoreboard(msg.scores, msg.host_name);
            
            const inputs = document.querySelectorAll('#categories input');
            inputs.forEach(inp => {
                inp.value = '';
                inp.disabled = true;
                inp.classList.remove('error', 'success-10', 'warning-5', 'error-0');
            });
            
            addLog(`<em>Gospodarz <strong>${msg.sender}</strong> zrestartował grę z nowymi ustawieniami! Wyniki zostały wyzerowane.</em>`, "system-msg");
        }
        else if (msg.type === "room_dissolved") {
            alert(msg.message);
            window.location.href = window.location.pathname;
        }
    };

    ws.onerror = (e) => {
        console.error("WS Error:", e);
        // if(e.code === 1008) alert('Nick zajęty!');
        // window.location.reload();
    };
}

function runLetterLottery(targetLetter, onComplete) {
    const modal = document.getElementById('lottery-modal');
    const letterDiv = document.getElementById('lottery-letter');
    const alphabet = "ABCDEFGHIJKLMNOPRSTUWZ";
    
    modal.style.display = 'flex';
    
    let duration = 2500; // 2.5 sekundy
    let intervalTime = 50;
    let elapsed = 0;
    
    const interval = setInterval(() => {
        elapsed += intervalTime;
        
        // Wybieramy losową literę z alfabetu
        const randomLetter = alphabet[Math.floor(Math.random() * alphabet.length)];
        letterDiv.innerText = randomLetter;
        
        // Efekt rozmycia przy dużych prędkościach
        letterDiv.style.filter = `blur(${Math.max(0, 5 - (elapsed/duration)*5)}px)`;
        
        if (elapsed >= duration) {
            clearInterval(interval);
            letterDiv.innerText = targetLetter;
            letterDiv.style.filter = 'none';
            letterDiv.style.transform = 'scale(1.2)';
            letterDiv.style.color = 'var(--success)';
            
            // Strzał confetti przy wylosowaniu!
            confetti({
                particleCount: 100,
                spread: 70,
                origin: { y: 0.6 }
            });
            
            setTimeout(() => {
                modal.style.display = 'none';
                letterDiv.style.transform = 'scale(1)';
                letterDiv.style.color = 'var(--accent)';
                if (onComplete) onComplete();
            }, 1500);
        }
    }, intervalTime);
}
