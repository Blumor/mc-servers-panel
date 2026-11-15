"use strict";
/* ----------------------------------------------------------------- réglages */
let settingsForm = null;
document.querySelectorAll('.mtab').forEach(tab => tab.onclick = () => {
  document.querySelectorAll('.mtab').forEach(t => t.classList.toggle('on', t === tab));
  document.querySelectorAll('#scrimSet .pane').forEach(p => p.classList.remove('on'));
  $({srv:'paneSrv', props:'paneProps', players:'panePlayers', backups:'paneBackups'}[tab.dataset.pane]).classList.add('on');
});

/* Les onglets server.properties / Joueurs / Sauvegardes servent aussi de pages au panel Survie :
   on les remet dans la fenêtre avant de l'ouvrir. */
function restorePanes(){
  $('paneSrv').parentNode.append($('paneProps'), $('panePlayers'), $('paneBackups'));
}
$('btnSettings').onclick = async () => {
  const s = cur(); if (!s) return toast('Aucun serveur sélectionné','err');
  restorePanes();
  $('setSub').textContent = s.name + ' · ' + s.version + ' · ' + s.id;
  $('sName').value = s.name; $('sPort').value = s.port;
  $('sRam').value = s.ram_mb; $('sRamLab').textContent = s.ram_mb + ' Mo';
  $('sSeedMode').value = s.seed_mode; $('sSeed').value = s.seed || '';
  $('sPropForm').innerHTML = '<div class="muted" style="padding:14px 0">Chargement…</div>';
  $('sPropSearch').value = '';
  openModal('scrimSet');
  try {
    const r = await API.get('/api/servers/'+s.id+'/settings');
    settingsForm = buildPropsForm($('sPropForm'), r.schema, r.settings);
  } catch(e){
    $('sPropForm').innerHTML = '';
    $('sPropForm').append(el('div','note warn','Impossible de lire server.properties : '+e.message));
  }
  loadPlayers(s.id);
  $('sAutoBackup').value = String(s.auto_backup_hours || 0);
  loadBackups(s.id);
};
$('sRam').oninput = e => $('sRamLab').textContent = e.target.value + ' Mo';
$('sPropSearch').addEventListener('input', e => settingsForm && settingsForm.filter(e.target.value));

async function loadPlayers(id){
  try {
    const r = await API.get('/api/servers/'+id+'/players');
    drawPlayers(r);
  } catch(e){ toast('Liste des joueurs indisponible : '+e.message, 'err'); }
}
function drawPlayers(r){
  $('sWlToggle').setAttribute('aria-checked', String(!!r.whitelist_enabled));
  $('sCrackToggle').setAttribute('aria-checked', String(!r.online_mode));
  $('sWlCount').textContent = r.whitelist.length ? r.whitelist.length + ' joueur(s)' : '';
  $('sOpCount').textContent = r.ops.length ? r.ops.length + ' joueur(s)' : '';
  renderPlayerChips($('sWlList'), r.whitelist, n => editPlayer('whitelist','remove',n));
  renderPlayerChips($('sOpList'), r.ops, n => editPlayer('ops','remove',n));
  const note = $('sPlayersNote'); note.innerHTML = '';
  if (r.note) note.append(el('div','note warn', r.note));
  if (!r.online_mode) note.append(el('div','note warn',
    'Comptes crack acceptés : aucun pseudo n’est vérifié. Quelqu’un qui connaît l’adresse peut entrer ' +
    'sous ton pseudo ou celui d’un OP, et la whitelist ne l’arrête pas (elle se base sur le pseudo). ' +
    'Ne donne l’adresse qu’à des gens de confiance.'));
}
async function editPlayer(which, action, player){
  const s = cur(); if (!s) return;
  try {
    const r = await API.post('/api/servers/'+s.id+'/players', {list:which, action, player});
    drawPlayers(r);
    toast((action==='add'?'Ajouté : ':'Retiré : ') + player + (s.state==='running' ? ' (appliqué en direct)' : ''), 'ok', 2600);
  } catch(e){ toast(e.message, 'err', 6000); }
}
function addPlayerLive(which){
  const input = $(which === 'ops' ? 'sOpInput' : 'sWlInput');
  const name = input.value.trim();
  if (!name) return;
  input.value = '';
  editPlayer(which, 'add', name);
}
$('sWlAdd').onclick = () => addPlayerLive('whitelist');
$('sOpAdd').onclick = () => addPlayerLive('ops');
$('sWlInput').addEventListener('keydown', e => { if (e.key==='Enter'){ e.preventDefault(); addPlayerLive('whitelist'); } });
$('sOpInput').addEventListener('keydown', e => { if (e.key==='Enter'){ e.preventDefault(); addPlayerLive('ops'); } });
$('sWlToggle').onclick = async () => {
  const s = cur(); if (!s) return;
  const sw = $('sWlToggle');
  const next = sw.getAttribute('aria-checked') !== 'true';
  sw.setAttribute('aria-checked', String(next));
  try {
    const value = next ? 'true' : 'false';
    await API.post('/api/servers/'+s.id+'/settings', {settings:{'white-list': value}});
    toast('Whitelist ' + (next ? 'activée' : 'désactivée'), 'ok', 2400);
    if (settingsForm) settingsForm.setSaved('white-list', value);
  } catch(e){ sw.setAttribute('aria-checked', String(!next)); toast(e.message,'err'); }
};
$('sCrackToggle').onclick = async () => {
  const s = cur(); if (!s) return;
  const sw = $('sCrackToggle');
  const next = sw.getAttribute('aria-checked') !== 'true';  // true = accepter les comptes crack
  sw.setAttribute('aria-checked', String(next));
  try {
    const value = next ? 'false' : 'true';  // valeur de online-mode
    await API.post('/api/servers/'+s.id+'/settings', {settings:{'online-mode': value}});
    if (settingsForm) settingsForm.setSaved('online-mode', value);
    toast((next ? 'Comptes crack acceptés' : 'Comptes crack refusés') +
          (s.state === 'running' ? ' — pris en compte au prochain reset ou redémarrage' : ''), 'ok', 4500);
    loadPlayers(s.id);
  } catch(e){ sw.setAttribute('aria-checked', String(!next)); toast(e.message,'err'); }
};

$('btnSaveSet').onclick = async () => {
  const s = cur(); if (!s) return;
  const settings = settingsForm ? settingsForm.read() : {};
  try {
    const r = await API.post('/api/servers/'+s.id, {
      name: $('sName').value, port: +$('sPort').value, ram_mb: +$('sRam').value,
      seed_mode: $('sSeedMode').value, auto_backup_hours: +$('sAutoBackup').value, seed: $('sSeed').value.trim(),
      settings,
    });
    // Le backend dit ce qui a été refusé et ce qui n'a pas pu s'appliquer à chaud
    // (avant : S.schema, null tant que la fenêtre de création n'avait jamais été ouverte).
    const rejected = r.rejected || [], later = r.restart_needed || [];
    const n = Object.keys(settings).length - rejected.length;
    closeModal('scrimSet');
    toast(n > 0 ? n + ' réglage(s) enregistré(s)' : 'Réglages enregistrés', 'ok');
    if (rejected.length) toast('Valeur refusée pour : ' + rejected.join(', '), 'err', 8000);
    if (later.length) toast('Pris en compte au prochain reset ou redémarrage : ' + later.join(', '), '', 8000);
    refresh();
  } catch(e){ toast(e.message, 'err'); }
};
$('btnClean').onclick = async () => {
  const s = cur(); if (!s) return;
  const safety = kindOf(s) === 'speedrun' ? '' : ' Une sauvegarde est faite juste avant.';
  if (!confirm('Supprimer mondes, logs et caches de « '+s.name+' » ? La configuration est conservée.' + safety)) return;
  try { await API.post('/api/servers/'+s.id+'/clean'); closeModal('scrimSet'); toast('Nettoyage lancé','ok'); }
  catch(e){ toast(e.message,'err'); }
};
$('btnDelete').onclick = async () => {
  const s = cur(); if (!s) return;
  if (!confirm('Supprimer définitivement le serveur « '+s.name+' » et tous ses fichiers ?')) return;
  try {
    await API.del('/api/servers/'+s.id);
    closeModal('scrimSet'); S.current = null; toast('Serveur supprimé','ok'); refresh();
  } catch(e){ toast(e.message,'err'); }
};


/* ---------------------------------------------------------------- sauvegardes */
async function loadBackups(id){
  const box = $('sBackupList');
  try {
    const [r, usage] = await Promise.all([API.get('/api/servers/'+id+'/backups'), API.get('/api/servers/'+id+'/usage')]);
    $('sUsage').textContent = 'Serveur : ' + fmtBytes(usage.server) + ' · sauvegardes : ' + fmtBytes(usage.backups);
    drawBackups(id, r.backups);
  } catch(e){ box.innerHTML = ''; box.append(el('div','note warn','Sauvegardes indisponibles : '+e.message)); }
}
function drawBackups(id, list){
  const box = $('sBackupList'); box.innerHTML = '';
  $('sBackupCount').textContent = list.length ? list.length + ' sauvegarde(s)' : '';
  if (!list.length){ box.append(el('div','muted','Aucune sauvegarde pour l’instant.')); return; }
  list.forEach(b => {
    const row = el('div','brow');
    const info = el('div','');
    info.append(el('div','', new Date(b.created*1000).toLocaleString('fr-FR') + ' — ' + b.label),
                el('div','meta', fmtBytes(b.size) + (b.auto ? ' · automatique' : '')));
    const acts = el('div','acts');
    const restore = el('button','btn sm','Restaurer');
    restore.onclick = async () => {
      if (!confirm('Remplacer le monde actuel par la sauvegarde du ' + new Date(b.created*1000).toLocaleString('fr-FR') +
                   ' ? Le monde actuel est sauvegardé juste avant.')) return;
      try { await API.post('/api/servers/'+id+'/backups/restore', {name: b.name}); closeModal('scrimSet'); toast('Restauration lancée','ok'); }
      catch(e){ toast(e.message,'err'); }
    };
    const del = el('button','btn sm danger','Supprimer');
    del.onclick = async () => {
      if (!confirm('Supprimer définitivement cette sauvegarde ?')) return;
      try { const r = await API.post('/api/servers/'+id+'/backups/delete', {name: b.name}); drawBackups(id, r.backups); }
      catch(e){ toast(e.message,'err'); }
    };
    acts.append(restore, del);
    row.append(info, acts);
    box.append(row);
  });
}
$('sBackupNow').onclick = async () => {
  const s = cur(); if (!s) return;
  try { await API.post('/api/servers/'+s.id+'/backups', {}); toast('Sauvegarde en cours…','ok'); }
  catch(e){ toast(e.message,'err'); }
};
