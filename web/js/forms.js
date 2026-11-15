"use strict";
/* Éditeur server.properties et listes de joueurs. */
/* ------------------------------------------------ éditeur de server.properties */
function makeSwitch(on){
  const b = el('button','switch'); b.type='button'; b.setAttribute('role','switch');
  b.setAttribute('aria-checked', String(!!on)); b.appendChild(el('i'));
  b.onclick = () => {
    b.setAttribute('aria-checked', b.getAttribute('aria-checked')==='true'?'false':'true');
    b.dispatchEvent(new Event('change', {bubbles:true}));
  };
  return b;
}
function tagEl(cls, text){ return el('span','tag '+cls, text); }

/** Construit le formulaire et renvoie { read(), setSaved(key, value), filter(q) }.
 *  opts.exclude : clés à ne pas afficher (pilotées par un autre contrôle de la fenêtre). */
function buildPropsForm(container, schema, values, opts){
  opts = opts || {};
  container.innerHTML = '';
  const fields = new Map();          // key -> {row, get, initial, spec, setSaved}
  const known = new Set(schema.fields.map(f => f.key));
  const exclude = new Set(opts.exclude || []);
  const buckets = new Map(schema.groups.map(g => [g.id, []]));
  schema.fields.forEach(f => { if (!exclude.has(f.key)) buckets.get(f.group).push(f); });

  // Clés présentes dans le fichier mais absentes du schéma : mods, plugins,
  // versions plus récentes. On les édite en texte plutôt que de les cacher.
  const extras = Object.keys(values || {})
    .filter(k => !known.has(k) && k !== 'query.port')
    .sort()
    .map(k => ({key:k, group:'other', type:'str', label:k, unknown:true}));
  if (extras.length) buckets.set('other', extras);

  const groupLabels = new Map(schema.groups.map(g => [g.id, g.label]));
  groupLabels.set('other', 'Clés non standard');

  let first = true;
  for (const [gid, list] of buckets){
    if (!list.length) continue;
    const det = el('details','pgroup'); if (first){ det.open = true; first = false; }
    const sum = document.createElement('summary');
    sum.append(el('span','', groupLabels.get(gid) || gid), el('span','count', list.length + ' réglages'));
    det.append(sum);
    const body = el('div','pbody');
    list.forEach(f => body.append(propRow(f, values, fields)));
    det.append(body);
    container.append(det);
  }

  return {
    read(){
      const changed = {};
      for (const [key, f] of fields){
        if (f.spec.locked) continue;
        const now = f.get();
        if (now !== f.initial) changed[key] = now;
      }
      return changed;
    },
    /** Valeur déjà enregistrée ailleurs (interrupteur rapide) : met la ligne à jour
     *  sans reconstruire le formulaire, donc sans perdre les modifications en cours. */
    setSaved(key, value){
      const f = fields.get(key);
      if (f) f.setSaved(String(value));
    },
    filter(query){
      const q = (query||'').trim().toLowerCase();
      container.querySelectorAll('details.pgroup').forEach(det => {
        let visible = 0;
        det.querySelectorAll('.prow').forEach(row => {
          const hit = !q || row.dataset.search.includes(q);
          row.classList.toggle('hidden', !hit);
          if (hit) visible++;
        });
        det.classList.toggle('hidden', visible === 0);
        if (q && visible) det.open = true;
      });
    },
  };
}

function propRow(spec, values, fields){
  const raw = values && values[spec.key] != null ? String(values[spec.key]) : (spec.default || '');
  const row = el('div','prow' + (spec.locked ? ' locked' : ''));
  row.dataset.search = (spec.label + ' ' + spec.key + ' ' + (spec.hint||'')).toLowerCase();

  const lbl = el('div','lbl');
  lbl.append(el('span','', spec.label));
  lbl.append(el('code','', spec.key));
  if (spec.hint) lbl.append(el('div','hint', spec.hint));
  const tags = el('div','tags');
  if (spec.locked) tags.append(tagEl('lock','géré par le panel'));
  if (spec.restart) tags.append(tagEl('rst','redémarrage requis'));
  if (spec.unknown) tags.append(tagEl('lock','hors schéma'));
  if (tags.childElementCount) lbl.append(tags);

  const ctl = el('div','ctl');
  let get, set;
  if (spec.type === 'bool'){
    // invert : l'interrupteur montre l'inverse de la valeur (« accepter les crack » = online-mode=false).
    const inv = !!spec.invert;
    const sw = makeSwitch((raw === 'true') !== inv);
    if (spec.locked) sw.disabled = true;
    ctl.append(sw);
    get = () => ((sw.getAttribute('aria-checked') === 'true') !== inv) ? 'true' : 'false';
    set = v => sw.setAttribute('aria-checked', String((v === 'true') !== inv));
    sw.addEventListener('change', mark);
  } else if (spec.type === 'enum'){
    const sel = document.createElement('select');
    (spec.options||[]).forEach(o => { const op = el('option','', o.replace('minecraft:','')); op.value = o; sel.append(op); });
    if (!spec.options.includes(raw)) { const op = el('option','', raw); op.value = raw; sel.append(op); }
    sel.value = raw; sel.disabled = !!spec.locked; ctl.append(sel);
    get = () => sel.value; set = v => { sel.value = v; };
    sel.addEventListener('change', mark);
  } else {
    const inp = document.createElement('input');
    inp.type = spec.type === 'int' ? 'number' : 'text';
    if (spec.min != null) inp.min = spec.min;
    if (spec.max != null) inp.max = spec.max;
    inp.value = raw; inp.disabled = !!spec.locked; ctl.append(inp);
    get = () => inp.value.trim(); set = v => { inp.value = v; };
    inp.addEventListener('input', mark);
  }
  row.append(lbl, ctl);
  const field = {row, get, initial: raw, spec};
  field.setSaved = v => { set(v); field.initial = v; mark(); };
  fields.set(spec.key, field);
  function mark(){ row.classList.toggle('changed', get() !== field.initial); }
  return row;
}

/* ------------------------------------------------------------- listes joueurs */
function renderPlayerChips(box, names, onRemove){
  box.innerHTML = '';
  if (!names.length){ box.append(el('span','muted','Personne pour l’instant')); return; }
  names.forEach(entry => {
    const name = typeof entry === 'string' ? entry : entry.name;
    const chip = el('span','pchip');
    const img = el('img'); img.alt = '';
    img.src = 'https://minotar.net/avatar/' + encodeURIComponent(name) + '/26';
    img.onerror = () => img.replaceWith(el('span','','👤'));
    chip.append(img, el('span','', name));
    const rm = el('button','rm','×'); rm.type = 'button'; rm.title = 'Retirer ' + name;
    rm.onclick = () => onRemove(name);
    chip.append(rm);
    box.append(chip);
  });
}

