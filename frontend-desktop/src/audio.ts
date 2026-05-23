export function initAudio(): AudioContext {
  const ctx = new (globalThis.AudioContext ?? (globalThis as any).webkitAudioContext)();
  if (ctx.state === 'suspended') ctx.resume();
  return ctx;
}

export function playTick(ctx?: AudioContext) {
  ctx ??= initAudio();
  const o = ctx.createOscillator();
  const g = ctx.createGain();
  o.connect(g); g.connect(ctx.destination);
  o.type = 'sine'; o.frequency.setValueAtTime(800, ctx.currentTime);
  g.gain.setValueAtTime(0.05, ctx.currentTime);
  g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.1);
  o.start(); o.stop(ctx.currentTime + 0.1);
}

export function playGong(ctx?: AudioContext) {
  ctx ??= initAudio();
  const o = ctx.createOscillator();
  const g = ctx.createGain();
  o.connect(g); g.connect(ctx.destination);
  o.type = 'triangle'; o.frequency.setValueAtTime(150, ctx.currentTime);
  o.frequency.exponentialRampToValueAtTime(40, ctx.currentTime + 1.5);
  g.gain.setValueAtTime(0.3, ctx.currentTime);
  g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 1.5);
  o.start(); o.stop(ctx.currentTime + 1.5);
}

export function playRoundStartReveal(ctx?: AudioContext) {
  ctx ??= initAudio();
  const t0 = ctx.currentTime;
  [523.25, 659.25].forEach((f, i) => {
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.type = 'sine'; o.connect(g); g.connect(ctx.destination);
    const s = t0 + i * 0.07;
    o.frequency.setValueAtTime(f, s);
    g.gain.setValueAtTime(0, s);
    g.gain.linearRampToValueAtTime(0.13, s + 0.025);
    g.gain.exponentialRampToValueAtTime(0.001, s + 0.32);
    o.start(s); o.stop(s + 0.33);
  });
}
