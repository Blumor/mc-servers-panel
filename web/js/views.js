"use strict";
/* Vues : accueil, panels par type de serveur, « Mes serveurs ». Navigation par #/adresse. */
const ROUTES = {'': 'home', 'speedrun': 'speedrun', 'survie': 'survival', 'serveurs': 'manage', 'serveur': 'server'};
const PANEL_HASH = {speedrun: '#/speedrun', survival: '#/survie'};
const VIEW_TITLE = {home: 'MC Panel', speedrun: 'Speedrun', survival: 'Survie entre potes', manage: 'Mes serveurs'};

function route(){
  const parts = location.hash.replace(/^#\/?/, '').split('/');
  const view = ROUTES[parts[0]] || 'home';
  if (view === 'server'){
    const id = decodeURIComponent(parts[1] || ''), cat = PAGE_CATS.some(c => c[0] === parts[2]) ? parts[2] : 'dashboard';
    const same = S.view === 'server' && S.pageId === id && S.pageCat === cat;
    if (same) return;
    const newServer = S.pageId !== id || S.view !== 'server';
    S.view = 'server'; S.pageId = id; S.pageCat = cat; pageNavSig = ''; S.playersSig = null;
    if (newServer){ S.current = id; loadLogs(id); }
    placeDash(true);
    render(); loadPageCategory(cat);
    return;
  }
  if (view === S.view) return;
  if (S.view === 'server') placeDash(false);
  S.view = view; tabsSig = ''; S.playersSig = null; manageSig = ''; survSig = '';
  render();
}

function renderNav(){
  document.querySelectorAll('#viewnav a').forEach(a => a.classList.toggle('on', a.dataset.view === S.view));
  $('brandTitle').textContent = S.view === 'home' ? 'MC Panel' : 'MC Panel · ' + VIEW_TITLE[S.view];
}

function renderHome(){
  const label = (n) => n ? n + ' serveur' + (n > 1 ? 's' : '') : 'Aucun serveur';
  const count = (k) => S.servers.filter(s => kindOf(s) === k).length;
  $('countSpeedrun').textContent = label(count('speedrun'));
  $('countSurvival').textContent = label(count('survival'));
  $('countAll').textContent = label(S.servers.length);
  $('brandsub').textContent = 'prêt';
}

const EMPTY_TEXT = {
  speedrun: ['Aucun serveur speedrun.<br>On en crée un ?',
             'Monde hardcore jetable : quand quelqu’un meurt, un clic et vous repartez sur un monde neuf.'],
  survival: ['Aucun serveur de survie.<br>On en crée un ?',
             'Un monde qui dure, sauvegardé automatiquement, pour jouer avec les potes sur la durée.'],
};
function renderEmpty(){
  const [title, text] = EMPTY_TEXT[viewKind()];
  $('emptyTitle').innerHTML = title;  // texte fixe ci-dessus, jamais de donnée externe
  $('emptyText').textContent = text;
  $('brandsub').textContent = 'prêt';
}

/* ------------------------------------------------------------ Mes serveurs */
let manageSig = '';
S.usage = {};  // id -> {server, backups, at}

async function loadUsage(id){
  const known = S.usage[id];
  if (known && (known.loading || Date.now() - known.at < 60000)) return;
  S.usage[id] = Object.assign({}, known, {loading: true});
  try {
    const r = await API.get('/api/servers/' + id + '/usage');
    S.usage[id] = {server: r.server, backups: r.backups, at: Date.now()};
  } catch(e){ S.usage[id] = {at: Date.now()}; }
  manageSig = ''; render();
}

function renderManage(){
  const sig = S.servers.map(s => [s.id, s.name, s.state, s.version, s.port, s.last_backup,
    (S.usage[s.id] || {}).server, (S.usage[s.id] || {}).backups].join(':')).join('|');
  $('brandsub').textContent = S.servers.length + ' serveur(s)';
  if (sig === manageSig) return;
  manageSig = sig;
  const box = $('manageList'); box.innerHTML = '';
  if (!S.servers.length){
    box.append(el('div', 'muted', 'Aucun serveur. Crée-en un depuis le panel Speedrun ou Survie.'));
    return;
  }
  S.servers.forEach(s => {
    loadUsage(s.id);
    const usage = S.usage[s.id] || {};
    const kind = kindOf(s);
    const row = el('div', 'mrow');
    const name = el('div', 'name');
    name.append(el('span', 'dot ' + dotClass(s.state)), el('span', '', s.name), el('em', 'kind ' + kind, KIND_LABEL[kind] || kind));
    const [stateLabel] = STATE_LABEL[s.state] || STATE_LABEL.stopped;
    const meta1 = el('div', 'meta', stateLabel + ' · ' + s.version + ' · port ' + s.port);
    const meta2 = el('div', 'meta', 'Disque ' + fmtBytes(usage.server) + ' · sauvegardes ' + fmtBytes(usage.backups) +
                     ' · dernière ' + fmtAgo(s.last_backup));
    const acts = el('div', 'acts');
    const button = (label, title, fn) => { const b = el('button', 'btn sm ghost', label); b.title = title; b.onclick = fn; acts.append(b); return b; };
    button('Ouvrir', 'Ouvrir ce serveur', () => { S.current = s.id; location.hash = kind === 'survival' ? pageHash(s.id) : PANEL_HASH[kind]; });
    const up = s.state === 'running', busy = ['starting','stopping','resetting','installing'].includes(s.state);
    button(up ? '■' : '▶', up ? 'Arrêter' : 'Démarrer', () => manageAction(s, up ? 'stop' : 'start')).disabled = busy;
    button('💾', 'Sauvegarder maintenant', () => manageAction(s, 'backups')).disabled = busy;
    button('⚙️', 'Réglages, joueurs, sauvegardes', () => {
      S.current = s.id;
      if (kind === 'survival') location.hash = pageHash(s.id, 'general'); else $('btnSettings').onclick();
    });
    row.append(name, meta1, meta2, acts);
    box.append(row);
  });
}

async function manageAction(s, action){
  try {
    await API.post('/api/servers/' + s.id + '/' + action, {});
    if (action === 'backups') S.usage[s.id] = null;
  } catch(e){ toast(e.message, 'err', 6000); }
}

/* ------------------------------------------------------------ Survie : liste */
let survSig = '';
function renderSurvivalList(){
  const list = S.servers.filter(s => kindOf(s) === 'survival');
  const sig = list.map(s => [s.id, s.name, s.state, s.version, (s.live || {}).player_count].join(':')).join('|');
  $('brandsub').textContent = list.length + ' serveur(s) de survie';
  if (sig === survSig && $('survCards').childElementCount) return;
  survSig = sig;
  const box = $('survCards'); box.innerHTML = '';
  list.forEach(s => {
    const card = el('a', 'tile scard'); card.href = pageHash(s.id);
    const [stateLabel] = STATE_LABEL[s.state] || STATE_LABEL.stopped;
    const head = el('span', 'ticon', '🏡');
    const players = (s.live || {}).player_count || 0;
    card.append(head, el('b', '', s.name),
      el('span', '', (SOFTWARE_LABEL[s.software] || 'Vanilla') + ' · ' + (s.version === '?' ? 'dernière version' : 'Minecraft ' + s.version) + ' · ' + players + ' joueur(s)'),
      el('em', '', stateLabel));
    box.append(card);
  });
  const create = el('div', 'tile create');
  create.append(el('span', 'ticon', '＋'), el('b', '', 'Créer un serveur'), el('span', '', 'Tu règles tout ensuite : version, joueurs, sauvegardes…'));
  create.onclick = createSurvival;
  box.append(create);
}
async function createSurvival(){
  try {
    const r = await API.post('/api/servers', {name: 'Survie', kind: 'survival', auto_backup_hours: 6});
    await refresh();
    location.hash = pageHash(r.server.id, 'general');
    toast('Serveur créé : règle-le puis clique sur Démarrer', 'ok', 4500);
  } catch(e){ toast(e.message, 'err'); }
}

/* ------------------------------------------------- page d'un serveur (survie) */
const PAGE_CATS = [
  ['dashboard', '📊', 'Tableau de bord'],
  ['general', '⚙️', 'Général'],
  ['software', '🧩', 'Logiciel'],
  ['content', '🔌', 'Plugins & mods'],
  ['modpacks', '🎁', 'Modpacks'],
  ['resourcepack', '🎨', 'Pack de ressources'],
  ['datapacks', '📦', 'Datapacks'],
  ['players', '👥', 'Joueurs'],
  ['backups', '💾', 'Sauvegardes'],
  ['files', '📝', 'Fichiers de config'],
  ['advanced', '🧪', 'Avancé'],
];
const SOFTWARE_LABEL = {vanilla: 'Vanilla', paper: 'Paper', fabric: 'Fabric', neoforge: 'NeoForge'};
const contentLabel = (sw) => sw === 'paper' ? 'Plugins' : (sw === 'fabric' || sw === 'neoforge') ? 'Mods' : 'Plugins & mods';
const pageHash = (id, cat) => '#/serveur/' + encodeURIComponent(id) + (cat ? '/' + cat : '');
let pageNavSig = '';
$('srvpage').classList.add('page-mode');

/* Le tableau de bord du Speedrun (console, joueurs, boutons) sert aussi de page « Tableau de bord ». */
function placeDash(inPage){
  if (inPage) $('catDashboard').append($('dash'));
  else { $('empty').after($('dash')); }
}

function renderServerPage(){
  const s = S.servers.find(x => x.id === S.pageId);
  if (!s){ if (S.servers.length || S.connected) $('pgName').textContent = 'Serveur introuvable'; return; }
  S.current = s.id;
  const [lab, cls] = STATE_LABEL[s.state] || STATE_LABEL.stopped;
  $('pgState').className = 'state-pill ' + cls;
  $('pgState').replaceChildren(el('span', 'dot ' + dotClass(s.state)), el('span', '', lab));
  $('pgName').textContent = s.name;
  $('pgMeta').textContent = 'Survie · ' + (SOFTWARE_LABEL[s.software] || 'Vanilla') + ' · ' +
    (s.version === '?' ? 'dernière version' : 'Minecraft ' + s.version) + ' · port ' + s.port;
  setChip('pgAddr', '📋', s.address);
  const up = s.state === 'running', busy = ['starting','stopping','resetting','installing'].includes(s.state);
  $('pgStart').disabled = up || busy;
  $('pgStop').disabled = (!up && s.state !== 'error') || busy;
  $('pgBackup').disabled = busy;
  const sig = s.id + '|' + S.pageCat + '|' + s.software;
  if (sig !== pageNavSig){
    pageNavSig = sig;
    const nav = $('pgNav'); nav.innerHTML = '';
    PAGE_CATS.forEach(([cat, icon, label]) => {
      const a = el('a', cat === S.pageCat ? 'on' : '', icon + '  ' + (cat === 'content' ? contentLabel(s.software) : label));
      a.href = pageHash(s.id, cat);
      nav.append(a);
    });
    document.querySelectorAll('#srvpage .cat').forEach(c => c.classList.toggle('on', c.dataset.cat === S.pageCat));
  }
  if (S.pageCat === 'dashboard'){ $('dash').classList.remove('hidden'); renderCockpit(s); }
  else $('brandsub').textContent = up ? 'serveur en ligne' : lab.toLowerCase();
}

async function loadPageCategory(cat){
  const s = S.servers.find(x => x.id === S.pageId) || await (async () => { await refresh(); return S.servers.find(x => x.id === S.pageId); })();
  if (!s) return;
  if (cat === 'general') return fillGeneral(s);
  if (cat === 'players'){ $('catPlayers').append($('panePlayers')); return loadPlayers(s.id); }
  if (cat === 'backups'){ $('catBackups').append($('paneBackups')); return loadBackups(s.id); }
  if (cat === 'software') return openSoftwarePage(s);
  if (['content', 'modpacks', 'resourcepack', 'datapacks'].includes(cat)) return openContentPage(s, cat);
  if (cat === 'files') return openFilesPage(s);
  if (cat === 'advanced'){
    $('advSlot').append($('paneProps'));
    $('sPropSearch').value = '';
    try {
      const r = await API.get('/api/servers/' + s.id + '/settings');
      settingsForm = buildPropsForm($('sPropForm'), r.schema, r.settings);
    } catch(e){ toast('server.properties illisible : ' + e.message, 'err'); }
  }
}

async function ensureVersions(){
  if (S.versions.length) return S.latest;
  const r = await API.get('/api/versions?kind=release&limit=1000');
  S.versions = r.versions; S.latest = r.latest;
  return r.latest;
}

async function fillGeneral(s){
  $('gName').value = s.name; $('gPort').value = s.port;
  $('gRam').value = s.ram_mb; $('gRamLab').textContent = s.ram_mb + ' Mo';
  $('gBackup').value = String(s.auto_backup_hours || 0);
  $('gSeed').value = s.seed_mode === 'fixed' ? (s.seed || '') : '';
  try {
    const latest = await ensureVersions();
    const sel = $('gVersion'); sel.innerHTML = '';
    const first = el('option', '', 'Dernière (' + latest + ')'); first.value = ''; sel.append(first);
    S.versions.forEach(v => { const o = el('option', '', v.id + '  ·  ' + v.released); o.value = v.id; sel.append(o); });
    sel.value = s.version === '?' ? '' : s.version;
    if (sel.value !== (s.version === '?' ? '' : s.version)){ const o = el('option', '', s.version); o.value = s.version; sel.append(o); sel.value = s.version; }
  } catch(e){ toast('Liste des versions indisponible (hors ligne ?)', 'err'); }
  try {
    const r = await API.get('/api/servers/' + s.id + '/settings');
    const st = r.settings;
    $('gDiff').value = st.difficulty; $('gMode').value = st.gamemode;
    $('gMax').value = st['max-players']; $('gMotd').value = st.motd;
    $('gHardcore').setAttribute('aria-checked', String(st.hardcore === 'true'));
    $('gPvp').setAttribute('aria-checked', String(st.pvp !== 'false'));
    $('gCrack').setAttribute('aria-checked', String(st['online-mode'] === 'false'));
  } catch(e){ toast('Réglages illisibles : ' + e.message, 'err'); }
}
['gHardcore', 'gPvp', 'gCrack'].forEach(id => $(id).onclick = flipSwitch);
$('gRam').oninput = e => $('gRamLab').textContent = e.target.value + ' Mo';

async function savePage(body, count){
  const s = cur(); if (!s) return;
  try {
    const r = await API.post('/api/servers/' + s.id, body);
    const rejected = r.rejected || [], later = r.restart_needed || [];
    toast(count ? 'Enregistré' : 'Rien à enregistrer', 'ok', 2500);
    if (rejected.length) toast('Valeur refusée pour : ' + rejected.join(', '), 'err', 8000);
    if (later.length) toast('Pris en compte au prochain démarrage : ' + later.join(', '), '', 7000);
    await refresh();
  } catch(e){ toast(e.message, 'err'); }
}
$('gSave').onclick = () => {
  const seed = $('gSeed').value.trim();
  savePage({
    name: $('gName').value.trim() || 'Survie', version: $('gVersion').value, port: +$('gPort').value,
    ram_mb: +$('gRam').value, auto_backup_hours: +$('gBackup').value,
    seed_mode: seed ? 'fixed' : 'random', seed,
    settings: {
      difficulty: $('gDiff').value, gamemode: $('gMode').value, 'max-players': $('gMax').value,
      motd: $('gMotd').value, hardcore: isOn('gHardcore') ? 'true' : 'false', pvp: isOn('gPvp') ? 'true' : 'false',
      'online-mode': isOn('gCrack') ? 'false' : 'true',
    },
  }, 1);
};
$('advSave').onclick = () => {
  const settings = settingsForm ? settingsForm.read() : {};
  savePage({settings}, Object.keys(settings).length);
  if (settingsForm) Object.entries(settings).forEach(([k, v]) => settingsForm.setSaved(k, v));
};
$('gClean').onclick = async () => {
  const s = cur(); if (!s) return;
  if (!confirm('Effacer le monde de « ' + s.name + ' » ? Une sauvegarde est faite juste avant, la config est conservée.')) return;
  try { await API.post('/api/servers/' + s.id + '/clean'); toast('Monde effacé (sauvegarde faite avant)', 'ok'); }
  catch(e){ toast(e.message, 'err'); }
};
$('gDelete').onclick = async () => {
  const s = cur(); if (!s) return;
  if (!confirm('Supprimer définitivement le serveur « ' + s.name + ' » et son monde ? Ses sauvegardes restent dans le dossier backups.')) return;
  try { await API.del('/api/servers/' + s.id); S.current = null; toast('Serveur supprimé', 'ok'); location.hash = '#/survie'; refresh(); }
  catch(e){ toast(e.message, 'err'); }
};
$('pgStart').onclick = () => act('start');
$('pgStop').onclick = () => act('stop');
$('pgBackup').onclick = () => act('backups');
$('pgAddr').onclick = () => { const s = cur(); if (s) copy(s.address, 'Adresse serveur'); };
