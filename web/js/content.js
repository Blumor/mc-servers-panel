"use strict";
/* Pages Logiciel, Plugins/Mods, Modpacks, Pack de ressources, Datapacks, Fichiers de config. */

/* ------------------------------------------------------------------ Logiciel */
const SOFTWARE_INFO = {
  vanilla: ['Minecraft officiel', 'Le jeu tel quel, sans ajout. Idéal pour jouer simplement.'],
  paper: ['Plugins', 'Plugins côté serveur (protection, économie, homes…) et meilleures performances. Les joueurs n’installent rien.'],
  fabric: ['Mods', 'Mods légers et d’optimisation. Les joueurs doivent installer les mêmes mods.'],
  neoforge: ['Gros mods', 'Gros mods et modpacks (Create, Mekanism…). Les joueurs doivent installer les mêmes mods.'],
};

async function openSoftwarePage(s){
  const grid = $('swGrid'); grid.innerHTML = '';
  grid.append(el('div', 'muted', 'Vérification des logiciels disponibles…'));
  let r;
  try { r = await API.get('/api/software?version=' + encodeURIComponent(s.version === '?' ? '' : s.version)); }
  catch(e){ grid.innerHTML = ''; grid.append(el('div', 'note warn', 'Impossible de vérifier : ' + e.message)); return; }
  grid.innerHTML = '';
  Object.keys(SOFTWARE_INFO).forEach(sw => {
    const [tag, text] = SOFTWARE_INFO[sw];
    const current = s.software === sw, ok = r.available[sw];
    const card = el('div', 'swcard' + (current ? ' on' : '') + (ok ? '' : ' off'));
    card.append(el('span', 'tagline', tag), el('b', '', SOFTWARE_LABEL[sw]), el('p', '', ok ? text : 'Pas disponible pour Minecraft ' + r.version + '.'));
    const btn = el('button', 'btn sm' + (current ? ' ghost' : ''), current ? '✓ Actuel' : 'Choisir');
    btn.disabled = current || !ok;
    btn.onclick = async () => {
      if (!confirm('Passer « ' + s.name + ' » en ' + SOFTWARE_LABEL[sw] + ' ? Le monde est sauvegardé avant.')) return;
      try {
        await API.post('/api/servers/' + s.id + '/software', {software: sw});
        toast('Logiciel : ' + SOFTWARE_LABEL[sw] + ' (téléchargé au prochain démarrage)', 'ok', 4500);
        await refresh(); openSoftwarePage(cur());
      } catch(e){ toast(e.message, 'err', 7000); }
    };
    card.append(btn);
    grid.append(card);
  });
}

/* ---------------------------------------------------------- contenu Modrinth */
const CONTENT_INFO = {
  plugin: {title: 'Plugins', hint: 'Plugins Paper, depuis Modrinth. Installés avec leurs dépendances, actifs au prochain démarrage.',
           placeholder: 'Chercher un plugin (EssentialsX, LuckPerms, WorldEdit…)'},
  mod: {title: 'Mods', hint: 'Mods depuis Modrinth, avec leurs dépendances. Les mods uniquement côté joueur (graphismes…) sont écartés.',
        placeholder: 'Chercher un mod (Create, Lithium, Waystones…)'},
  modpack: {title: 'Modpacks', hint: 'Un modpack remplace la version de Minecraft, le logiciel et les mods du serveur. Le monde est sauvegardé avant. Serveur arrêté.',
            placeholder: 'Chercher un modpack (Fabric ou NeoForge)'},
  resourcepack: {title: 'Pack de ressources', hint: 'Envoyé automatiquement aux joueurs à la connexion. Un seul pack à la fois.',
                 placeholder: 'Chercher un pack de ressources'},
  datapack: {title: 'Datapacks', hint: 'Ajoutés au monde (recettes, mécaniques, aventures). Actifs au prochain démarrage.',
             placeholder: 'Chercher un datapack'},
};
const CAT_BOX = {content: 'catContent', modpacks: 'catModpacks', resourcepack: 'catResourcepack', datapacks: 'catDatapacks', minigames: 'catMinigames'};
/* Page Mini-jeux : catégorie « minigame » de Modrinth, dans le format que le logiciel accepte. */
const MINIGAME_TYPE = {vanilla: 'datapack', paper: 'plugin', fabric: 'mod', neoforge: 'mod'};
const MINIGAME_INFO = {title: 'Mini-jeux', hint: 'Mini-jeux depuis Modrinth : Manhunt, OneBlock, BedWars, Duels… En Vanilla ce sont des datapacks ; passe en Paper (catégorie Logiciel) pour les mini-jeux en plugin.',
                       placeholder: 'Chercher un mini-jeu (manhunt, oneblock, bedwars…)'};
const CP = {box: null, ctype: null, query: '', offset: 0, timer: null};

function fmtCount(n){ return n >= 1e6 ? (n/1e6).toFixed(1) + ' M' : n >= 1e3 ? Math.round(n/1e3) + ' k' : String(n); }
function icon(url){ const img = el('img'); img.alt = ''; img.loading = 'lazy'; if (url) img.src = url; img.onerror = () => { img.removeAttribute('src'); }; return img; }

async function openContentPage(s, cat){
  const box = $(CAT_BOX[cat]); box.innerHTML = '';
  const ctype = cat === 'content' ? ({paper: 'plugin', fabric: 'mod', neoforge: 'mod'})[s.software]
              : cat === 'minigames' ? MINIGAME_TYPE[s.software] || 'datapack'
              : ({modpacks: 'modpack', resourcepack: 'resourcepack', datapacks: 'datapack'})[cat];
  if (!ctype){
    box.append(el('h3', 'cattitle', 'Plugins & mods'));
    const note = el('div', 'note', 'Le serveur est en Vanilla. Pour des plugins, passe en Paper ; pour des mods, en Fabric ou NeoForge : ');
    const link = el('a', '', 'catégorie Logiciel'); link.href = pageHash(s.id, 'software'); note.append(link);
    box.append(note);
    return;
  }
  const info = cat === 'minigames' ? MINIGAME_INFO : CONTENT_INFO[ctype];
  Object.assign(CP, {box, ctype, cat, query: '', offset: 0, category: cat === 'minigames' ? 'minigame' : ''});
  box.append(el('h3', 'cattitle', info.title), el('div', 'hint', info.hint));
  if (ctype === 'mod'){
    const share = el('div', 'note');
    share.append('Les joueurs doivent avoir les mêmes mods. ');
    const a = el('a', '', '📦 Télécharger le pack pour les joueurs (.mrpack)'); a.href = '/api/servers/' + encodeURIComponent(s.id) + '/client-pack';
    share.append(a, ' — à importer dans Modrinth App ou Prism Launcher. (Lunar Client ne charge pas de mods.)');
    box.append(share);
  }
  if (ctype !== 'modpack'){
    const head = el('div', 'sectitle', 'Installés ');
    const upd = el('button', 'btn sm ghost', 'Vérifier les mises à jour'); upd.style.marginLeft = 'auto';
    upd.onclick = () => checkUpdates(s);
    head.append(el('span', 'n', ''), upd);
    box.append(head, el('div', 'crows'));
  } else if (s.modpack){
    box.append(el('div', 'note', 'Modpack actuel : ' + s.modpack.title + ' ' + (s.modpack.version || '')));
  }
  const search = el('div', 'csearch');
  const input = el('input'); input.placeholder = info.placeholder;
  input.oninput = () => { clearTimeout(CP.timer); CP.timer = setTimeout(() => { CP.query = input.value.trim(); CP.offset = 0; runSearch(s, false); }, 350); };
  search.append(input);
  box.append(el('div', 'sectitle', ctype === 'modpack' ? 'Modpacks' : 'Ajouter'), search, el('div', 'cgrid'));
  const more = el('button', 'btn sm ghost hidden', 'Plus de résultats'); more.style.marginTop = '12px';
  more.onclick = () => { CP.offset += 20; runSearch(s, true); };
  box.append(more);
  CP.more = more;
  if (ctype !== 'modpack') loadInstalled(s);
  runSearch(s, false);
}

async function loadInstalled(s){
  const rows = CP.box.querySelector('.crows'); if (!rows) return;
  let r;
  try { r = await API.get('/api/servers/' + s.id + '/content'); } catch(e){ toast(e.message, 'err'); return; }
  const items = r.items.filter(i => CP.ctype === 'mod' ? (i.type === 'mod') : i.type === CP.ctype);
  CP.box.querySelector('.sectitle .n').textContent = items.length ? plural(items.length, 'installé') : '';
  rows.innerHTML = '';
  if (!items.length){ rows.append(el('div', 'muted', 'Rien d’installé pour l’instant.')); return; }
  items.forEach(i => {
    const row = el('div', 'crow');
    const text = el('div', '');
    const title = el('div', 't', i.title);
    if (CP.updates && CP.updates[i.project_id]) title.append(el('span', 'badge-up', '→ ' + CP.updates[i.project_id]));
    text.append(title, el('div', 'm', (i.version_number || '') + (i.from_pack ? ' · fourni par le modpack' : '') + (i.enabled === false ? ' · désactivé' : '')));
    const acts = el('div', 'acts');
    const key = i.project_id || i.path;
    if (i.type === 'resourcepack'){
      const sw = makeSwitch(!!i.required); sw.title = 'Obligatoire pour se connecter';
      sw.addEventListener('change', () => contentOption(s, key, {required: sw.getAttribute('aria-checked') === 'true'}));
      acts.append(el('span', 'm', 'Obligatoire'), sw);
    } else {
      const sw = makeSwitch(i.enabled !== false); sw.title = 'Activé';
      sw.addEventListener('change', () => contentOption(s, key, {enabled: sw.getAttribute('aria-checked') === 'true'}));
      acts.append(sw);
    }
    if (CP.updates && CP.updates[i.project_id]){
      const up = el('button', 'btn sm', 'Mettre à jour');
      up.onclick = () => installContent(s, i.project_id, i.type, 'update');
      acts.append(up);
    }
    const rm = el('button', 'btn sm danger', 'Retirer');
    rm.onclick = async () => {
      if (!confirm('Retirer « ' + i.title + ' » ?')) return;
      try { await API.post('/api/servers/' + s.id + '/content/remove', {project_id: key}); loadInstalled(s); runSearch(s, false); }
      catch(e){ toast(e.message, 'err'); }
    };
    acts.append(rm);
    row.append(icon(i.icon_url), text, acts);
    rows.append(row);
  });
}

async function contentOption(s, key, opt){
  try { await API.post('/api/servers/' + s.id + '/content/option', Object.assign({project_id: key}, opt)); loadInstalled(s); }
  catch(e){ toast(e.message, 'err'); }
}

async function checkUpdates(s){
  try {
    const r = await API.get('/api/servers/' + s.id + '/content/updates');
    CP.updates = Object.fromEntries(r.updates.map(u => [u.project_id, u.latest]));
    toast(r.updates.length ? plural(r.updates.length, 'mise à jour disponible', 'mises à jour disponibles') : 'Tout est à jour', 'ok');
    loadInstalled(s);
  } catch(e){ toast(e.message, 'err'); }
}

async function runSearch(s, append){
  const box = CP.box, grid = box.querySelector('.cgrid'); if (!grid) return;
  const ctype = CP.ctype;
  if (!append){ grid.innerHTML = ''; grid.append(el('div', 'muted', 'Recherche…')); }
  let r;
  try {
    r = await API.get('/api/servers/' + s.id + '/content/search?type=' + ctype + '&q=' + encodeURIComponent(CP.query) + '&offset=' + CP.offset +
                      (CP.category ? '&category=' + CP.category : ''));
  } catch(e){ grid.innerHTML = ''; grid.append(el('div', 'note warn', 'Modrinth injoignable : ' + e.message)); return; }
  if (ctype !== CP.ctype || box !== CP.box) return;  // l'utilisateur a changé de page entre-temps
  if (!append) grid.innerHTML = '';
  if (!r.hits.length && !append) grid.append(el('div', 'muted', 'Aucun résultat compatible avec ce serveur.'));
  r.hits.forEach(h => {
    const card = el('div', 'ccard');
    const head = el('div', '');
    head.append(el('div', 't', h.title), el('div', 'a', 'par ' + h.author + ' · ' + fmtCount(h.downloads) + ' téléchargements'));
    const foot = el('div', 'foot');
    const btn = el('button', 'btn sm', ctype === 'modpack' ? 'Installer le modpack' : ctype === 'resourcepack' ? 'Utiliser' : 'Installer');
    if (h.installed){ btn.textContent = '✓ Installé'; btn.disabled = true; }
    if (h.client_only){ btn.textContent = 'Côté joueur seulement'; btn.disabled = true; btn.title = 'Ce mod ne sert qu’au client (graphismes, interface) : inutile sur un serveur.'; }
    btn.onclick = () => {
      if (ctype === 'modpack' && !confirm('Installer « ' + h.title + ' » ? La version de Minecraft, le logiciel et les mods du serveur seront remplacés. Le monde est sauvegardé avant.')) return;
      btn.disabled = true; btn.textContent = 'Installation…';
      installContent(s, h.project_id, ctype, 'install');
    };
    const link = el('a', 'a', 'Voir sur Modrinth'); link.href = 'https://modrinth.com/project/' + encodeURIComponent(h.slug); link.target = '_blank'; link.rel = 'noopener';
    foot.append(link, btn);
    card.append(icon(h.icon_url), head, el('div', 'd', h.description), foot);
    grid.append(card);
  });
  CP.more.classList.toggle('hidden', CP.offset + 20 >= r.total);
}

async function installContent(s, projectId, ctype, op){
  try {
    await API.post('/api/servers/' + s.id + '/content/' + op, {project_id: projectId, type: ctype});
    toast(op === 'update' ? 'Mise à jour…' : 'Installation…', '', 2500);
  } catch(e){ toast(e.message, 'err', 7000); }
}

/* Fin d'une installation (job « content ») : on rafraîchit la page ouverte. */
function onContentJob(job){
  if (job.status === 'done'){
    const res = job.result || {};
    toast('Installé : ' + (res.installed || '') + (res.version ? ' ' + res.version : ''), 'ok', 4500);
    (res.notes || []).forEach(n => toast(n, n.startsWith('Attention') || n.includes('introuvable') || n.includes('non installée') ? 'err' : '', 7000));
    if (res.software) refresh();
  }
  if (S.view === 'server' && CP.box && cur() && cur().id === job.target){
    if (CP.ctype !== 'modpack') loadInstalled(cur());
    runSearch(cur(), false);
  }
}

/* ------------------------------------------------------- fichiers de config */
const FP = {path: null};
async function openFilesPage(s){
  const list = $('fileList'); list.innerHTML = '';
  $('fileText').value = ''; $('fileText').disabled = true; $('fileSave').disabled = true;
  $('filePath').textContent = 'Choisis un fichier à gauche.'; FP.path = null;
  let r;
  try { r = await API.get('/api/servers/' + s.id + '/files'); } catch(e){ list.append(el('div', 'note warn', e.message)); return; }
  if (!r.files.length){ list.append(el('div', 'muted', 'Aucun fichier de config pour l’instant : démarre le serveur une fois, plugins et mods créent les leurs.')); return; }
  r.files.forEach(f => {
    const b = el('button', '', f.path); b.title = f.path + ' (' + fmtBytes(f.size) + ')';
    b.onclick = async () => {
      list.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b));
      try {
        const t = await API.get('/api/servers/' + s.id + '/file?path=' + encodeURIComponent(f.path));
        FP.path = f.path; $('filePath').textContent = f.path;
        $('fileText').value = t.text; $('fileText').disabled = false; $('fileSave').disabled = false;
      } catch(e){ toast(e.message, 'err'); }
    };
    list.append(b);
  });
}
$('fileSave').onclick = async () => {
  const s = cur(); if (!s || !FP.path) return;
  if (s.state === 'running' && !confirm('Le serveur tourne : certains plugins réécrivent leur config en s’arrêtant. Enregistrer quand même ?')) return;
  try { await API.post('/api/servers/' + s.id + '/file', {path: FP.path, text: $('fileText').value}); toast('Fichier enregistré (ancienne version : .bak)', 'ok'); }
  catch(e){ toast(e.message, 'err'); }
};
