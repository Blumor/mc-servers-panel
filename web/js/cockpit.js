"use strict";
/* Tableau de bord d'un serveur : rendu, console, flux temps réel, actions, clavier. */
/* ============================================================ RENDER ========= */
const STATE_LABEL = {
  stopped:['Arrêté','st-stopped'], starting:['Démarrage…','st-starting'], running:['En ligne','st-running'],
  stopping:['Arrêt…','st-stopping'], resetting:['Reset…','st-resetting'], installing:['Installation…','st-installing'],
  error:['Erreur','st-error'],
};

function dotClass(state){
  return state==='running' ? 'on' : state==='error' ? 'off' : state==='stopped' ? '' : 'warn';
}
let tabsSig = '';
function renderTabs(){
  // Appelé à chaque tick (1/s) : on ne reconstruit que si un onglet a changé.
  const list = viewServers();
  const sig = S.view + '|' + S.current + '|' + list.map(s => s.id + ':' + s.name + ':' + s.state).join(',');
  if (sig === tabsSig) return;
  tabsSig = sig;
  const box = $('tabs'); box.innerHTML = '';
  list.forEach((s, i) => {
    const t = el('button', 'tab' + (s.id===S.current?' on':''));
    const d = el('span','dot ' + dotClass(s.state));
    t.append(d, el('span','',s.name));
    if (i < 9){
      const num = el('span','', String(i+1));
      num.style.cssText = 'opacity:.4;font-family:var(--mono);font-size:10px';
      t.append(num);
    }
    t.onclick = () => selectServer(s.id);
    box.appendChild(t);
  });
  const add = el('button','tab','＋'); add.style.cssText='width:42px;justify-content:center;padding:0';
  add.onclick = () => openCreate(); box.appendChild(add);
}

/* Un plantage de rendu ne doit jamais figer le panel en pleine run. */
function render(){
  try { renderInner(); }
  catch(err){ console.error('render', err); $('brandsub').textContent = 'erreur d’affichage'; }
}
function renderInner(){
  renderNav();
  const v = S.view;
  const sections = {home: 'home', manage: 'manage', survival: 'survlist', server: 'srvpage'};
  Object.entries(sections).forEach(([view, id]) => $(id).classList.toggle('hidden', v !== view));
  $('btnNew').classList.toggle('hidden', v !== 'speedrun');
  $('btnSettings').classList.toggle('hidden', v !== 'speedrun');
  if (v !== 'speedrun'){ $('empty').classList.add('hidden'); if (v !== 'server') $('dash').classList.add('hidden'); }
  if (v === 'home') return renderHome();
  if (v === 'manage') return renderManage();
  if (v === 'survival') return renderSurvivalList();
  if (v === 'server') return renderServerPage();
  const list = viewServers();
  const has = list.length > 0;
  $('empty').classList.toggle('hidden', has);
  $('dash').classList.toggle('hidden', !has);
  if (!has) return renderEmpty();
  if (!list.some(x => x.id === S.current)){ S.current = list[0].id; loadLogs(S.current); }
  renderTabs();
  renderCockpit(cur());
}
function renderCockpit(s){
  if (!s) return;
  const speedrun = kindOf(s) === 'speedrun';

  const [lab, cls] = STATE_LABEL[s.state] || STATE_LABEL.stopped;
  const pill = $('statePill'); pill.className = 'state-pill ' + cls;
  pill.innerHTML = ''; pill.append(el('span','dot ' + dotClass(s.state)), el('span','',lab));

  setChip('chipAddr', '📋', s.address);
  setChip('chipVer', '📦', s.version);
  setChip('chipResets', '🔁', String(s.resets), 'resets');
  setChip('chipBackup', '💾', fmtAgo(s.last_backup));
  $('chipResets').classList.toggle('hidden', !speedrun);
  $('chipBackup').classList.toggle('hidden', speedrun);
  $('actReset').classList.toggle('hidden', !speedrun);
  $('actBackup').classList.toggle('hidden', speedrun);
  $('turboRow').classList.toggle('hidden', !speedrun);
  $('timerLab').textContent = speedrun ? 'Temps de run' : 'En ligne depuis';
  $('mResetK').textContent = speedrun ? 'Dernier reset' : 'Dernière sauvegarde';
  const st = s.settings || {}, crack = st['online-mode'] === 'false';
  const flags = [st.hardcore === 'true' ? '💀 Hardcore' : '', crack ? '🔓 Comptes crack' : ''].filter(Boolean);
  const chipFlags = $('chipFlags');
  chipFlags.textContent = flags.join(' · ');
  chipFlags.title = crack ? 'Comptes crack acceptés : les pseudos ne sont pas vérifiés' : '';
  chipFlags.classList.toggle('hidden', !flags.length);

  const busy = ['starting','stopping','resetting','installing'].includes(s.state);
  const up = s.state === 'running';
  $('actStart').disabled = up || busy;
  $('actStop').disabled  = (!up && s.state!=='error') || busy;
  $('actReset').disabled = busy;
  $('actBackup').disabled = busy;
  $('resetSub').textContent = s.turbo ? (s.standby_ready ? 'instantané ⚡' : 'préchauffage…') : 'monde neuf';

  $('swTurbo').setAttribute('aria-checked', String(!!s.turbo));
  const warm = $('warmChip'); warm.className = 'warm';
  if (!s.turbo) { warm.textContent = 'désactivé'; }
  else if (s.standby_ready) { warm.className='warm ready'; warm.innerHTML='⚡ Remplaçant prêt'; }
  else if (up) { warm.className='warm booting'; warm.innerHTML='<span class="spinner"></span> Préchauffage'; }
  else { warm.textContent = 'en attente'; }
  $('turboHint').textContent = s.turbo
    ? 'Un second monde tourne en fond. Après un reset, reconnecte-toi immédiatement.'
    : 'Garde un second monde déjà chargé. Reset ≈ 1 seconde.';

  const live = s.live || {};
  $('timer').textContent = fmtDur(s.run_seconds);
  $('timer').classList.toggle('live', up);
  $('mPlayers').textContent = live.player_count || 0;
  $('mReset').textContent = !speedrun ? fmtAgo(s.last_backup) : s.last_reset_ms == null ? '—'
    : (s.last_reset_ms < 1500 ? s.last_reset_ms+'ms' : (s.last_reset_ms/1000).toFixed(1)+'s');
  $('mReset').classList.toggle('small', !speedrun);
  $('mBoot').textContent = live.boot_seconds ? live.boot_seconds.toFixed(1)+'s' : (busy ? (live.spawn_progress||0)+'%' : '—');
  $('mRam').textContent = (s.ram_mb/1024).toFixed(1)+' Go' + (s.turbo ? ' ×2' : '');

  // Reconstruit seulement si la liste change : sinon les avatars clignotent à chaque tick.
  const names = live.players || [];
  const psig = s.id + (up ? '+' : '-') + names.join(',');
  if (psig !== S.playersSig){
    S.playersSig = psig;
    const pbox = $('players'); pbox.innerHTML = '';
    if (!names.length) pbox.append(el('span','muted', up?'Personne connecté':'Serveur hors ligne'));
    else names.forEach(p => {
      const c = el('span','pl'); const img = el('img'); img.src = 'https://minotar.net/avatar/'+encodeURIComponent(p)+'/24';
      img.onerror = () => { img.replaceWith(el('span','','👤')); };
      c.append(img, el('span','',p)); pbox.append(c);
    });
  }

  if (s.state === 'error' && live.error) $('brandsub').textContent = live.error.slice(0,60);
  else $('brandsub').textContent = up ? 'serveur en ligne' : 'prêt';
}

function renderSystem(){
  const sys = S.system || {};
  const jv = sys.java_best;
  setChip('chipJava', '☕', jv ? 'Java '+jv : 'auto');
  setChip('chipIp', '🏠', sys.local_ip || '—');
  if (S.publicIp) setChip('chipPub', '🌐', S.publicIp);
  const ram = Math.max(2048, Math.min(16384, (sys.ram_total_mb||8192)));
  $('fRam').max = ram; $('sRam').max = ram;
  $('fRamHint').textContent = 'RAM détectée : ' + ((sys.ram_total_mb||0)/1024).toFixed(1) + ' Go — conseillé ' +
    ((sys.ram_suggested_mb||4096)/1024).toFixed(1) + ' Go';
}

/* ============================================================ CONSOLE ======== */
const consoleBox = $('console');
let pending = [], rafQueued = false;
function pushLine(item){
  pending.push(item);
  if (!rafQueued){ rafQueued = true; requestAnimationFrame(drainLines); }
}
function drainLines(){
  rafQueued = false;
  if (!pending.length) return;
  const frag = document.createDocumentFragment();
  for (const it of pending){
    const row = el('div','ln '+(it.lvl||'info'));
    const d = new Date((it.t||Date.now()/1000)*1000);
    // Minecraft prefixe deja l'heure: on la retire, la notre est plus fiable.
    const text = String(it.line||'').replace(/^\[\d{2}:\d{2}:\d{2}\]\s*/, '');
    row.append(el('span','tm', d.toTimeString().slice(0,8)), el('span','tx', text));
    frag.appendChild(row);
  }
  pending = [];
  consoleBox.appendChild(frag);
  S.lines = consoleBox.childElementCount;
  while (S.lines > 600){ consoleBox.removeChild(consoleBox.firstChild); S.lines--; }
  if (S.autoscroll) consoleBox.scrollTop = consoleBox.scrollHeight;
}
consoleBox.addEventListener('scroll', ()=>{
  const atEnd = consoleBox.scrollHeight - consoleBox.scrollTop - consoleBox.clientHeight < 40;
  if (S.autoscroll !== atEnd){ S.autoscroll = atEnd; $('btnAuto').style.opacity = atEnd ? 1 : .45; }
});
async function loadLogs(id){
  consoleBox.innerHTML = '';
  try {
    const r = await API.get('/api/servers/'+id+'/logs');
    (r.lines||[]).forEach(pushLine);
  } catch(e){ /* serveur jamais démarré */ }
}

/* ============================================================ SSE =========== */
let es = null, reconnectTimer = null;
function connect(){
  if (es) es.close();
  es = new EventSource('/api/events');
  es.addEventListener('open', ()=> setConn(true));
  es.addEventListener('hello', (e)=>{ const d = JSON.parse(e.data); S.servers = d.servers; S.system = d.system; renderSystem(); render(); });
  es.addEventListener('tick', (e)=>{ const d = JSON.parse(e.data); S.servers = d.servers; S.lastTickAt = Date.now(); render(); });
  es.addEventListener('server', (e)=>{
    const s = JSON.parse(e.data); const i = S.servers.findIndex(x=>x.id===s.id);
    if (i<0) S.servers.push(s); else S.servers[i] = s; render();
  });
  es.addEventListener('servers', (e)=>{ S.servers = JSON.parse(e.data); render(); });
  es.addEventListener('log', (e)=>{ const d = JSON.parse(e.data); if (!S.current || d.server===S.current) pushLine(d); });
  es.addEventListener('job', (e)=> onJob(JSON.parse(e.data)));
  es.addEventListener('error', ()=>{
    setConn(false);
    if (!reconnectTimer) reconnectTimer = setTimeout(()=>{ reconnectTimer=null; connect(); }, 1600);
  });
}
function setConn(on){
  S.connected = on;
  $('dotConn').className = 'dot ' + (on?'on':'off');
  $('chipConn').lastElementChild.textContent = on ? 'Connecté' : 'Reconnexion…';
}

/* ============================================================ JOBS ========== */
const jobBar = $('jobbar');
let jobHideTimer = null;
function onJob(job){
  if (job.status === 'running'){
    jobBar.style.width = Math.max(6, (job.progress||0)*100) + '%';
    if (job.message) $('brandsub').textContent = job.message;
    clearTimeout(jobHideTimer);
  } else {
    jobBar.style.width = '100%';
    clearTimeout(jobHideTimer);
    jobHideTimer = setTimeout(()=>{ jobBar.style.width='0%'; }, 450);
    if (job.kind === 'backup' || job.kind === 'restore'){
      S.usage[job.target] = null; manageSig = '';
      if ($('scrimSet').classList.contains('on') && cur() && cur().id === job.target) loadBackups(job.target);
    }
    if (job.status === 'error') toast(job.error || 'Échec de l’opération', 'err', 7000);
    else if (job.kind === 'reset'){
      const ms = job.result && job.result.ms;
      flash(ms != null && ms < 1500 ? 'NEW WORLD' : 'RESET');
      toast('Monde neuf ' + (ms!=null ? (ms<1500 ? 'en '+ms+' ms ⚡' : 'en '+(ms/1000).toFixed(1)+' s') : 'prêt') +
            (job.result && job.result.instant ? ' — reconnecte-toi !' : ''), 'ok', 5000);
    }
    else if (job.kind === 'backup') toast((job.result && job.result.name ? 'Sauvegarde faite : ' + job.result.name : 'Sauvegarde faite'), 'ok', 4000);
    else if (job.kind === 'restore') toast('Monde restauré', 'ok', 5000);
    else if (job.kind === 'start') toast('Serveur démarré', 'ok');
    else if (job.kind === 'stop') toast('Serveur arrêté', 'ok', 2200);
  }
}

/* ============================================================ ACTIONS ======= */
async function act(kind, btn){
  const s = cur(); if (!s) return;
  if (kind === 'reset'){
    // Anti double-clic : en Turbo la bascule prend 1 ms, un 2e reset effacerait le monde tout neuf.
    if (Date.now() - S.lastResetAt < 1200) return;
    S.lastResetAt = Date.now();
  }
  if (btn) fireBtn(btn);
  try { await API.post('/api/servers/'+s.id+'/'+kind, {}); }
  catch(e){ toast(e.message, 'err', 6000); }
}
function selectServer(id){
  S.current = id; render(); loadLogs(id);
  try { localStorage.setItem('mcpanel.current', id); } catch(e){}
}

$('actStart').onclick = (e)=> act('start', e.currentTarget);
$('actStop').onclick  = (e)=> act('stop',  e.currentTarget);
$('actReset').onclick = (e)=> act('reset', e.currentTarget);
$('actBackup').onclick = (e)=> act('backups', e.currentTarget);
$('swTurbo').onclick = async ()=>{
  const s = cur(); if (!s) return;
  const next = !s.turbo;
  $('swTurbo').setAttribute('aria-checked', String(next));
  try {
    await API.post('/api/servers/'+s.id+'/turbo', {enabled: next});
    toast(next ? 'Turbo activé — le remplaçant démarre' : 'Turbo désactivé', 'ok');
  } catch(e){ toast(e.message,'err'); }
};
$('btnAuto').onclick = ()=>{ S.autoscroll = !S.autoscroll; $('btnAuto').style.opacity = S.autoscroll?1:.45;
  if (S.autoscroll) consoleBox.scrollTop = consoleBox.scrollHeight; };
$('btnClear').onclick = ()=>{ consoleBox.innerHTML=''; S.lines=0; };
$('chipIp').onclick = ()=> copy(S.system.local_ip || 'localhost', 'IP locale');
$('chipPub').onclick = ()=>{ const s=cur(); if(S.publicIp) copy(S.publicIp+(s && s.port!==25565 ? ':'+s.port : ''), 'Adresse pour ton pote'); };
$('chipAddr').onclick = ()=>{ const s=cur(); if(s) copy(s.address, 'Adresse serveur'); };

/* commandes */
async function sendCmd(cmd){
  const s = cur(); if (!s || !cmd.trim()) return;
  try {
    await API.post('/api/servers/'+s.id+'/command', {command: cmd});
    S.history.push(cmd); S.hIdx = S.history.length;
  } catch(e){ toast(e.message, 'err'); }
}
$('btnSend').onclick = ()=>{ sendCmd($('cmdInput').value); $('cmdInput').value=''; };
$('cmdInput').addEventListener('keydown', (e)=>{
  if (e.key === 'Enter'){ sendCmd(e.target.value); e.target.value=''; }
  else if (e.key === 'ArrowUp'){ if (S.hIdx>0){ S.hIdx--; e.target.value = S.history[S.hIdx]; e.preventDefault(); } }
  else if (e.key === 'ArrowDown'){ if (S.hIdx < S.history.length-1){ S.hIdx++; e.target.value = S.history[S.hIdx]; } else { S.hIdx=S.history.length; e.target.value=''; } }
  else if (e.key === 'Escape'){ e.target.blur(); }
});
document.querySelectorAll('.qbtn').forEach(b => b.onclick = () => {
  if (b.dataset.cmd) return sendCmd(b.dataset.cmd);
  const who = prompt(b.dataset.op === 'op' ? 'Pseudo à passer OP :' : 'Pseudo à whitelister :');
  if (who) sendCmd((b.dataset.op === 'op' ? 'op ' : 'whitelist add ') + who.trim());
});

/* ============================================================ KEYBOARD ====== */
document.addEventListener('keydown', (e) => {
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
  if (e.key === 'Escape') document.querySelectorAll('.scrim.on').forEach(s=>s.classList.remove('on'));
  // e.repeat : touche R maintenue = rafale de resets.
  if (typing || e.ctrlKey || e.metaKey || e.altKey || e.repeat) return;
  if (!viewKind() || document.querySelector('.scrim.on')) return;  // raccourcis : seulement dans un panel
  if (S.view === 'server' && S.pageCat !== 'dashboard') return;  // page serveur : seulement sur le tableau de bord
  const k = e.key.toLowerCase();
  const speedrun = viewKind() === 'speedrun';
  if (k === 'r'){ e.preventDefault(); if(speedrun && !$('actReset').disabled) act('reset', $('actReset')); }
  else if (k === 'b'){ e.preventDefault(); if(!speedrun && !$('actBackup').disabled) act('backups', $('actBackup')); }
  else if (k === 's'){ e.preventDefault(); if(!$('actStart').disabled) act('start', $('actStart')); }
  else if (k === 'x'){ e.preventDefault(); if(!$('actStop').disabled) act('stop', $('actStop')); }
  else if (k === 'c'){ e.preventDefault(); $('cmdInput').focus(); }
  else if (k === 'n'){ e.preventDefault(); openCreate(); }
  else if (k === '?'){ toast((speedrun ? 'R reset' : 'B sauvegarde') + ' · S start · X stop · C console · N nouveau · 1-9 serveur', '', 6000); }
  else if (/^[1-9]$/.test(k)){ const s = viewServers()[+k-1]; if (s) selectServer(s.id); }
});

