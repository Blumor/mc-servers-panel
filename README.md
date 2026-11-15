# MC Speedrun Panel

Panel web pour lancer et réinitialiser un serveur Minecraft local en un clic. Pensé pour le
speedrun coop : quand l'un de vous meurt, un clic (ou la touche <kbd>R</kbd>) et vous repartez sur
un monde neuf.

Rien à installer à la main à part Python : Java et le `.jar` officiel Mojang sont téléchargés
automatiquement.

---

## Démarrage rapide

| Système | Lancer |
|---|---|
| **Windows** | télécharger **`MCSpeedrunPanel.exe`** dans les [Releases](https://github.com/Blumor/mc-speedrun-panel/releases/latest), le ranger dans un dossier à lui, double-clic. Rien d'autre à installer. |
| Linux / WSL / macOS | `./panel.sh` (Python 3.9+) |
| Windows, depuis le code source | double-clic sur `PANEL.bat`, ou `py -m mcpanel` |

L'exe range mondes et réglages dans `mcpanel-data`, à côté de lui. Il n'est pas signé : si Windows
affiche « Windows a protégé votre ordinateur », *Informations complémentaires* → *Exécuter quand
même*. Avec le *Contrôle intelligent des applications* activé, Windows refuse tout exe non signé :
passer par le code source.

1. Le navigateur s'ouvre sur `http://localhost:8765/`. Fermer la fenêtre noire arrête le panel
   et ses serveurs ; relancer l'exe alors qu'il tourne déjà rouvre juste l'onglet.
2. **Créer mon serveur** → version, RAM, Turbo → **Créer & démarrer**.
3. Dans Minecraft : *Multijoueur* → *Connexion directe* → `localhost`.
4. Ton pote : l'adresse 🌐 en haut du panel (clic = copie). Voir [Jouer à deux](#jouer-à-deux).

Options : `./panel.sh --port 9000`, `--no-browser`, `--lan` (panel accessible depuis le réseau
local, **sans mot de passe**, réseau de confiance uniquement).

---

## Les panels

À l'ouverture, l'accueil propose un type de partie :

| Panel | Pour quoi |
|---|---|
| 💀 **Speedrun** | Mondes hardcore jetables : reset en un clic, mode Turbo (détails ci-dessous). |
| 🏡 **Survie entre potes** | Un monde qui dure. « Créer un serveur » ouvre sa page complète, catégories à gauche : Tableau de bord, Général, Logiciel, Plugins/Mods, Modpacks, Pack de ressources, Datapacks, Joueurs, Sauvegardes, Fichiers de config, Avancé. On règle tout, puis Démarrer. **Sauvegardes automatiques**, pas de reset possible. |
| 🗺️ **Aventure & mini-jeux** | Bientôt : maps aventure et mini-jeux à installer en un clic. |
| 🛠️ **Mes serveurs** | Tous les serveurs : état, version, place disque, dernière sauvegarde, démarrer/arrêter, sauvegarder, réglages. |

**Plugins et mods** (page d'un serveur de survie) :

- **Logiciel** : Vanilla, Paper (plugins), Fabric ou NeoForge (mods), téléchargés depuis leurs sources
  officielles. Seuls ceux qui existent pour la version choisie sont proposés. Le monde est sauvegardé
  avant chaque changement.
- **Plugins / Mods / Datapacks / Pack de ressources / Modpacks** : recherche dans le catalogue
  [Modrinth](https://modrinth.com), filtrée sur la version et le logiciel du serveur. « Installer »
  prend la bonne version, vérifie le fichier (SHA-1) et ajoute les dépendances obligatoires, y compris
  celles que seul le fichier du mod déclare. Les mods qui ne servent qu'aux joueurs sont écartés.
  Activer/désactiver, retirer, mises à jour. Le pack de ressources est envoyé aux joueurs à la connexion.
- **Pack pour les joueurs** (serveurs à mods) : un `.mrpack` à importer dans Modrinth App ou Prism
  Launcher, pour avoir les mêmes mods que le serveur. Lunar Client ne charge pas de mods.
- **Fichiers de config** : éditeur des configs des plugins, des mods et de Paper, avec copie `.bak`.
- Serveurs moddés : Java exactement à la version prévue par Mojang (téléchargé si besoin).

**Sauvegardes** (⚙️ → Sauvegardes, ou bouton 💾 / touche <kbd>B</kbd> en survie) : archive ZIP du monde
et de la config, faite à chaud (écritures suspendues le temps de l'archive). Restaurer remplace le
monde actuel, qui est d'abord sauvegardé lui-même. « Nettoyer » un serveur de survie fait aussi une
sauvegarde avant. Elles sont rangées dans `backups/`, hors du dossier du serveur.

### Panel Speedrun

- **RESET** (<kbd>R</kbd>) — monde neuf, config conservée. C'est *le* bouton.
- **START** (<kbd>S</kbd>) / **STOP** (<kbd>X</kbd>)
- Console live (coloration, envoi de commandes, raccourcis `op`, `whitelist`, `difficulty`…)
- Chronomètre de run, joueurs connectés, temps de boot, nombre de resets
- Éditeur complet de `server.properties`, whitelist et OP (UUID récupérés chez Mojang)
- Plusieurs serveurs en parallèle, <kbd>1</kbd>…<kbd>9</kbd> pour basculer

Raccourcis : <kbd>R</kbd> reset · <kbd>S</kbd> start · <kbd>X</kbd> stop · <kbd>C</kbd> console ·
<kbd>N</kbd> nouveau serveur · <kbd>?</kbd> aide

### Mode Turbo — reset instantané

Sans Turbo, un reset prend ~7 s : tuer la JVM, effacer le monde, relancer.

Avec Turbo, le panel garde **un deuxième serveur déjà démarré** sur un monde neuf, et un proxy
écoute sur le port public (25565). Un reset bascule juste le proxy : **~1 ms**. Vous cliquez
« Se reconnecter » dans Minecraft et vous êtes dans un monde vierge. L'ancien serveur est recyclé
en fond et un nouveau remplaçant préchauffe (~10 s).

Coût : double RAM (deux JVM). Avec 16 Go, 4 Go par serveur passe. Le badge « ⚡ Remplaçant prêt »
indique quand le reset instantané est disponible.

> Le proxy impose `prevent-proxy-connections=false` (le serveur voit `127.0.0.1` comme IP
> client). Le panel s'en charge.

---

## Jouer à deux

**Toi** : `localhost`

**Ton pote** :

1. Donne-lui l'IP publique affichée 🌐 en haut du panel (avec `:port` si ce n'est pas 25565).
2. **Redirige le port** sur ta box (*NAT/PAT*, *Redirection de ports*, souvent `192.168.1.1`) :
   TCP 25565 externe → 25565 interne, vers ton PC.
3. **Pare-feu Windows** (invite de commandes admin) :
   ```
   netsh advfirewall firewall add rule name="Minecraft 25565" dir=in action=allow protocol=TCP localport=25565
   ```

**Si le panel tourne dans WSL2** : `localhost` marche depuis Windows, mais la box redirige vers
l'IP de Windows, pas celle de WSL. Le plus simple : activer le réseau en miroir dans
`%UserProfile%\.wslconfig` puis `wsl --shutdown` :

```ini
[wsl2]
networkingMode=mirrored
```

Sinon, lancer le panel directement sous Windows avec `PANEL.bat`.

Opérateur en CGNAT (pas d'IP publique dédiée) : passer par un tunnel type Playit.gg, ou un VPN
type ZeroTier / Radmin VPN / Tailscale.

**Ton pote n'a pas de compte Minecraft officiel ?** Active *Accepter les comptes crack* (à la
création, ou ⚙️ → Joueurs ; désactivé par défaut). Contrepartie : plus aucun pseudo n'est
vérifié. Quelqu'un qui a l'adresse peut entrer sous ton pseudo ou celui d'un OP, et la whitelist
ne l'arrête pas (elle se base sur le pseudo). Ne donne l'adresse qu'à des gens de confiance.
Les UUID de la whitelist et des OP sont convertis tout seuls au démarrage suivant.

---

## Réglages (bouton ⚙️)

- **Serveur** : nom, port, RAM, version, graine. Graine *aléatoire à chaque reset* (défaut) ou
  *fixe* pour rejouer une seed. Appliqué au prochain démarrage.
- **server.properties** : tous les réglages avec le bon contrôle (interrupteur, menu, nombre
  borné), recherche intégrée. `difficulty`, `gamemode`, `white-list` et `player-idle-timeout`
  s'appliquent en direct ; le reste au prochain reset ou redémarrage (en Turbo, le remplaçant
  est relancé pour en tenir compte). Les clés pilotées par le panel
  (`server-port`, `query.port`, `prevent-proxy-connections`, `level-seed`) sont verrouillées.
  Les clés inconnues (mods, versions futures) restent éditables en texte.
- **Joueurs** : whitelist, OP et comptes crack. Serveur allumé, passe par la console
  (`whitelist add`, `op`) ; éteint, le panel écrit les JSON. Si Mojang ne connaît pas le pseudo,
  UUID hors-ligne (ne marche qu'avec les comptes crack acceptés).

Réglages par défaut orientés speedrun : difficulté `hard`, `hardcore=true`, `spawn-protection=0`,
`sync-chunk-writes=false`, graine aléatoire. Hardcore se désactive à la création dans
*Options avancées*.

---

## Structure

```
panel.sh / PANEL.bat   lanceurs (Linux-WSL-macOS / Windows)
panel.json             config du panel (port, ouverture auto du navigateur)
mcpanel/               backend Python, bibliothèque standard uniquement
  __main__.py          point d'entrée (python -m mcpanel)
  http_api.py          API JSON + flux SSE + fichiers statiques
  manager.py           cycle de vie des serveurs, reset, mode Turbo
  instance.py          processus Java : console, états, diagnostics
  proxy.py             proxy TCP du mode Turbo
  deps.py              téléchargement Java (Temurin) et jar Mojang (vérifié SHA-1)
  props.py             schéma typé de server.properties
  players.py           whitelist / OP, résolution des UUID
  backups.py           sauvegardes ZIP à chaud, restauration, rotation
  software.py          Paper / Fabric / NeoForge : versions, téléchargement, installation
  content.py           Modrinth : recherche, installation, dépendances, modpacks, pack joueurs
  files.py             éditeur des fichiers de config
web/                   interface : index.html, app.css, js/ (un fichier par partie, sans build)
packaging/             construction de l'exe Windows (PyInstaller)
.github/workflows/     un tag vX.Y.Z construit, teste et publie l'exe dans les Releases
servers/<nom>/         un dossier par serveur (monde, config, logs)
  .slots/a  .slots/b   les deux serveurs du mode Turbo
.cache/jars/           jars Minecraft partagés entre serveurs
.runtime/              JRE portable si aucun Java compatible trouvé
.trash/                suppressions différées (renommage instantané, effacement en fond)
```

Versions : toutes les releases depuis la 1.2.5 (Mojang ne fournit pas de serveur avant). Pour
les vieilles versions, le panel s'adapte tout seul : Java 8, `difficulty`/`gamemode` écrits en
nombres avant la 1.14, correctif officiel Mojang contre Log4Shell de la 1.7 à la 1.18.0.

Java requis : 26.x → Java 25, 1.20.5+ → 21, 1.18+ → 17, 1.17 → 16, avant → Java 8 (pas plus
récent : certaines vieilles versions plantent). Le panel prend un Java installé
compatible, sinon télécharge un JRE portable dans `.runtime/` (sans droits admin).

---

## Prérequis

- Python 3.9+ (`PANEL.bat` propose de l'installer via `winget`)
- ~1 Go disque par monde, 4 Go RAM libres (8 Go en Turbo)

---

## En cas de pépin

| Symptôme | Solution |
|---|---|
| « Le port est déjà utilisé » | Un autre serveur occupe 25565. Arrête-le ou change de port dans ⚙️. |
| Le serveur s'arrête tout de suite | Lire la console du panel : l'erreur y est traduite. Le panel réessaie seul pour les pannes connues (Java trop ancien, jar corrompu, RAM refusée, EULA). |
| « Impossible de contacter les serveurs Mojang » | Pas de connexion. Les versions déjà dans `.cache/jars/` marchent hors ligne. |
| Ton pote ne se connecte pas | Port non redirigé, pare-feu, ou WSL2 sans réseau miroir. Voir [Jouer à deux](#jouer-à-deux). |
| Le panel ne s'ouvre pas | Port 8765 pris : le panel bascule sur le suivant, l'adresse est affichée dans le terminal. |
| « Connexion perdue » après un reset Turbo | Normal, c'est la bascule. « Se reconnecter ». |
| « Hôte non autorisé » ou « Requête venant d'un autre site refusée » | Le panel ne répond qu'à sa propre page, ouverte via `localhost`, une IP ou le nom du PC. Protection contre les sites web qui tenteraient de le piloter. |
