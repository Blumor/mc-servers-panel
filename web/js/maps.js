"use strict";
/* Panel Aventure & mini-jeux : catalogue de maps, import (ZIP ou lien), page Map, page Mini-jeux. */

const MAPS = {catalog: null, busy: {}};  // busy : id serveur -> texte de l'installation en cours
const MAP_ICON = {parkour: '🏃', aventure: '🗡️', puzzle: '🧩', minijeu: '🎯'};
const MAP_CATEGORIES = [['aventure', 'Aventure'], ['parkour', 'Parkour'], ['puzzle', 'Puzzle'], ['minijeu', 'Mini-jeu']];

async function loadCatalog(){
  if (!MAPS.catalog) MAPS.catalog = await API.get('/api/maps');
  return MAPS.catalog;
}

/* ------------------------------------------------------------ liste du panel */
let advSig = '';
function renderAdventureList(){
  const list = S.servers.filter(s => kindOf(s) === 'adventure');
  const sig = list.map(s => [s.id, s.name, s.state, s.version, (s.map || {}).title, (s.live || {}).player_count, MAPS.busy[s.id]].join(':')).join('|');
  $('brandsub').textContent = list.length ? plural(list.length, 'serveur aventure', 'serveurs aventure') : 'choisis une map';
  if (!$('advCatalog').childElementCount) fillCatalog($('advCatalog'), $('advSites'), (m) => playMap({id: m.id, title: m.title}), 'Jouer');
  if (!$('advImport').childElementCount) $('advImport').append(importBox((source) => playMap(source)));
  if (sig === advSig) return;
  advSig = sig;
  const box = $('advCards'); box.innerHTML = '';
  $('advMineTitle').classList.toggle('hidden', !list.length);
  list.forEach(s => {
    const card = el('a', 'tile scard'); card.href = pageHash(s.id);
    const [stateLabel] = STATE_LABEL[s.state] || STATE_LABEL.stopped;
    const m = s.map || {};
    card.append(el('span', 'ticon', MAP_ICON[m.category] || '🗺️'), el('b', '', s.name),
      el('span', '', (m.title ? m.title : 'Monde sans map') + ' · ' + (s.version === '?' ? 'dernière version' : 'Minecraft ' + s.version) +
                     ' · ' + plural((s.live || {}).player_count || 0, 'joueur')),
      el('em', '', MAPS.busy[s.id] ? 'Installation…' : stateLabel));
    box.append(card);
  });
}

function fillCatalog(grid, sites, onPick, label){
  grid.innerHTML = ''; grid.append(el('div', 'muted', 'Chargement du catalogue…'));
  loadCatalog().then(cat => {
    grid.innerHTML = '';
    cat.maps.forEach(m => grid.append(mapCard(m, onPick, label)));
    const blank = el('div', 'ccard mapcard blank');
    blank.append(el('div', 'micon', '🎯'), (() => { const h = el('div', ''); h.append(el('div', 't', 'Monde vide pour mini-jeux'), el('div', 'a', 'Monde normal, sans map')); return h; })(),
      el('div', 'd', 'Un monde Minecraft classique en mode aventure, où ajouter des mini-jeux (Manhunt, OneBlock, BedWars…) depuis la page Mini-jeux.'));
    const foot = el('div', 'foot'); const b = el('button', 'btn sm ghost', 'Créer');
    b.onclick = createBlankAdventure; foot.append(el('span', ''), b); blank.append(foot);
    if (label === 'Jouer') grid.append(blank);
    if (sites){
      sites.innerHTML = '';
      cat.sites.forEach(x => {
        const a = el('a', 'site'); a.href = x.url; a.target = '_blank'; a.rel = 'noopener';
        a.append(el('b', '', x.title + ' ↗'), el('span', '', x.text));
        sites.append(a);
      });
    }
  }).catch(e => { grid.innerHTML = ''; grid.append(el('div', 'note warn', 'Catalogue indisponible : ' + e.message)); });
}

function mapCard(m, onPick, label){
  const card = el('div', 'ccard mapcard');
  const head = el('div', '');
  head.append(el('div', 't', m.title), el('div', 'a', 'par ' + m.author + ' · ' + (MAPS.catalog.categories[m.category] || m.category) + ' · ' + m.players));
  const foot = el('div', 'foot');
  const link = el('a', 'a', 'Page de l’auteur'); link.href = m.page; link.target = '_blank'; link.rel = 'noopener';
  const btn = el('button', 'btn sm', label);
  btn.onclick = () => onPick(m, btn);
  foot.append(link, btn);
  card.append(el('div', 'micon', MAP_ICON[m.category] || '🗺️'), head, el('div', 'd', m.description), foot);
  return card;
}

/* Zone d'import : fichier ZIP (glisser-déposer ou parcourir) ou lien https. */
function importBox(onSource){
  const wrap = el('div', 'mapimport');
  const catSel = el('select'); catSel.title = 'Type de map : règle le mode de jeu, la difficulté et le PvP';
  MAP_CATEGORIES.forEach(([v, l]) => { const o = el('option', '', l); o.value = v; catSel.append(o); });
  const drop = el('label', 'drop');
  const file = el('input'); file.type = 'file'; file.accept = '.zip,application/zip'; file.className = 'hidden';
  drop.append(el('b', '', '📁 Dépose le fichier .zip de la map ici'), el('span', '', 'ou clique pour le choisir'), file);
  const pick = (f) => {
    if (!f) return;
    if (!/\.zip$/i.test(f.name)){ toast('Il faut le fichier .zip de la map (les .mcworld sont des maps Bedrock, incompatibles).', 'err', 6000); return; }
    onSource({file: f, title: f.name.replace(/\.zip$/i, ''), category: catSel.value});
  };
  file.onchange = () => { pick(file.files[0]); file.value = ''; };
  drop.ondragover = (e) => { e.preventDefault(); drop.classList.add('over'); };
  drop.ondragleave = () => drop.classList.remove('over');
  drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove('over'); pick(e.dataTransfer.files[0]); };
  const row = el('div', 'csearch');
  const url = el('input'); url.placeholder = 'ou colle un lien direct https://…/map.zip';
  const go = el('button', 'btn sm', 'Installer');
  go.onclick = () => {
    const v = url.value.trim();
    if (!/^https:\/\//i.test(v)){ toast('Colle un lien https:// vers le fichier .zip de la map.', 'err'); return; }
    onSource({url: v, title: decodeURIComponent(v.split('/').pop().split('?')[0]).replace(/\.zip$/i, '') || 'Map', category: catSel.value});
  };
  row.append(url, go);
  const typeRow = el('div', 'maptype'); typeRow.append(el('span', '', 'Type de map'), catSel);
  wrap.append(drop, row, typeRow,
    el('div', 'hint', 'Maps Java uniquement. La version de Minecraft est lue dans la map et choisie toute seule ; blocs de commande et vol sont activés.'));
  return wrap;
}

/* ---------------------------------------------------------------- création */
async function newAdventureServer(name){
  const r = await API.post('/api/servers', {name: (name || 'Aventure').slice(0, 40), kind: 'adventure'});
  await refresh();
  return S.servers.find(x => x.id === r.server.id) || r.server;
}
async function createBlankAdventure(){
  try {
    const s = await newAdventureServer('Mini-jeux');
    location.hash = pageHash(s.id, 'minigames');
    toast('Serveur créé : ajoute des mini-jeux puis clique sur Démarrer', 'ok', 5000);
  } catch(e){ toast(e.message, 'err'); }
}
async function playMap(source){
  try {
    const s = await newAdventureServer(source.title);
    location.hash = pageHash(s.id, 'map');
    await sendMap(s, source);
  } catch(e){ toast(e.message, 'err', 7000); }
}

async function sendMap(s, source){
  MAPS.busy[s.id] = source.file ? 'Envoi de la map…' : 'Téléchargement de la map…';
  advSig = ''; refreshMapPage(s.id);
  try {
    if (source.file) await uploadMap(s, source);
    else await API.post('/api/servers/' + s.id + '/map/install', {id: source.id || '', url: source.url || '', title: source.title || '', category: source.category || ''});
    MAPS.busy[s.id] = 'Installation de la map…';
  } catch(e){
    delete MAPS.busy[s.id];
    toast(e.message, 'err', 7000);
  }
  advSig = ''; refreshMapPage(s.id);
}

/* XHR plutôt que fetch : seule façon d'afficher la progression d'un envoi de fichier. */
function uploadMap(s, source){
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/servers/' + encodeURIComponent(s.id) + '/map/upload?name=' + encodeURIComponent(source.file.name) +
             '&category=' + encodeURIComponent(source.category || 'aventure'));
    xhr.setRequestHeader('Content-Type', 'application/zip');
    xhr.upload.onprogress = (e) => {
      if (!e.lengthComputable) return;
      MAPS.busy[s.id] = 'Envoi de la map : ' + Math.round(e.loaded / e.total * 100) + ' %';
      jobBar.style.width = Math.max(6, e.loaded / e.total * 50) + '%';
      $('brandsub').textContent = MAPS.busy[s.id];
    };
    xhr.onload = () => {
      let data = {};
      try { data = JSON.parse(xhr.responseText); } catch(e){ data = {ok: false, error: 'Réponse illisible du panel'}; }
      if (xhr.status >= 400 || data.ok === false) reject(new Error(data.error || 'HTTP ' + xhr.status)); else resolve(data);
    };
    xhr.onerror = () => reject(new Error('Envoi interrompu'));
    xhr.send(source.file);
  });
}

/* Fin d'une tâche « map » ou « map-restart ». */
function onMapJob(job){
  delete MAPS.busy[job.target];
  advSig = '';
  if (job.status === 'done'){
    const res = job.result || {};
    if (job.kind === 'map') toast('Map installée : ' + (res.map || '') + ' (Minecraft ' + (res.version || '?') + '). Clique sur Démarrer !', 'ok', 6000);
    else toast('Map remise à zéro : tout est comme au premier lancement', 'ok', 5000);
    (res.notes || []).forEach(n => toast(n, '', 9000));
  }
  refresh().then(() => refreshMapPage(job.target));
}

function refreshMapPage(id){
  if (S.view === 'server' && S.pageId === id && S.pageCat === 'map'){ const s = cur(); if (s) openMapPage(s); }
  if (S.view === 'adventure') render();
}

/* ----------------------------------------------------------------- page Map */
async function openMapPage(s){
  const box = $('catMap'); box.innerHTML = '';
  box.append(el('h3', 'cattitle', 'Map'));
  if (MAPS.busy[s.id]){
    box.append(el('div', 'note', '⏳ ' + MAPS.busy[s.id] + ' La version de Minecraft, le monde et les réglages se mettent en place tout seuls.'));
    return;
  }
  let info = {map: null, original: null, resource_pack: false};
  try { info = await API.get('/api/servers/' + s.id + '/map'); } catch(e){ /* page quand même utilisable */ }
  const m = info.map;
  if (m){
    const card = el('div', 'mapnow');
    const text = el('div', '');
    text.append(el('b', '', (MAP_ICON[m.category] || '🗺️') + ' ' + m.title),
      el('div', 'm', [m.author ? 'par ' + m.author : '', (MAPS.catalog && MAPS.catalog.categories[m.category]) || m.category,
                      m.map_version ? 'faite pour Minecraft ' + m.map_version : 'version d’origine inconnue',
                      'installée ' + fmtAgo(m.installed)].filter(Boolean).join(' · ')));
    if (m.page && /^https:\/\//.test(m.page)){
      const a = el('a', 'a', 'Page de la map ↗'); a.href = m.page; a.target = '_blank'; a.rel = 'noopener'; text.append(a);
    }
    const acts = el('div', 'acts');
    const again = el('button', 'btn sm', '🔁 Recommencer la map');
    again.disabled = !info.original;
    again.title = info.original ? 'Remet la map comme au premier lancement' : 'Pas de copie d’origine : réinstalle la map';
    again.onclick = async () => {
      if (!confirm('Recommencer « ' + m.title + ' » ? Toute la progression des joueurs sur cette map est effacée (pas de sauvegarde).')) return;
      try { await API.post('/api/servers/' + s.id + '/map/restart'); MAPS.busy[s.id] = 'Remise à zéro de la map…'; openMapPage(s); }
      catch(e){ toast(e.message, 'err'); }
    };
    acts.append(again);
    if (info.resource_pack){
      const rp = el('a', 'btn sm ghost', '🎨 Pack de ressources de la map'); rp.href = '/api/servers/' + encodeURIComponent(s.id) + '/map/resources';
      rp.title = 'À donner aux joueurs : Options → Packs de ressources → Ouvrir le dossier';
      acts.append(rp);
    }
    card.append(text, acts);
    box.append(card);
  } else {
    box.append(el('div', 'note', 'Pas de map sur ce serveur : c’est un monde normal. Choisis-en une ci-dessous, ou ajoute des mini-jeux.'));
  }
  const up = s.state === 'running' || s.state === 'starting';
  box.append(el('div', 'sectitle', m ? 'Changer de map' : 'Choisir une map'));
  if (up) box.append(el('div', 'note warn', 'Arrête le serveur pour changer de map.'));
  const confirmReplace = () => !m || confirm('Remplacer « ' + m.title + ' » ? Le monde actuel est sauvegardé avant.');
  const grid = el('div', 'cgrid');
  box.append(grid);
  fillCatalog(grid, null, (map) => { if (confirmReplace()) sendMap(s, {id: map.id, title: map.title}); }, 'Installer');
  box.append(el('div', 'sectitle', 'Importer ta map'), importBox((source) => { if (confirmReplace()) sendMap(s, source); }));
}
