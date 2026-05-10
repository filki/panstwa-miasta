function toggleReady() {
    const btn = document.getElementById('btn-draw');
    if (btn.classList.contains('ready')) {
        btn.classList.remove('ready');
        btn.innerHTML = '👍 Gotowy do rundy';
        btn.style.backgroundColor = 'var(--primary)';
        sendJson({ type: "not_ready" });
    } else {
        btn.classList.add('ready');
        btn.innerHTML = '⏳ Czekamy na resztę...';
        btn.style.backgroundColor = 'var(--accent)';
        sendJson({ type: "ready" });
    }
}

function stopGame() {
    const stopBtn = document.getElementById('btn-stop');
    stopBtn.setAttribute('data-stopped', 'true');
    stopBtn.disabled = true;
    
    // Natychmiastowe wysłanie swoich wyników jak się wciśnie STOP
    sendJson({ type: "stop" });
    disableAndSubmit();
}

function requestRestart() {
    const rounds = parseInt(document.getElementById('restart-rounds').value) || 5;
    const limit = parseInt(document.getElementById('restart-limit').value) || 90;
    sendJson({
        type: "restart_game",
        rounds: rounds,
        limit: limit
    });
    document.getElementById('restart-settings').style.display = 'none';
}

function dissolveRoom() {
    if (confirm("Czy na pewno chcesz rozwiązać pokój? Wszyscy zostaną rozłączeni!")) {
        sendJson({ type: "dissolve_room" });
    }
}

function enableInputs() {
    if(window.currentCountdown) clearInterval(window.currentCountdown);
    const inputs = document.querySelectorAll('#categories input');
    inputs.forEach(inp => {
        inp.disabled = false;
        inp.value = '';
        inp.classList.remove('error', 'success-10', 'warning-5', 'error-0'); 
        inp.style.borderColor = '';
        
        // Remove stare listenery, żeby się nie duplikowały
        const clone = inp.cloneNode(true);
        inp.parentNode.replaceChild(clone, inp);
    });
    
    // Ponownie łapiemy, bo zrobiliśmy cloneNode
    const newInputs = document.querySelectorAll('#categories input');
    newInputs.forEach((inp, i) => {
        inp.addEventListener('input', (e) => {
            checkAllFilled();
            validateFirstLetter(e.target);
        });
        
        // Zgłaszaj odpowiedzi Enterem
        inp.addEventListener('keypress', e => {
            if (e.key === 'Enter') {
                if(i < newInputs.length - 1) newInputs[i+1].focus();
                else {
                    const stopBtn = document.getElementById('btn-stop');
                    if(!stopBtn.disabled) stopGame(); // Ostatni input i enter = STOP!
                }
            }
        });
    });
    
    const btnStop = document.getElementById('btn-stop');
    btnStop.disabled = true;
    btnStop.removeAttribute('data-stopped');
    btnStop.innerHTML = '🛑 STOP!';
    
    // Przywracamy literę jeśli zniknęła
    if(window.currentLetter) {
        document.getElementById('current-letter').innerHTML = window.currentLetter;
    }
}

function checkAllFilled() {
    const inputs = Array.from(document.querySelectorAll('#categories input'));
    const allFilled = inputs.every(inp => inp.value.trim().length > 0);
    const stopBtn = document.getElementById('btn-stop');
    
    if (allFilled && !stopBtn.hasAttribute('data-stopped')) {
        stopBtn.disabled = false;
    } else {
        stopBtn.disabled = true;
    }
}

function validateFirstLetter(inp) {
    if (!window.currentLetter) return;
    const val = inp.value.trim();
    if (val.length > 0 && val[0].toUpperCase() !== window.currentLetter) {
        inp.style.borderColor = 'var(--danger)';
    } else {
        inp.style.borderColor = ''; 
    }
}

function disableAndSubmit() {
    const inputs = document.querySelectorAll('#categories input');
    let answers = {};
    inputs.forEach(inp => {
        answers[inp.dataset.category] = inp.value.trim();
        inp.disabled = true;
    });
    
    document.getElementById('btn-stop').disabled = true;
    sendJson({ type: "answers", answers: answers });
}
