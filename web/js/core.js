"use strict";
/* Socle : API, état, utilitaires d'interface, fenêtres. */
/* ============================================================ API ============ */
const API = {
  async call(path, opts={}) {
    const res = await fetch(path, {headers:{'Content-Type':'application/json'}, ...opts});
    let data = null;
    try { data = await res.json(); } catch(e){ data = {ok:false, error:'Réponse illisible du panel'}; }
    if (!res.ok || data.ok === false) throw new Error(data && data.error ? data.error : 'HTTP '+res.status);
    return data;
  },
  get:  (p)      => API.call(p),
  post: (p,body) => API.call(p, {method:'POST', body: JSON.stringify(body||{})}),
  del:  (p)      => API.call(p, {method:'DELETE'}),
};

/* ============================================================ STATE ========== */
const S = {
  servers: [], current: null, system: {}, versions: [],
  autoscroll: true, connected: false, history: [], hIdx: -1,
  pendingReset: 0, lines: 0, lastTickAt: 0, lastResetAt: 0, playersSig: null,
  schema: null, propDefaults: {}, newWhitelist: [], newOps: [],
};
const $ = (id) => document.getElementById(id);
const el = (tag, cls, txt) => { const n=document.createElement(tag); if(cls)n.className=cls; if(txt!=null)n.textContent=txt; return n; };
const cur = () => S.servers.find(s => s.id === S.current) || null;

/* Panels : chaque vue d'un type de serveur ne montre que les serveurs de ce type. */
S.view = 'home';
S.propDefaultsByKind = {};
const KIND_LABEL = {speedrun: 'Speedrun', survival: 'Survie'};
const VIEW_KIND = {speedrun: 'speedrun', survival: 'survival'};
const viewKind = () => S.view === 'server' ? (cur() ? kindOf(cur()) : null) : (VIEW_KIND[S.view] || null);
const kindOf = (s) => s.kind || 'speedrun';
const viewServers = () => { const k = viewKind(); return k ? S.servers.filter(s => kindOf(s) === k) : S.servers; };
function fmtBytes(n){
  if (n == null) return '…';
  const u = ['o','Ko','Mo','Go','To']; let i = 0;
  while (n >= 1024 && i < u.length-1){ n /= 1024; i++; }
  return (i ? n.toFixed(n < 10 ? 1 : 0) : n) + ' ' + u[i];
}
function fmtAgo(ts){
  if (!ts) return 'jamais';
  const d = Math.max(0, Date.now()/1000 - ts);
  if (d < 60) return "à l'instant";
  if (d < 3600) return 'il y a ' + Math.floor(d/60) + ' min';
  if (d < 86400) return 'il y a ' + Math.floor(d/3600) + ' h';
  return 'il y a ' + Math.floor(d/86400) + ' j';
}

/* ============================================================ UI HELPERS ===== */
function toast(msg, kind='', ms=3400){
  const t = el('div', 'toast '+kind);
  t.append(el('span','',kind==='ok'?'✅':kind==='err'?'⚠️':'ℹ️'), el('span','',msg));
  $('toasts').appendChild(t);
  setTimeout(()=>{ t.classList.add('out'); setTimeout(()=>t.remove(), 320); }, ms);
}
function flash(text){
  const f = $('bigflash'); $('bigflashtxt').textContent = text;
  f.classList.remove('go'); void f.offsetWidth; f.classList.add('go');
}
function fireBtn(btn){ btn.classList.remove('fired'); void btn.offsetWidth; btn.classList.add('fired'); }
function fmtDur(sec){
  if (sec == null) return '--:--';
  sec = Math.max(0, Math.floor(sec));
  const h = Math.floor(sec/3600), m = Math.floor(sec%3600/60), s = sec%60;
  const p = (n)=>String(n).padStart(2,'0');
  return h ? `${h}:${p(m)}:${p(s)}` : `${p(m)}:${p(s)}`;
}
function copy(text, label){
  const done = () => toast((label||'Copié')+' : '+text,'ok',2200);
  const fail = () => toast('Copie impossible','err');
  if (navigator.clipboard && window.isSecureContext)
    navigator.clipboard.writeText(text).then(done).catch(() => legacyCopy(text) ? done() : fail());
  else if (legacyCopy(text)) done();
  else fail();
}
/* En --lan (http://IP-du-PC), la page n'est pas un « contexte sécurisé » : pas de navigator.clipboard. */
function legacyCopy(text){
  const ta = el('textarea'); ta.value = text; ta.setAttribute('readonly', '');
  ta.style.cssText = 'position:fixed;top:0;left:0;opacity:0;pointer-events:none';
  document.body.append(ta); ta.select();
  let ok = false; try { ok = document.execCommand('copy'); } catch(e){}
  ta.remove();
  return ok;
}
/* Chips « icône + valeur » : textContent, jamais innerHTML (version, IP... viennent de l'extérieur). */
function setChip(id, icon, value, suffix){
  const chip = $(id);
  chip.textContent = icon + ' ';
  chip.append(el('b', '', value));
  if (suffix) chip.append(' ' + suffix);
}
const isOn = (id) => $(id).getAttribute('aria-checked') === 'true';
function flipSwitch(e){
  const b = e.currentTarget;
  b.setAttribute('aria-checked', b.getAttribute('aria-checked') === 'true' ? 'false' : 'true');
}
document.addEventListener('pointermove', (e)=>{
  const b = e.target.closest?.('.btn'); if(!b) return;
  const r = b.getBoundingClientRect();
  b.style.setProperty('--mx', (e.clientX-r.left)+'px'); b.style.setProperty('--my', (e.clientY-r.top)+'px');
});

/* ============================================================ MODALS ======== */
function openModal(id){ $(id).classList.add('on'); }
function closeModal(id){ $(id).classList.remove('on'); }
document.querySelectorAll('[data-close]').forEach(b => b.onclick = e => e.target.closest('.scrim').classList.remove('on'));
document.querySelectorAll('.scrim').forEach(sc => sc.addEventListener('click', e => { if (e.target === sc) sc.classList.remove('on'); }));

