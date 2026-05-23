// Simple Audio Synthesizer
let audioCtx = null;

function initAudio() {
    if (!audioCtx) {
        audioCtx = new (globalThis.AudioContext || globalThis.webkitAudioContext)();
    }
    if (audioCtx.state === 'suspended') {
        audioCtx.resume();
    }
}

function playTick() {
    if (!audioCtx) return;
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.type = 'sine';
    osc.frequency.setValueAtTime(800, audioCtx.currentTime);
    gain.gain.setValueAtTime(0.05, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.1);
    osc.start();
    osc.stop(audioCtx.currentTime + 0.1);
}

function playGong() {
    if (!audioCtx) return;
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(150, audioCtx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(40, audioCtx.currentTime + 1.5);
    gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 1.5);
    osc.start();
    osc.stop(audioCtx.currentTime + 1.5);
}

function playLotterySpinTick(elapsed, duration) {
    if (!audioCtx) return;
    const safeDur = Math.max(duration, 1);
    const progress = Math.min(1, elapsed / safeDur);
    const freq = 380 + progress * 520;
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.type = 'sine';
    const t = audioCtx.currentTime;
    osc.frequency.setValueAtTime(freq, t);
    gain.gain.setValueAtTime(0.038, t);
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.034);
    osc.start(t);
    osc.stop(t + 0.036);
}

function playRoundStartReveal() {
    if (!audioCtx) return;
    const t0 = audioCtx.currentTime;
    const notes = [523.25, 659.25];
    notes.forEach((freq, i) => {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = 'sine';
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        const start = t0 + i * 0.07;
        osc.frequency.setValueAtTime(freq, start);
        gain.gain.setValueAtTime(0, start);
        gain.gain.linearRampToValueAtTime(0.13, start + 0.025);
        gain.gain.exponentialRampToValueAtTime(0.001, start + 0.32);
        osc.start(start);
        osc.stop(start + 0.33);
    });
}

if (typeof module !== 'undefined') {
    module.exports = {
        initAudio,
        playTick,
        playGong,
        playLotterySpinTick,
        playRoundStartReveal,
    };
}
