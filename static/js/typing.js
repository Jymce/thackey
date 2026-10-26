/* ThacKey typing engine — vanilla JS, no framework.
 * Renders target text, captures per-keystroke telemetry, computes live stats,
 * POSTs the session to the Django API (session auth + CSRF), then shows the
 * result+analysis modal: instant session hot spots first, profile weaknesses
 * and the suggested drill once the save resolves. */
(function () {
  const root = document.getElementById('typing-root');
  if (!root) return;

  const area = document.getElementById('typing-area');
  const isAuthed = root.dataset.auth === 'true';
  const csrf = document.querySelector('meta[name=csrf-token]')?.content || '';

  const ui = {
    wpm: document.getElementById('live-wpm'),
    acc: document.getElementById('live-acc'),
    time: document.getElementById('live-time'),
    modal: document.getElementById('result-modal'),
    note: document.getElementById('modal-note'),
    resWpm: document.getElementById('res-wpm'),
    resAcc: document.getElementById('res-acc'),
    resErr: document.getElementById('res-err'),
    resTime: document.getElementById('res-time'),
    hotWrap: document.getElementById('modal-hotspots-wrap'),
    hotspots: document.getElementById('modal-hotspots'),
    weakWrap: document.getElementById('modal-weak-wrap'),
    weaknesses: document.getElementById('modal-weaknesses'),
    sugWrap: document.getElementById('modal-suggest-wrap'),
    rationale: document.getElementById('modal-rationale'),
    practice: document.getElementById('modal-practice'),
    newTest: document.getElementById('modal-newtest'),
    close: document.getElementById('modal-close'),
    resView: document.getElementById('res-view'),
    resLogin: document.getElementById('res-login'),
    adaptivePill: document.getElementById('adaptive-pill'),
    kb: document.getElementById('kb'),
    soundBtn: document.getElementById('sound-toggle'),
  };

  let mode = 'words';          // 'words' | 'adaptive'
  let source = 'standard';     // 'standard' | 'adaptive'
  let adaptiveTestId = null;
  let text = '';
  let spans = [];
  let pos = 0;
  let keystrokes = [];
  let errors = 0;
  let startedAt = null;        // ms timestamp
  let finished = false;
  let timerId = null;
  let suggestion = null;       // server-suggested drill, post-save

  /* ---------- typing sound (WebAudio synth "thock") ---------- */

  let audioCtx = null;
  let noiseBuf = null;
  let soundOn = localStorage.getItem('thackey-sound') !== 'off';

  function setSound(on) {
    soundOn = on;
    localStorage.setItem('thackey-sound', on ? 'on' : 'off');
    if (ui.soundBtn) ui.soundBtn.textContent = `sound ${on ? 'on' : 'off'}`;
  }

  function thock(key) {
    if (!soundOn) return;
    try {
      if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const len = Math.floor(audioCtx.sampleRate * 0.03);
        noiseBuf = audioCtx.createBuffer(1, len, audioCtx.sampleRate);
        const d = noiseBuf.getChannelData(0);
        for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / len);
      }
      if (audioCtx.state === 'suspended') audioCtx.resume();
      const t = audioCtx.currentTime;
      const base = key === ' ' ? 85 : key === 'Backspace' ? 110 : 150;
      const f = base * (0.9 + Math.random() * 0.3);

      // low thump: fast pitch drop
      const osc = audioCtx.createOscillator();
      const og = audioCtx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(f * 2, t);
      osc.frequency.exponentialRampToValueAtTime(f, t + 0.04);
      og.gain.setValueAtTime(0.45, t);
      og.gain.exponentialRampToValueAtTime(0.001, t + 0.1);
      osc.connect(og).connect(audioCtx.destination);
      osc.start(t); osc.stop(t + 0.11);

      // click transient: filtered noise burst
      const src = audioCtx.createBufferSource();
      src.buffer = noiseBuf;
      const bp = audioCtx.createBiquadFilter();
      bp.type = 'bandpass';
      bp.frequency.value = 1500 + Math.random() * 900;
      bp.Q.value = 0.9;
      const ng = audioCtx.createGain();
      ng.gain.setValueAtTime(0.3, t);
      ng.gain.exponentialRampToValueAtTime(0.001, t + 0.03);
      src.connect(bp).connect(ng).connect(audioCtx.destination);
      src.start(t);
    } catch (e) { /* audio unavailable — type in silence */ }
  }

  /* ---------- on-screen keyboard ---------- */

  const KB_ROWS = [
    '1234567890-='.split(''),
    'qwertyuiop[]\\'.split(''),
    "asdfghjkl;'".split(''),
    'zxcvbnm,./'.split(''),
  ];
  let keyEls = {};

  function addKey(row, key, label, extra) {
    const el = document.createElement('div');
    el.className = `kb-key ${extra || ''}`;
    el.dataset.key = key;
    el.textContent = label;
    keyEls[key] = el;
    row.appendChild(el);
  }

  function buildKeyboard() {
    if (!ui.kb) return;
    ui.kb.innerHTML = '';
    keyEls = {};
    for (const keys of KB_ROWS) {
      const r = document.createElement('div');
      r.className = 'kb-row';
      for (const k of keys) addKey(r, k, k);
      ui.kb.appendChild(r);
    }
    addKey(ui.kb.firstChild, 'Backspace', '⌫', 'kb-wide');
    const spaceRow = document.createElement('div');
    spaceRow.className = 'kb-row';
    addKey(spaceRow, ' ', '', 'kb-space');
    ui.kb.appendChild(spaceRow);
  }

  function pressKey(key, err) {
    const el = keyEls[key.length === 1 ? key.toLowerCase() : key];
    if (!el) return;
    el.classList.remove('pressed', 'err');
    void el.offsetWidth;  // restart the transition on rapid repeats
    el.classList.add('pressed');
    if (err) el.classList.add('err');
    setTimeout(() => el.classList.remove('pressed', 'err'), 140);
  }

  function highlightNext() {
    ui.kb?.querySelectorAll('.next').forEach(el => el.classList.remove('next'));
    if (finished || pos >= text.length) return;
    keyEls[text[pos].toLowerCase()]?.classList.add('next');
  }

  /* ---------- text loading ---------- */

  async function loadStandard(count) {
    mode = 'words'; source = 'standard'; adaptiveTestId = null;
    const res = await fetch(`/api/v1/texts/random/?category=words&count=${count}`);
    const data = await res.json();
    begin(data.content || data.body || 'the quick brown fox');
  }

  async function loadAdaptive() {
    let test = JSON.parse(sessionStorage.getItem('adaptiveTest') || 'null');
    if (!test && isAuthed) {
      ui.adaptivePill.textContent = '✦ generating…';
      try {
        const res = await fetch('/api/v1/adaptive/generate/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
          body: '{}',
        });
        if (res.ok) {
          test = await res.json();
          sessionStorage.setItem('adaptiveTest', JSON.stringify(test));
        }
      } catch (e) { /* fall through */ }
    }
    ui.adaptivePill.textContent = '✦ adaptive';
    if (!test) {
      loadStandard(50);  // not logged in / no profile — fall back
      return;
    }
    mode = 'adaptive'; source = 'adaptive'; adaptiveTestId = test.id;
    begin(test.content);
  }

  /* ---------- render ---------- */

  function begin(newText) {
    text = newText.trim();
    pos = 0; errors = 0; keystrokes = []; startedAt = null; finished = false;
    suggestion = null;
    if (timerId) clearInterval(timerId);
    closeModal();
    document.body.classList.remove('focus-mode');
    area.innerHTML = '';
    spans = [];
    for (const ch of text) {
      const s = document.createElement('span');
      s.className = 'char-pending';
      s.textContent = ch;
      area.appendChild(s);
      spans.push(s);
    }
    setCurrent(0);
    highlightNext();
    updateStats();
    area.focus();
  }

  function setCurrent(i) {
    spans.forEach(s => s.classList.remove('char-current'));
    if (i < spans.length) spans[i].classList.add('char-current');
  }

  /* ---------- input ---------- */

  function onKey(e) {
    if (!ui.modal.classList.contains('hidden')) {
      if (e.key === 'Tab') { e.preventDefault(); restart(); }
      return;  // modal open — swallow typing keys
    }
    if (finished) return;
    if (e.key === 'Tab') { e.preventDefault(); restart(); return; }
    if (e.key === 'Escape') { return; }
    if (e.key !== 'Backspace' && e.key.length !== 1) return;
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    e.preventDefault();
    thock(e.key);

    const now = performance.now();
    if (startedAt === null) {
      startedAt = now;
      timerId = setInterval(updateStats, 250);
      document.body.classList.add('focus-mode');
    }
    const latency = keystrokes.length ? now - keystrokes[keystrokes.length - 1].t : now - startedAt;
    const timestamp = now - startedAt;

    if (e.key === 'Backspace') {
      pressKey('Backspace');
      if (pos > 0) {
        pos--;
        keystrokes.push({ seq: keystrokes.length, expected_char: text[pos], typed_char: '', correct: false, latency_ms: latency, timestamp_ms: timestamp, is_backspace: true, t: now });
        spans[pos].className = 'char-pending';
        setCurrent(pos);
        highlightNext();
      }
      return;
    }

    if (pos >= text.length) { pressKey(e.key); return; }
    const expected = text[pos];
    const correct = e.key === expected;
    pressKey(e.key, !correct);
    if (!correct) errors++;

    keystrokes.push({ seq: keystrokes.length, expected_char: expected, typed_char: e.key, correct, latency_ms: latency, timestamp_ms: timestamp, is_backspace: false, t: now });
    spans[pos].className = correct ? 'char-correct' : 'char-incorrect';
    pos++;
    setCurrent(pos);
    highlightNext();
    updateStats();

    if (pos >= text.length) finish();
  }

  /* ---------- stats ---------- */

  function elapsedS() { return startedAt === null ? 0 : (performance.now() - startedAt) / 1000; }

  function computeStats() {
    const s = elapsedS();
    const correct = keystrokes.filter(k => k.correct).length;
    const mins = s / 60 || 0;
    const wpm = mins > 0 ? (correct / 5) / mins : 0;
    const raw = mins > 0 ? (keystrokes.filter(k => !k.is_backspace).length / 5) / mins : 0;
    const typed = keystrokes.filter(k => !k.is_backspace).length;
    const acc = typed ? (correct / typed) * 100 : 100;
    return { s, wpm, raw, acc };
  }

  function updateStats() {
    const { s, wpm, acc } = computeStats();
    ui.wpm.textContent = Math.round(wpm);
    ui.acc.textContent = Math.round(acc);
    ui.time.textContent = `${Math.floor(s)}s`;
  }

  /* ---------- client-side session analysis (instant) ---------- */

  function sessionHotspots() {
    const stats = {};  // char -> {n, err, latSum}
    for (const k of keystrokes) {
      if (k.is_backspace || !k.expected_char) continue;
      const ch = k.expected_char.toLowerCase();
      const st = stats[ch] || (stats[ch] = { n: 0, err: 0, lat: 0 });
      st.n++;
      if (!k.correct) st.err++;
      if (k.latency_ms) st.lat += k.latency_ms;
    }
    const avgs = Object.values(stats).filter(s => s.n > 0 && s.lat > 0).map(s => s.lat / s.n);
    const median = avgs.length ? avgs.sort((a, b) => a - b)[Math.floor(avgs.length / 2)] : 0;

    const spots = [];
    for (const [ch, st] of Object.entries(stats)) {
      if (st.n < 2) continue;
      const errRate = st.err / st.n;
      const avg = st.lat / st.n;
      if (errRate > 0 || (median && avg > median * 1.4)) {
        spots.push({ key: ch, err: errRate, ms: avg });
      }
    }
    spots.sort((a, b) => (b.err - a.err) || (b.ms - a.ms));
    return spots.slice(0, 6);
  }

  function chip(label, title, cls) {
    const el = document.createElement('span');
    el.className = `badge ${cls}`;
    el.textContent = label;
    if (title) el.title = title;
    return el;
  }

  /* ---------- modal ---------- */

  function openModal() {
    ui.modal.classList.remove('hidden');
    ui.modal.classList.add('flex');
  }
  function closeModal() {
    ui.modal.classList.add('hidden');
    ui.modal.classList.remove('flex');
    // reset post-save sections for next run
    ui.weakWrap.classList.add('hidden');
    ui.sugWrap.classList.add('hidden');
    ui.practice.classList.add('hidden');
    ui.resView.classList.add('hidden');
    ui.resLogin.classList.add('hidden');
    ui.hotWrap.classList.add('hidden');
    ui.note.textContent = '';
    suggestion = null;
  }

  async function finish() {
    finished = true;
    document.body.classList.remove('focus-mode');
    highlightNext();
    if (timerId) clearInterval(timerId);
    const { s, wpm, raw, acc } = computeStats();

    ui.resWpm.textContent = Math.round(wpm);
    ui.resAcc.textContent = Math.round(acc);
    ui.resErr.textContent = errors;
    ui.resTime.textContent = Math.round(s);

    // instant: this session's hot spots (no network needed)
    const spots = sessionHotspots();
    if (spots.length) {
      ui.hotspots.innerHTML = '';
      for (const p of spots) {
        const lbl = p.key === ' ' ? '␣' : p.key;
        ui.hotspots.appendChild(
          chip(`${lbl}${p.err > 0 ? ` ${Math.round(p.err * 100)}%` : ''}`,
            `err ${(p.err * 100).toFixed(0)}% · avg ${Math.round(p.ms)}ms`,
            p.err > 0 ? 'badge-destructive' : 'badge-secondary')
        );
      }
      ui.hotWrap.classList.remove('hidden');
    }
    ui.note.textContent = source === 'adaptive' ? 'adaptive session' : '';
    openModal();

    if (!isAuthed) {
      ui.resLogin.classList.remove('hidden');
      return;
    }

    const payload = {
      mode: mode === 'adaptive' ? 'adaptive' : 'words',
      source,
      adaptive_test: adaptiveTestId,
      started_at: new Date(Date.now() - s * 1000).toISOString(),
      finished_at: new Date().toISOString(),
      duration_s: Math.max(s, 0.1),
      wpm: +wpm.toFixed(2), raw_wpm: +raw.toFixed(2), accuracy: +acc.toFixed(2),
      char_count: text.length, error_count: errors,
      keystrokes: keystrokes.map(({ t, ...k }) => k),
    };

    try {
      const res = await fetch('/api/v1/sessions/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify(payload),
      });
      if (!res.ok) { ui.note.textContent = 'could not save session'; return; }
      const saved = await res.json();
      ui.resView.href = `/results/${saved.id}/`;
      ui.resView.classList.remove('hidden');
      ui.note.textContent = 'saved — weakness profile updated';

      const analysis = saved.analysis || {};
      // server-side per-session hotspots (more accurate than the client guess)
      if (analysis.hotspots?.length) {
        ui.hotspots.innerHTML = '';
        for (const p of analysis.hotspots) {
          const lbl = p.key.replace(' ', '␣');
          ui.hotspots.appendChild(
            chip(`${lbl}${p.err > 0 ? ` ${Math.round(p.err * 100)}%` : ''}`,
              `err ${(p.err * 100).toFixed(0)}% · avg ${Math.round(p.ms)}ms`,
              'badge-destructive')
          );
        }
        ui.hotWrap.classList.remove('hidden');
      }
      if (analysis.top_weaknesses?.length) {
        ui.weaknesses.innerHTML = '';
        for (const w of analysis.top_weaknesses) {
          ui.weaknesses.appendChild(
            chip(`${w.key.replace(' ', '␣')} ${w.score.toFixed(2)}`, null, 'badge-outline')
          );
        }
        ui.weakWrap.classList.remove('hidden');
      }
      if (analysis.suggestion?.targets?.length) {
        suggestion = analysis.suggestion;
        ui.rationale.textContent = suggestion.rationale;
        ui.sugWrap.classList.remove('hidden');
        ui.practice.classList.remove('hidden');
      }
    } catch (e) {
      ui.note.textContent = 'offline — session not saved';
    }
  }

  /* ---------- practice-this flow ---------- */

  async function practiceSuggested() {
    if (!suggestion) return;
    ui.practice.disabled = true;
    ui.practice.textContent = '✦ generating…';
    try {
      const res = await fetch('/api/v1/adaptive/generate/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify({
          targets: suggestion.targets,
          word_count: suggestion.word_count,
        }),
      });
      if (!res.ok) throw new Error();
      const test = await res.json();
      sessionStorage.setItem('adaptiveTest', JSON.stringify(test));
      ui.adaptivePill.classList.add('active');
      document.querySelectorAll('.mode-pill[data-count]').forEach(b => b.classList.remove('active'));
      closeModal();
      loadAdaptive();
    } catch (e) {
      ui.practice.textContent = '✦ practice these';
      ui.practice.disabled = false;
    }
  }

  function restart() {
    if (source === 'adaptive') loadAdaptive();
    else loadStandard(currentCount);
  }

  /* ---------- wire up ---------- */

  let currentCount = 50;
  document.querySelectorAll('.mode-pill[data-count]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.mode-pill').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentCount = +btn.dataset.count;
      loadStandard(currentCount);
    });
  });
  ui.adaptivePill?.addEventListener('click', () => {
    document.querySelectorAll('.mode-pill').forEach(b => b.classList.remove('active'));
    ui.adaptivePill.classList.add('active');
    loadAdaptive();
  });
  ui.newTest?.addEventListener('click', restart);
  ui.close?.addEventListener('click', closeModal);
  ui.practice?.addEventListener('click', practiceSuggested);
  ui.modal?.addEventListener('click', e => { if (e.target === ui.modal) closeModal(); });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !ui.modal.classList.contains('hidden')) {
      closeModal();
      return;
    }
    onKey(e);
  });
  area.addEventListener('click', () => area.focus());
  ui.soundBtn?.addEventListener('click', () => setSound(!soundOn));

  setSound(soundOn);
  buildKeyboard();

  // if an adaptive test is waiting from the analytics page, start with it
  if (sessionStorage.getItem('adaptiveTest')) {
    ui.adaptivePill.classList.add('active');
    document.querySelectorAll('.mode-pill[data-count]').forEach(b => b.classList.remove('active'));
    loadAdaptive();
  } else {
    loadStandard(currentCount);
  }
})();
