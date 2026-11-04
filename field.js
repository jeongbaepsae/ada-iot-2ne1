// 현장 측정 콘솔.
//
// 기기 내장 IMU(DeviceMotion)로 한 시행을 기록하고 CSV 로 저장한다.
// 저장 포맷은 이 저장소의 분석 파이프라인과 PADS 양쪽에 그대로 들어가도록 맞췄다.
//   elapsed_ms, acc_x_g..z (중력 포함), lin_x_g..z (중력 제외), gyro_x_dps..z
// 중력을 **포함한** 열을 같이 남기는 이유: 중력 방향이 연직이라는 절대 기준을 주기
// 때문이다. PADS 는 중력을 빼고 배포해서 손목 자세를 복원할 기준이 없다.

const $ = s => document.querySelector(s);
const G = 9.80665;

const st = {
  connected: false, recording: false, t0: 0, rows: [],
  lastMs: null, gaps: 0, peak: 0, zero: null,
};

// ---------- 작은 FFT (실시간 대역 지표용) ----------
function fft(re, im) {
  const n = re.length;
  for (let i = 1, j = 0; i < n; i++) {
    let bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) { [re[i], re[j]] = [re[j], re[i]]; [im[i], im[j]] = [im[j], im[i]]; }
  }
  for (let len = 2; len <= n; len <<= 1) {
    const ang = -2 * Math.PI / len;
    for (let i = 0; i < n; i += len) {
      for (let k = 0; k < len / 2; k++) {
        const w = ang * k, c = Math.cos(w), s = Math.sin(w);
        const ur = re[i + k], ui = im[i + k];
        const vr = re[i + k + len / 2] * c - im[i + k + len / 2] * s;
        const vi = re[i + k + len / 2] * s + im[i + k + len / 2] * c;
        re[i + k] = ur + vr; im[i + k] = ui + vi;
        re[i + k + len / 2] = ur - vr; im[i + k + len / 2] = ui - vi;
      }
    }
  }
}

/** 3축 신호의 대역 지표: 축별 스펙트럼 합에서 3-12 Hz RMS 와 지배 주파수. */
function bandStats(xyz, fs, lo = 3, hi = 12) {
  let n = 1; while (n * 2 <= xyz.length) n *= 2;
  if (n < 64) return null;
  const start = xyz.length - n;
  const pow = new Float64Array(n / 2 + 1);
  for (let ax = 0; ax < 3; ax++) {
    const re = new Float64Array(n), im = new Float64Array(n);
    let mean = 0;
    for (let i = 0; i < n; i++) mean += xyz[start + i][ax];
    mean /= n;
    for (let i = 0; i < n; i++) {
      const w = 0.5 - 0.5 * Math.cos(2 * Math.PI * i / (n - 1));   // hann
      re[i] = (xyz[start + i][ax] - mean) * w;
    }
    fft(re, im);
    for (let k = 0; k <= n / 2; k++) pow[k] += (re[k] * re[k] + im[k] * im[k]) / (n * n);
  }
  const df = fs / n;
  let sum = 0, best = 0, bestK = 0;
  for (let k = 1; k <= n / 2; k++) {
    const f = k * df;
    if (f < lo || f > hi) continue;
    sum += pow[k] * 2;
    if (pow[k] > best) { best = pow[k]; bestK = k; }
  }
  return { rms: Math.sqrt(sum) * Math.SQRT2, peakHz: bestK * df };
}

// ---------- 센서 ----------
function onMotion(e) {
  const now = performance.now();
  const ag = e.accelerationIncludingGravity, al = e.acceleration, rr = e.rotationRate;
  if (!ag || ag.x == null) return;
  if (st.lastMs != null && now - st.lastMs > 40) st.gaps++;
  st.lastMs = now;

  const acc = [ag.x / G, ag.y / G, ag.z / G];
  const lin = al && al.x != null ? [al.x / G, al.y / G, al.z / G] : [0, 0, 0];
  const gyr = rr ? [rr.alpha || 0, rr.beta || 0, rr.gamma || 0] : [0, 0, 0];
  const mag = Math.hypot(...lin);
  if (mag > st.peak) st.peak = mag;

  if (st.recording) st.rows.push([Math.round(now - st.t0), ...acc, ...lin, ...gyr]);
  st.live.push(st.zero ? lin.map((v, i) => v - st.zero[i]) : lin);
  if (st.live.length > 1024) st.live.shift();
}

async function connect() {
  try {
    if (typeof DeviceMotionEvent === 'undefined')
      throw new Error('이 브라우저에 DeviceMotion 이 없습니다.');
    if (typeof DeviceMotionEvent.requestPermission === 'function') {
      const r = await DeviceMotionEvent.requestPermission();
      if (r !== 'granted') throw new Error('센서 권한이 거부되었습니다.');
    }
    addEventListener('devicemotion', onMotion);
    // 2초 안에 값이 안 들어오면 차단된 환경으로 본다
    const before = st.live.length;
    await new Promise(r => setTimeout(r, 1200));
    if (st.live.length === before)
      throw new Error('센서 값이 들어오지 않습니다. HTTPS 환경인지, 아티팩트가 아닌 배포 페이지인지 확인하세요.');
    st.connected = true;
    setStatus('센서 연결됨', 'ok');
    $('#fRec').disabled = false; $('#fZero').disabled = false;
  } catch (err) {
    setStatus(err.message, 'bad');
  }
}

function setStatus(text, kind) {
  const el = $('#fStatus');
  el.textContent = text;
  el.dataset.kind = kind || '';
}

// ---------- 기록 ----------
function zeroRef() {
  const n = Math.min(st.live.length, 50);
  if (!n) return;
  const s = [0, 0, 0];
  for (let i = st.live.length - n; i < st.live.length; i++)
    for (let k = 0; k < 3; k++) s[k] += st.live[i][k];
  st.zero = s.map(v => v / n);
  setStatus('기준점 초기화 완료', 'ok');
}

function start() {
  if (!$('#fPid').value.trim()) { setStatus('참가자 ID 를 입력하세요 (익명 코드).', 'bad'); return; }
  st.recording = true; st.rows = []; st.gaps = 0; st.peak = 0; st.t0 = performance.now();
  zeroRef();
  $('#fRec').disabled = true; $('#fStop').disabled = false; $('#fSave').disabled = true;
  setStatus('측정 중', 'rec');
}
function stop() {
  st.recording = false;
  $('#fRec').disabled = false; $('#fStop').disabled = true;
  $('#fSave').disabled = !st.rows.length;
  setStatus(`측정 완료 · ${st.rows.length} 샘플`, 'ok');
}

const HEADER = ['elapsed_ms', 'acc_x_g', 'acc_y_g', 'acc_z_g',
  'lin_x_g', 'lin_y_g', 'lin_z_g', 'gyro_x_dps', 'gyro_y_dps', 'gyro_z_dps'];

function saveCsv() {
  const meta = [
    ['participant_id', $('#fPid').value], ['session_id', $('#fSid').value],
    ['task', $('#fTask').value], ['wrist', $('#fWrist').value],
    ['recorded_at', new Date().toISOString()],
    ['note', 'acc_* 는 중력 포함, lin_* 는 중력 제외'],
  ];
  const text = meta.map(m => `# ${m[0]}=${m[1]}`).join('\n') + '\n'
    + HEADER.join(',') + '\n'
    + st.rows.map(r => r.map(v => typeof v === 'number' ? v.toFixed(5) : v).join(',')).join('\n');
  const blob = new Blob([text], { type: 'text/csv' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `${$('#fPid').value}_${$('#fSid').value}_${$('#fTask').value}.csv`;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

// ---------- CSV 불러오기 ----------
function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/).filter(l => !l.startsWith('#'));
  const head = lines[0].split(',').map(h => h.trim());
  const col = n => head.indexOf(n);
  const ti = col('elapsed_ms');
  // 중력 제외 열이 있으면 그걸, 없으면 acc_*_g 를 쓴다
  const ax = col('lin_x_g') >= 0 ? ['lin_x_g', 'lin_y_g', 'lin_z_g'] : ['acc_x_g', 'acc_y_g', 'acc_z_g'];
  const ix = ax.map(col);
  if (ti < 0 || ix.some(i => i < 0)) throw new Error('elapsed_ms / acc_*_g 열이 필요합니다');
  const t = [], xyz = [];
  for (const line of lines.slice(1)) {
    const c = line.split(',');
    const tv = +c[ti], v = ix.map(i => +c[i]);
    if (!Number.isFinite(tv) || v.some(x => !Number.isFinite(x))) continue;
    t.push(tv / 1000); xyz.push(v);
  }
  if (t.length < 64) throw new Error('샘플이 너무 적습니다');
  const fs = (t.length - 1) / (t[t.length - 1] - t[0]);
  const dt = t.slice(1).map((v, i) => v - t[i]);
  const gaps = dt.filter(d => d > 0.04).length;
  const bs = bandStats(xyz, fs) || { rms: NaN, peakHz: NaN };
  return { n: t.length, dur: t[t.length - 1] - t[0], fs, gaps, ...bs, xyz };
}

async function loadFiles(files) {
  const list = $('#fFiles'); list.innerHTML = '';
  for (const f of files) {
    const row = document.createElement('div'); row.className = 'frow';
    try {
      const r = parseCsv(await f.text());
      row.innerHTML = `<b>${f.name}</b>`
        + `<span>${r.n.toLocaleString()} 샘플 · ${r.dur.toFixed(1)} s · ${r.fs.toFixed(1)} Hz</span>`
        + `<span>떨림 3–12 Hz RMS <b>${r.rms.toFixed(4)} g</b> · 피크 ${r.peakHz.toFixed(2)} Hz</span>`
        + `<span class="${r.gaps ? 'bad' : ''}">40 ms 초과 간격 ${r.gaps}</span>`;
      plotCloud('fLoadPlot', r.xyz, '불러온 파일');
    } catch (e) {
      row.innerHTML = `<b>${f.name}</b><span class="bad">읽기 실패 — ${e.message}</span>`;
    }
    list.appendChild(row);
  }
}

// ---------- 그림 ----------
const cssv = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
function plotCloud(id, pts, name) {
  const el = document.getElementById(id); if (!el || !window.Plotly) return;
  const col = cssv('--pd');
  const ax = t => ({ title: { text: t, font: { size: 10, color: cssv('--muted') } },
    gridcolor: cssv('--grid'), zerolinecolor: cssv('--rule'), showbackground: false,
    tickfont: { size: 9, color: cssv('--faint') } });
  Plotly.react(id, [{
    type: 'scatter3d', mode: 'markers',
    x: pts.map(p => p[0]), y: pts.map(p => p[1]), z: pts.map(p => p[2]),
    marker: { size: 2, opacity: .7, color: pts.map((_, i) => i),
      colorscale: [[0, cssv('--grid')], [1, col]], showscale: false },
    hovertemplate: '%{x:.3f}, %{y:.3f}, %{z:.3f} g<extra></extra>', name,
  }], {
    margin: { l: 0, r: 0, t: 0, b: 0 }, paper_bgcolor: 'rgba(0,0,0,0)', showlegend: false,
    scene: { xaxis: ax('X (g)'), yaxis: ax('Y'), zaxis: ax('Z'), aspectmode: 'cube' },
  }, { displaylogo: false, responsive: true, displayModeBar: false });
}

function tick() {
  const el = st.live;
  const dur = st.recording ? (performance.now() - st.t0) / 1000 : 0;
  const fs = st.rows.length > 1 && dur > 0 ? (st.rows.length - 1) / dur : 0;
  $('#mDur').textContent = dur.toFixed(1) + ' s';
  $('#mN').textContent = st.rows.length.toLocaleString();
  $('#mHz').textContent = fs.toFixed(1) + ' Hz';
  $('#mGap').textContent = st.gaps;
  $('#mPeak').textContent = st.peak.toFixed(3) + ' g';
  if (el.length > 128 && fs > 10) {
    const b = bandStats(el, fs);
    if (b) {
      $('#mBand').textContent = b.rms.toFixed(4) + ' g';
      $('#mF').textContent = b.peakHz.toFixed(2) + ' Hz';
    }
  }
  if (el.length > 8) plotCloud('fLivePlot', el.slice(-600), '실시간');
}

export function initField() {
  st.live = [];
  $('#fSid').value = 'S-' + new Date().toISOString().replace(/[-:]/g, '').slice(0, 15);
  $('#fConnect').onclick = connect;
  $('#fZero').onclick = zeroRef;
  $('#fRec').onclick = start;
  $('#fStop').onclick = stop;
  $('#fSave').onclick = saveCsv;
  $('#fInput').onchange = e => loadFiles(e.target.files);
  const dz = $('#fDrop');
  dz.ondragover = e => { e.preventDefault(); dz.classList.add('over'); };
  dz.ondragleave = () => dz.classList.remove('over');
  dz.ondrop = e => { e.preventDefault(); dz.classList.remove('over'); loadFiles(e.dataTransfer.files); };
  setInterval(tick, 200);
  if (typeof DeviceMotionEvent === 'undefined') setStatus('이 환경에는 DeviceMotion 이 없습니다.', 'bad');
}
