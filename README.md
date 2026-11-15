# MC Servers Panel

Un panel web pour créer et gérer des serveurs Minecraft sur ton PC, sans rien configurer à la main.
Tu choisis un type de partie, le panel télécharge Java, Minecraft, Paper/Fabric/NeoForge, les plugins
et les mods, puis lance le serveur. Ton pote n'a plus qu'à se connecter.

- 💀 **Speedrun** : mondes hardcore jetables, monde neuf en un clic, reset instantané avec le mode Turbo.
- 🏡 **Survie entre potes** : un monde qui dure, avec plugins, mods, modpacks, packs de ressources et sauvegardes automatiques.
- 🗺️ **Aventure & mini-jeux** : maps parkour et aventure installées en un clic, ta propre map en ZIP, mini-jeux Modrinth.
- 🛠️ **Mes serveurs** : vue d'ensemble et maintenance de tous les serveurs.

Toutes les versions de Minecraft Java depuis la 1.2.5 · Windows, Linux, macOS, WSL · interface en français.

---

## Sommaire

1. [Installation et lancement](#installation-et-lancement)
2. [Ce qu'il faut installer, ce qui s'installe tout seul](#ce-quil-faut-installer-ce-qui-sinstalle-tout-seul)
3. [Les panels](#les-panels)
   - [Accueil](#accueil)
   - [💀 Speedrun](#-speedrun)
   - [🏡 Survie entre potes](#-survie-entre-potes)
   - [🗺️ Aventure & mini-jeux](#️-aventure--mini-jeux)
   - [🛠️ Mes serveurs](#️-mes-serveurs)
4. [Sauvegardes](#sauvegardes)
5. [Jouer à plusieurs](#jouer-à-plusieurs)
6. [Architecture](#architecture)
7. [Versions de Minecraft et de Java](#versions-de-minecraft-et-de-java)
8. [Sécurité](#sécurité)
9. [Construire et publier l'exe](#construire-et-publier-lexe)
10. [En cas de pépin](#en-cas-de-pépin)

---

## Installation et lancement

### Windows (recommandé) : l'exe

1. Télécharge **`MCServersPanel.exe`** dans les [Releases](https://github.com/Blumor/mc-servers-panel/releases/latest).
2. Range-le dans un dossier à lui (ex. `Documents\MC Servers Panel`), puis double-clic.
3. Le navigateur s'ouvre sur `http://localhost:8765/`.

Laisse le terminal ouvert : le fermer arrête le panel **et** tous ses serveurs. Relancer l'exe
alors qu'il tourne déjà rouvre juste l'onglet.

L'exe n'est pas signé numériquement (le certificat coûte cher chaque année) :

- **« Windows a protégé votre ordinateur »** (SmartScreen) : *Informations complémentaires* → *Exécuter quand même*.
- **Antivirus** : faux positif fréquent pour les programmes Python empaquetés. Restaurer le fichier et ajouter une exception.
- **« Contrôle intelligent des applications a bloqué… »** : ce mode refuse tout exe non signé. Passer par le code source (ci-dessous).

### Depuis le code source (Windows, Linux, macOS, WSL)

Il faut **Python 3.9 ou plus**, rien d'autre.

```bash
git clone https://github.com/Blumor/mc-servers-panel.git
cd mc-servers-panel
./panel.sh            # Linux / macOS / WSL
```

Sous Windows : double-clic sur **`PANEL.bat`** (il propose d'installer Python via `winget` s'il
manque), ou `py -m mcpanel` dans le dossier.

### Options de lancement

| Option | Effet |
|---|---|
| `--port 9000` | Port du panel (défaut 8765 ; s'il est pris, le panel prend le suivant). |
| `--no-browser` | N'ouvre pas le navigateur. |
| `--lan` | Panel accessible depuis les autres appareils du réseau local. **Sans mot de passe** : réseau de confiance uniquement. |
| `--host-info` | Affiche l'IP locale et quitte. |

Exemple : `./panel.sh --port 9000 --no-browser`, ou `MCServersPanel.exe --lan`.

---

## Ce qu'il faut installer, ce qui s'installe tout seul

**À installer toi-même**

| Quoi | Quand |
|---|---|
| Rien | Avec l'exe Windows (Python est inclus dedans). |
| Python 3.9+ | Seulement si tu lances depuis le code source. Aucune bibliothèque à ajouter : le panel n'utilise que la bibliothèque standard. |
| Minecraft Java (côté joueur) | Pour jouer, évidemment. Launcher officiel, Lunar Client, Prism, Modrinth App… |

**Téléchargé automatiquement par le panel**, au premier besoin, puis gardé en cache :

| Quoi | Source | Rangé dans |
|---|---|---|
| Java (JRE portable, sans droits admin) | Eclipse Temurin (Adoptium) | `.runtime/` |
| Jar serveur vanilla (vérifié SHA-1) | Mojang (piston-meta) | `.cache/jars/` |
| Paper (vérifié SHA-256) | PaperMC (API Fill v3) | `.cache/jars/` |
| Fabric (lanceur serveur) | Fabric Meta | `.cache/jars/` |
| NeoForge (installeur exécuté une fois par serveur) | Maven NeoForged | dossier du serveur |
| Plugins, mods, modpacks, packs, datapacks, mini-jeux (vérifiés SHA-1) | Modrinth | dossier du serveur |
| Maps du catalogue | Site de leur auteur (ex. hielkemaps.com) | dossier du serveur |
| Correctif Log4Shell (1.7 → 1.18.0) | Mojang | dossier du serveur |

Si un Java compatible est déjà installé sur le PC, le panel le réutilise (sauf pour les serveurs à
mods, qui ont besoin de la version exacte prévue par Mojang).

**Où sont tes données**

| Lancement | Dossier des données |
|---|---|
| Exe | `mcpanel-data\` à côté de l'exe (ou `%LOCALAPPDATA%\MC Servers Panel` si le dossier de l'exe est protégé, ex. Program Files) |
| Code source | Le dossier du projet |

Pour déplacer ou sauvegarder tout le panel : copier ce dossier.

**Matériel** : ~1 Go de disque par monde, 2 à 4 Go de RAM libre par serveur (le double en mode Turbo),
plus pour un modpack lourd.

---

## Les panels

### Accueil

« On joue à quoi ? » : quatre tuiles, une par panel, avec le nombre de serveurs de chaque type.
Chaque serveur appartient à un panel (speedrun, survie ou aventure), choisi à sa création. Navigation
par adresse : `#/speedrun`, `#/survie`, `#/aventure`, `#/serveurs`, `#/serveur/<id>/<catégorie>`. Les boutons
précédent/suivant du navigateur marchent.

---

### 💀 Speedrun

Pour le speedrun coop : quand l'un de vous meurt, un clic (ou <kbd>R</kbd>) et vous repartez sur un
monde neuf.

**Créer un serveur** : fenêtre rapide, version, RAM, Turbo, puis *Créer & démarrer*. Dans les
*Options avancées* : graine, hardcore, comptes crack…

**Cockpit**

- **RESET** (<kbd>R</kbd>) : monde neuf, config conservée. C'est *le* bouton.
- **START** (<kbd>S</kbd>) / **STOP** (<kbd>X</kbd>).
- Console live : coloration, envoi de commandes, raccourcis `op`, `whitelist`, `difficulty`…
- Chronomètre de run, joueurs connectés, temps de démarrage, nombre de resets.
- Plusieurs serveurs en parallèle, <kbd>1</kbd>…<kbd>9</kbd> pour passer de l'un à l'autre.

Raccourcis : <kbd>R</kbd> reset · <kbd>S</kbd> start · <kbd>X</kbd> stop · <kbd>C</kbd> console ·
<kbd>N</kbd> nouveau serveur · <kbd>?</kbd> aide

**Réglages par défaut** : difficulté `hard`, `hardcore=true`, `spawn-protection=0`,
`sync-chunk-writes=false`, graine aléatoire à chaque reset (ou fixe pour rejouer une seed).

**Réglages (⚙️)**

- **Serveur** : nom, port, RAM, version, graine. Appliqué au prochain démarrage.
- **server.properties** : tous les réglages avec le bon contrôle (interrupteur, menu, nombre borné),
  recherche intégrée. `difficulty`, `gamemode`, `white-list` et `player-idle-timeout` s'appliquent en
  direct, le reste au prochain reset. Les clés pilotées par le panel (`server-port`, `query.port`,
  `prevent-proxy-connections`, `level-seed`) sont verrouillées. Les clés inconnues restent éditables
  en texte.
- **Joueurs** : whitelist, OP, comptes crack.
- **Sauvegardes** : voir [Sauvegardes](#sauvegardes).

Les serveurs speedrun restent en vanilla : pas de plugins ni de mods.

#### Mode Turbo : reset instantané

Sans Turbo, un reset prend ~7 s : arrêter Java, effacer le monde, relancer.

Avec Turbo, le panel garde **un deuxième serveur déjà démarré** sur un monde neuf, et un proxy écoute
sur le port public (25565). Un reset bascule juste le proxy : **~1 ms**. Vous cliquez *Se
reconnecter* dans Minecraft et vous êtes dans un monde vierge. L'ancien serveur est recyclé en fond et
un nouveau remplaçant se prépare (~10 s). Le badge « ⚡ Remplaçant prêt » indique quand le reset
instantané est disponible.

Coût : double RAM (deux serveurs Java). Avec 16 Go, 4 Go par serveur passe. Le proxy impose
`prevent-proxy-connections=false` (le serveur voit `127.0.0.1` comme IP des joueurs) ; le panel s'en
charge.

---

### 🏡 Survie entre potes

Un monde qui dure, avec ou sans plugins et mods. Pas de reset ; sauvegarde automatique toutes les 6 h
par défaut.

**Créer un serveur** ouvre directement sa **page complète**, façon Aternos : en-tête avec état,
adresse à copier, *Démarrer* / *Arrêter* / *Sauvegarder*, et les catégories à gauche (une page
chacune). On règle tout, puis *Démarrer*.

| Catégorie | Contenu |
|---|---|
| 📊 **Tableau de bord** | État, joueurs connectés, console live, adresse à donner aux potes. |
| ⚙️ **Général** | Nom, version, port, RAM, difficulté, mode de jeu, joueurs max, sauvegarde auto (désactivée, 1 h, 3 h, 6 h, 24 h), MOTD, graine, hardcore, PvP, comptes crack. Zone sensible : effacer le monde (sauvegardé avant), supprimer le serveur. |
| 🧩 **Logiciel** | Vanilla, **Paper** (plugins), **Fabric** ou **NeoForge** (mods). Seuls ceux qui existent pour la version choisie sont proposés. Serveur arrêté ; le monde est sauvegardé avant chaque changement. |
| 🔌 **Plugins** / **Mods** | Recherche dans le catalogue [Modrinth](https://modrinth.com), filtrée sur la version et le logiciel du serveur. Le libellé suit le logiciel (Plugins en Paper, Mods en Fabric/NeoForge). |
| 🎁 **Modpacks** | Installe un modpack Modrinth (`.mrpack`) : bonne version de Minecraft, loader figé, mods serveur, fichiers de config. Les anciens mods sont retirés, le monde est sauvegardé avant. |
| 🎨 **Pack de ressources** | Pack envoyé aux joueurs à la connexion (lien + SHA-1 écrits dans `server.properties`), facultatif ou obligatoire. |
| 📦 **Datapacks** | Installés dans `world/datapacks/`, marchent même en vanilla. |
| 👥 **Joueurs** | Whitelist et OP (UUID récupérés chez Mojang). Serveur allumé, passe par la console ; éteint, le panel écrit les fichiers JSON. |
| 💾 **Sauvegardes** | Liste, créer, restaurer, supprimer, place disque. |
| 📝 **Fichiers de config** | Éditeur des configs des plugins, des mods et de Paper (`bukkit.yml`, `spigot.yml`, `config/`, `plugins/`…). L'ancienne version est gardée en `.bak`. |
| 🧪 **Avancé** | Tout `server.properties`, avec le même éditeur typé que le speedrun. |

**Ce que fait « Installer »** (plugins, mods, packs) :

1. prend le fichier compatible avec la version et le logiciel du serveur ;
2. vérifie son empreinte SHA-1 ;
3. ajoute les dépendances obligatoires, y compris celles que seul le fichier du mod déclare (ex. Fabric API) ;
4. refuse les mods qui ne servent qu'aux joueurs (Sodium, Iris…), signalés dès la recherche.

Ensuite : activer/désactiver (le fichier est renommé `.disabled`), retirer, voir les mises à jour.

**Pack pour les joueurs** (serveurs Fabric/NeoForge) : un bouton génère un `.mrpack` à importer dans
Modrinth App ou Prism Launcher, pour que tes potes aient exactement les mêmes mods que le serveur.
Lunar Client ne charge pas de mods : il marche avec Paper et vanilla, pas avec un serveur moddé.

**Réglages par défaut** : difficulté `normal`, hardcore désactivé, 10 joueurs max,
`sync-chunk-writes=true` (sûreté du monde avant la vitesse).

---

### 🗺️ Aventure & mini-jeux

Des maps toutes faites (parkour, aventure, puzzle) ou des mini-jeux, à lancer entre potes sans rien
configurer. La page du panel propose trois façons de commencer :

1. **Choisir une map du catalogue** → *Jouer*. Le panel crée le serveur, télécharge la map depuis le
   site de son auteur et l'installe. Au catalogue pour l'instant : les 11 maps parkour de
   [Hielke](https://hielkemaps.com/maps) (Parkour Spiral 1 à 3, Parkour Paradise 1 à 3, Volcano,
   Pyramid, Town, Egg, Dimension Parkour), jouables à plusieurs et à jour pour la dernière version.
2. **Importer ta map** : glisse le fichier `.zip` d'une map Java (ou clique pour le choisir), ou
   colle un lien direct `https://…/map.zip`. Liens vers Minecraft Maps, Planet Minecraft et CurseForge
   pour en trouver d'autres.
3. **Monde vide pour mini-jeux** : un monde normal en mode aventure, où ajouter des mini-jeux.

**Ce que fait l'installation d'une map**

- Trouve le monde dans l'archive (le dossier qui contient `level.dat`, même rangé dans un sous-dossier).
- **Lit dans `level.dat` la version de Minecraft de la map** et règle le serveur dessus : pas de map
  cassée par une version trop récente ou trop ancienne. Les maps d'avant la 1.9 n'indiquent pas leur
  version : le panel le signale, il faut alors choisir la version dans *Général*.
- Applique les réglages du type de map : mode aventure, blocs de commande et vol autorisés (la
  plupart des maps en ont besoin), pas de protection du spawn ; difficulté *peaceful* et PvP coupé
  pour le parkour et les puzzles, PvP activé pour les mini-jeux.
- Garde une **copie d'origine** de la map. Le monde précédent, s'il y en avait un, est sauvegardé avant.
- Refuse les maps Bedrock (`.mcworld`, incompatibles avec Java), les archives sans monde, et les
  archives piégées (chemins qui sortent du dossier, plus de 8 Go décompressés, 2 Go max à l'envoi).

**Page d'un serveur aventure** : la même page à catégories que la survie, avec deux catégories en plus
(et sans Modpacks) :

| Catégorie | Contenu |
|---|---|
| 🗺️ **Map** | Map installée (auteur, version d'origine, lien vers sa page), **🔁 Recommencer la map** (remet le monde comme au premier lancement, progression effacée), pack de ressources de la map s'il y en a un (à télécharger et donner aux joueurs), changer de map (catalogue ou import). |
| 🎯 **Mini-jeux** | Mini-jeux du catalogue [Modrinth](https://modrinth.com) (Manhunt, OneBlock, BedWars, Duels…). En Vanilla ce sont des datapacks ; en Paper, des plugins. |

Les autres catégories (Général, Logiciel, Plugins/Mods, Pack de ressources, Datapacks, Joueurs,
Sauvegardes, Fichiers de config, Avancé) marchent comme en survie. Sauvegarde automatique
désactivée par défaut : la copie d'origine suffit pour recommencer.

Les maps restent la propriété de leurs auteurs : le panel ne les redistribue pas, il les télécharge
depuis leur site quand tu les choisis, pour un usage personnel.

---

### 🛠️ Mes serveurs

Tous les serveurs, tous types confondus, sur une seule page. Pour chacun : état, type, version,
port, place disque (monde + sauvegardes), dernière sauvegarde. Actions directes : démarrer, arrêter,
sauvegarder, ouvrir les réglages ou sa page. Boutons *＋ Speedrun*, *＋ Survie* et *＋ Aventure*
pour en créer un.

---

## Sauvegardes

- **Contenu** : archive ZIP du monde et de la config, rangée dans `backups/<serveur>/`, hors du
  dossier du serveur.
- **À chaud** : serveur allumé, le panel suspend les écritures (`save-off`, `save-all`), archive,
  puis réactive (`save-on`). Personne n'est déconnecté.
- **Automatiques** (survie et aventure) : selon la fréquence choisie dans *Général* ; les 10 dernières sont
  gardées.
- **Avant chaque opération risquée** : changement de logiciel, de version, de modpack ou de map,
  effacement du monde, restauration. Ces sauvegardes-là ne sont jamais supprimées automatiquement.
- **Restaurer** remplace le monde actuel, qui est d'abord sauvegardé lui-même. Le serveur redémarre
  ensuite s'il tournait, même si la restauration échoue.
- Bouton 💾 ou touche <kbd>B</kbd> ; en speedrun, via ⚙️ → *Sauvegardes*.

---

## Jouer à plusieurs

**Toi** : dans Minecraft, *Multijoueur* → *Connexion directe* → `localhost` (ou `localhost:port`).

**Tes potes** :

1. Donne-leur l'adresse affichée 🌐 en haut du panel (clic = copie), avec `:port` si ce n'est pas 25565.
2. **Redirige le port** sur ta box (*NAT/PAT*, *Redirection de ports*, souvent `192.168.1.1`) :
   TCP 25565 externe → 25565 interne, vers ton PC. Un port par serveur allumé.
3. **Pare-feu Windows** (invite de commandes admin) :
   ```
   netsh advfirewall firewall add rule name="Minecraft 25565" dir=in action=allow protocol=TCP localport=25565
   ```

**Panel dans WSL2** : `localhost` marche depuis Windows, mais la box redirige vers l'IP de Windows,
pas celle de WSL. Activer le réseau en miroir dans `%UserProfile%\.wslconfig`, puis `wsl --shutdown` :

```ini
[wsl2]
networkingMode=mirrored
```

Ou lancer le panel directement sous Windows (exe ou `PANEL.bat`).

**Pas d'IP publique dédiée** (CGNAT) : tunnel type Playit.gg, ou VPN type ZeroTier / Radmin VPN /
Tailscale.

**Pote sans compte Minecraft officiel** : activer *Accepter les comptes crack* (désactivé par défaut).
Contrepartie : plus aucun pseudo n'est vérifié. Quelqu'un qui a l'adresse peut entrer sous ton pseudo
ou celui d'un OP, et la whitelist ne l'arrête pas. Ne donne l'adresse qu'à des gens de confiance. Les
UUID de la whitelist et des OP sont convertis tout seuls au démarrage suivant.

---

## Architecture

```
 Navigateur (web/)                         Panel Python (mcpanel/)                     Disque
┌──────────────────────┐   JSON (fetch)  ┌──────────────────────────────┐
│ index.html, app.css  │ ──────────────▶ │ http_api   API + fichiers web │
│ js/ (sans build)     │ ◀────────────── │ bus        événements SSE     │
│  core, views,        │   SSE (live)    │ jobs       tâches de fond     │
│  cockpit, content…   │                 │ manager    cycle de vie       │──▶ servers/<id>/
└──────────────────────┘                 │ instance   processus Java ────┼──▶ java -jar …
                                         │ proxy      bascule Turbo      │
 Minecraft (joueurs) ──── TCP 25565 ───▶ │ deps / software / content     │──▶ .cache/ .runtime/
                                         │ backups / players / props     │──▶ backups/
                                         └──────────────────────────────┘
                                                      │ HTTPS
          Mojang · Adoptium · PaperMC · Fabric · NeoForged · Modrinth · sites des maps
```

**Principes**

- **Zéro dépendance** : backend en Python, bibliothèque standard uniquement ; interface en HTML/CSS/JS
  sans framework ni étape de build. Rien à `pip install`, rien à `npm install`.
- **Un seul processus** : le panel sert la page web, l'API, et pilote les serveurs Minecraft (des
  processus `java` enfants). Fermer le panel les arrête tous (sous Windows, un *Job Object* garantit
  qu'aucun Java ne reste orphelin).
- **Temps réel** : l'interface reçoit états, lignes de console, joueurs et progression des tâches par
  un flux SSE (`/api/events`), sans rafraîchir.
- **Tâches longues en fond** : téléchargements, installations, sauvegardes, resets passent par une
  file de tâches, une à la fois par serveur, avec progression affichée.

**Backend `mcpanel/`**

| Fichier | Rôle |
|---|---|
| `__main__.py` | Point d'entrée (`python -m mcpanel`), options, ouverture du navigateur, instance unique. |
| `config.py` | Chemins, version de l'app, tableau Java par version de Minecraft. |
| `http_api.py` | Serveur HTTP : API JSON, flux SSE, fichiers statiques, contrôles Host/Origin. |
| `bus.py` | Bus d'événements vers les navigateurs connectés (SSE). |
| `jobs.py` | File de tâches de fond, sérialisées par serveur, avec progression. |
| `manager.py` | Création, démarrage, arrêt, reset, Turbo, changement de version/logiciel, sauvegardes auto. |
| `instance.py` | Un processus Java : console, détection des états, diagnostics d'erreur traduits. |
| `proxy.py` | Proxy TCP du mode Turbo. |
| `deps.py` | Java (détection ou téléchargement Temurin), liste des versions et jars Mojang. |
| `software.py` | Paper / Fabric / NeoForge : versions disponibles, téléchargement, installation. |
| `content.py` | Modrinth : recherche, installation, dépendances, modpacks, pack pour les joueurs. |
| `maps.py` | Maps : catalogue, téléchargement et import ZIP, lecture de `level.dat`, installation, recommencer. |
| `files.py` | Éditeur des fichiers de config, avec garde-fous et `.bak`. |
| `props.py` | Schéma typé de `server.properties`, réglages par défaut par type de serveur. |
| `players.py` | Whitelist, OP, résolution des UUID (en ligne et hors ligne). |
| `backups.py` | Sauvegardes ZIP à chaud, restauration, rotation, place disque. |

**Interface `web/`** : `index.html` (toutes les vues), `app.css`, et `js/` en scripts classiques
qui partagent leurs fonctions : `core.js` (état, API, SSE), `views.js` (routes, accueil, Mes
serveurs, page d'un serveur), `cockpit.js` (panel speedrun), `create.js` (création), `settings.js` et
`forms.js` (réglages, éditeur typé), `content.js` (logiciel, Modrinth, mini-jeux, fichiers),
`maps.js` (panel aventure, catalogue, import, page Map), `app.js` (démarrage, raccourcis).

**Données**

```
panel.json               config du panel (port, ouverture auto du navigateur)
servers/<id>/            un dossier par serveur
  panel.json             réglages du panel pour ce serveur (type, version, logiciel, RAM…)
  server.properties      config Minecraft
  world/                 le monde
  plugins/ mods/ config/ contenu installé (survie, aventure)
  map-resources.zip      pack de ressources fourni par la map (aventure)
  .slots/a  .slots/b     les deux serveurs du mode Turbo (speedrun)
backups/<id>/            sauvegardes ZIP (dont la copie d'origine des maps)
.cache/jars/             jars Minecraft/Paper/Fabric partagés entre serveurs
.runtime/                Java portable téléchargé
.trash/                  suppressions différées (renommage instantané, effacement en fond)
.logs/                   journaux du panel
```

**Autres dossiers du dépôt** : `panel.sh` / `PANEL.bat` (lanceurs depuis le code source),
`packaging/` (construction de l'exe), `.github/workflows/` (publication automatique).

---

## Versions de Minecraft et de Java

Toutes les versions release depuis la **1.2.5** (Mojang ne fournit pas de serveur avant). Le panel
adapte la config tout seul : `difficulty`/`gamemode` écrits en nombres avant la 1.14, correctif
officiel Mojang contre Log4Shell de la 1.7 à la 1.18.0.

| Minecraft | Java |
|---|---|
| 26.x | 25 |
| 1.20.5 → 1.21.x | 21 |
| 1.18 → 1.20.4 | 17 |
| 1.17 | 16 |
| avant 1.17 | 8 (pas plus récent : certaines vieilles versions plantent) |

Logiciels disponibles selon la version : Paper sur la plupart des versions depuis la 1.8, Fabric
depuis la 1.14, NeoForge depuis la 1.20.2. Le panel ne propose que ceux qui existent pour la version
choisie.

---

## Sécurité

- Le panel n'écoute que sur ta machine par défaut. `--lan` l'ouvre au réseau local, **sans mot de
  passe**.
- Il ne répond qu'à sa propre page : les requêtes venant d'un autre site ou d'un nom d'hôte inconnu
  sont refusées (protection contre les sites qui tenteraient de piloter le panel, y compris par
  *DNS rebinding*).
- Les fichiers téléchargés sont vérifiés par empreinte (SHA-1 ou SHA-256) quand la source en fournit
  une (Mojang, Paper, Modrinth). Les archives (maps, modpacks, sauvegardes) sont contrôlées contre
  l'écriture hors du dossier prévu ; les maps sont limitées en taille et téléchargées en HTTPS uniquement.
- L'éditeur de config n'ouvre que des fichiers texte de config, dans des dossiers connus, 1 Mo max.

---

## Construire et publier l'exe

L'exe est construit par GitHub Actions, sur Windows, avec PyInstaller :

1. Mettre à jour `APP_VERSION` dans `mcpanel/config.py` (ex. `2.3.0`).
2. Commit, puis tag correspondant : `git tag v2.3.0 && git push origin v2.3.0`.
3. Le workflow `.github/workflows/release.yml` vérifie que le tag correspond à `APP_VERSION`,
   construit `MCServersPanel.exe`, le lance pour vérifier que le panel répond, puis publie la release
   avec `packaging/RELEASE_NOTES.md` comme description.

En local : `python packaging/build_exe.py` (nécessite `pip install pyinstaller`), résultat dans
`dist/`.

---

## En cas de pépin

| Symptôme | Solution |
|---|---|
| « Le port est déjà utilisé » | Un autre serveur occupe ce port. Arrête-le ou change de port (Général ou ⚙️). |
| Le serveur s'arrête tout de suite | Lire la console : l'erreur y est traduite. Le panel réessaie seul pour les pannes connues (Java trop ancien, jar corrompu, RAM refusée, EULA). |
| « Incompatible mods found » / dépendance manquante | Un mod ne va pas avec la version ou le loader. Le désactiver dans Plugins/Mods, ou installer la dépendance indiquée. |
| « Impossible de contacter les serveurs Mojang » | Pas de connexion. Les versions déjà dans `.cache/jars/` marchent hors ligne. |
| Ton pote ne se connecte pas | Port non redirigé, pare-feu, ou WSL2 sans réseau miroir. Voir [Jouer à plusieurs](#jouer-à-plusieurs). |
| « Aucun monde Minecraft dans cette archive » | Le ZIP ne contient pas de `level.dat` : ce n'est pas une map Java (ou c'est un ZIP de ZIP : décompresse-le d'abord). |
| Une map ne marche pas bien (blocs de commande inactifs, joueurs expulsés pour vol) | Vérifier dans *Avancé* que `enable-command-block` et `allow-flight` sont activés, et la version de Minecraft demandée par la map dans *Général*. |
| Ton pote est refusé sur un serveur moddé | Il lui faut les mêmes mods : *Pack pour les joueurs* à importer dans Modrinth App ou Prism. |
| Le panel ne s'ouvre pas | Port 8765 pris : le panel bascule sur le suivant, l'adresse est affichée dans la fenêtre noire. |
| « Connexion perdue » après un reset Turbo | Normal, c'est la bascule. *Se reconnecter*. |
| « Hôte non autorisé » ou « Requête venant d'un autre site refusée » | Ouvrir le panel via `localhost`, une IP ou le nom du PC. Voir [Sécurité](#sécurité). |
