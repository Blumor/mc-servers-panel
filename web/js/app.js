"use strict";
/* ============================================================ BOOT ========== */
async function refresh(){
  try {
    const d = await API.get('/api/state');
    S.servers = d.servers; S.system = d.system;
    if (!S.current && S.servers.length){
      let saved = null; try { saved = localStorage.getItem('mcpanel.current'); } catch(e){}
      S.current = (saved && S.servers.some(s=>s.id===saved)) ? saved : S.servers[0].id;
    }
    renderSystem(); render();
    if (S.current) loadLogs(S.current);
  } catch(e){ toast('Panel injoignable : '+e.message, 'err', 8000); }
}
/* horloge locale du timer: évite d'attendre le tick serveur */
setInterval(() => {
  const s = cur(); if (!s || s.state !== 'running' || s.run_seconds == null) return;
  const drift = (Date.now() - S.lastTickAt)/1000;
  $('timer').textContent = fmtDur(s.run_seconds + (drift > 0 && drift < 5 ? drift : 0));
}, 250);

async function loadPublicIp(){
  try { const r = await API.get('/api/ip'); S.publicIp = r.public; }
  catch(e){ S.publicIp = null; }
  setChip('chipPub', '🌐', S.publicIp || 'hors ligne');
}

window.addEventListener('hashchange', route);
route(); refresh(); connect(); loadPublicIp();
