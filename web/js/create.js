"use strict";
/* ----------------------------------------------------------------- création */
let createForm = null;
async function loadSchema(kind){
  if (S.schema && S.propDefaultsByKind[kind]) return S.schema;
  const r = await API.get('/api/properties?kind=' + encodeURIComponent(kind));
  S.schema = r.schema; S.propDefaultsByKind[kind] = r.defaults || {};
  return S.schema;
}
const CREATE_TEXT = {
  speedrun: {title: 'Nouveau serveur speedrun', name: 'Speedrun', seed: 'Aléatoire à chaque reset', diff: 'hard'},
  survival: {title: 'Nouveau serveur de survie', name: 'Survie', seed: 'Aléatoire', diff: 'normal'},
};
let createKind = 'speedrun';
async function openCreate(kind){
  createKind = kind || viewKind() || 'speedrun';
  const text = CREATE_TEXT[createKind];
  const speedrun = createKind === 'speedrun';
  $('newTitle').textContent = text.title;
  $('fName').value = text.name;
  $('fSeedRandom').textContent = text.seed;
  $('fDiff').value = text.diff;
  $('fTurboRow').classList.toggle('hidden', !speedrun);
  $('fBackupRow').classList.toggle('hidden', speedrun);
  $('fAutoBackup').value = '6';
  openModal('scrimNew');
  $('fPort').value = 25565 + S.servers.length;
  $('fRam').value = Math.min(S.system.ram_suggested_mb || 4096, +$('fRam').max);
  $('fRamLab').textContent = $('fRam').value + ' Mo';
  S.newWhitelist = []; S.newOps = [];
  drawNewPlayers();
  $('fAdvanced').open = false;
  $('fCrack').setAttribute('aria-checked', 'false');  // option sensible : toujours repartir de « non »

  if (!S.versions.length){
    try {
      // Toutes les versions avec un jar serveur (1.2.5 et après), pas seulement les 40 dernières.
      const r = await API.get('/api/versions?kind=release&limit=1000');
      S.versions = r.versions;
      const sel = $('fVersion');
      sel.innerHTML = '<option value="">Dernière ('+r.latest+')</option>';
      r.versions.forEach(v => { const o = el('option','',v.id + '  ·  ' + v.released); o.value = v.id; sel.appendChild(o); });
    } catch(e){ toast('Liste des versions indisponible (hors ligne ?)','err'); }
  }
  try {
    const schema = await loadSchema(createKind);
    // Base = ce que le serveur écrirait tout seul, pour n'envoyer que les écarts.
    const base = {};
    schema.fields.forEach(f => base[f.key] = f.default || '');
    Object.assign(base, S.propDefaultsByKind[createKind]);
    // online-mode a son interrupteur dédié plus haut : pas de doublon dans les options avancées.
    createForm = buildPropsForm($('fPropForm'), schema, base, {exclude: ['online-mode']});
  } catch(e){ toast('Schéma des propriétés indisponible : '+e.message, 'err'); }
}
function drawNewPlayers(){
  $('fWlCount').textContent = S.newWhitelist.length ? S.newWhitelist.length + ' joueur(s)' : '';
  $('fOpCount').textContent = S.newOps.length ? S.newOps.length + ' joueur(s)' : '';
  renderPlayerChips($('fWlList'), S.newWhitelist, n => { S.newWhitelist = S.newWhitelist.filter(x=>x!==n); drawNewPlayers(); });
  renderPlayerChips($('fOpList'), S.newOps, n => { S.newOps = S.newOps.filter(x=>x!==n); drawNewPlayers(); });
}
function addNewPlayer(which){
  const input = $(which === 'ops' ? 'fOpInput' : 'fWlInput');
  const name = input.value.trim();
  if (!name) return;
  if (!/^[A-Za-z0-9_]{3,16}$/.test(name)) return toast('Pseudo invalide : 3 à 16 caractères, lettres, chiffres et _','err');
  const list = which === 'ops' ? S.newOps : S.newWhitelist;
  if (list.some(x => x.toLowerCase() === name.toLowerCase())) return toast(name + ' est déjà dans la liste','err');
  list.push(name); input.value = ''; drawNewPlayers();
}
$('fWlAdd').onclick = () => addNewPlayer('whitelist');
$('fOpAdd').onclick = () => addNewPlayer('ops');
$('fWlInput').addEventListener('keydown', e => { if (e.key==='Enter'){ e.preventDefault(); addNewPlayer('whitelist'); } });
$('fOpInput').addEventListener('keydown', e => { if (e.key==='Enter'){ e.preventDefault(); addNewPlayer('ops'); } });
$('fPropSearch').addEventListener('input', e => createForm && createForm.filter(e.target.value));

$('btnNew').onclick = () => openCreate(); $('btnCreateFirst').onclick = () => openCreate();
$('fRam').oninput = e => $('fRamLab').textContent = e.target.value + ' Mo';
$('fTurbo').onclick = flipSwitch;
$('fCrack').onclick = flipSwitch;

$('btnCreate').onclick = async () => {
  const btn = $('btnCreate');
  if (btn.disabled) return;  // double clic = deux serveurs créés
  const settings = Object.assign(
    {difficulty: $('fDiff').value, 'online-mode': isOn('fCrack') ? 'false' : 'true'},
    createForm ? createForm.read() : {});
  const body = {
    name: $('fName').value || CREATE_TEXT[createKind].name,
    kind: createKind,
    auto_backup_hours: createKind === 'speedrun' ? 0 : +$('fAutoBackup').value,
    version: $('fVersion').value,
    ram_mb: +$('fRam').value,
    port: +$('fPort').value,
    turbo: createKind === 'speedrun' && isOn('fTurbo'),
    seed_mode: $('fSeedMode').value,
    seed: $('fSeed').value.trim(),
    settings,
    whitelist: S.newWhitelist,
    ops: S.newOps,
    start: true,
  };
  btn.disabled = true;
  try {
    const r = await API.post('/api/servers', body);
    closeModal('scrimNew');
    S.current = r.server.id;
    toast('Serveur créé — téléchargement et démarrage…', 'ok');
    (r.notes || []).forEach(n => toast(n, 'err', 8000));
    await refresh(); loadLogs(r.server.id);
  } catch(e){ toast(e.message, 'err', 7000); }
  finally { btn.disabled = false; }
};

