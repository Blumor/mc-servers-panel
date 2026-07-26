# MC Speedrun Panel

Serveur Minecraft local, monté et réinitialisé en un bouton. Pensé pour le speedrun coop :
quand l'un de vous meurt, un clic (ou la touche <kbd>R</kbd>) et vous repartez sur un monde neuf.

Deux façons de s'en servir :

| | Pour qui | Comment |
|---|---|---|
| **Panel web** | Usage normal, tout en boutons | double-clic sur `PANEL.bat` |
| **`server.bat`** | Ligne de commande, scripts | `server.bat start`, `server.bat reset`… |

Rien à installer à la main : Java et le `.jar` du serveur sont téléchargés automatiquement.

---

## Démarrage rapide

1. Double-cliquez sur **`PANEL.bat`**.
   S'il manque Python, le script propose de l'installer (`winget`) et vous donne le lien.
2. Le navigateur s'ouvre sur `http://localhost:8765/`.
3. **Créer mon serveur** → choisissez la version, la RAM, activez le Turbo → **Créer & démarrer**.
4. Dans Minecraft : *Multijoueur* → *Connexion directe* → `localhost`.
5. Donnez à votre pote l'adresse affichée par `server.bat ip` (voir [Jouer à deux](#jouer-à-deux)).

---

## Le panel web

Trois gros boutons, et c'est tout.

- **RESET** (<kbd>R</kbd>) — monde neuf, config conservée. C'est *le* bouton.
- **START** (<kbd>S</kbd>) / **STOP** (<kbd>X</kbd>)
- Console live avec coloration, envoi de commandes, raccourcis (`op`, `whitelist`, `difficulty`…)
- Chronomètre de run, joueurs connectés, temps de boot, nombre de resets
- Éditeur complet de `server.properties` et gestion whitelist / OP — voir
  [Réglages du monde](#réglages-du-monde)
- Plusieurs serveurs en parallèle, <kbd>1</kbd>…<kbd>9</kbd> pour basculer

Raccourcis clavier : <kbd>R</kbd> reset · <kbd>S</kbd> start · <kbd>X</kbd> stop · <kbd>C</kbd> console ·
<kbd>N</kbd> nouveau serveur · <kbd>?</kbd> aide

### Mode Turbo — reset quasi instantané

Sans Turbo, un reset prend ~8 s : il faut tuer la JVM, effacer le monde, tout relancer.

Avec Turbo, le panel garde **un deuxième serveur déjà démarré** sur un monde neuf, et fait écouter
un proxy sur votre port public (25565). Un reset ne fait plus que basculer le proxy sur ce serveur
de secours : **1 à 3 millisecondes**, mesuré. Vous cliquez « Se reconnecter » dans Minecraft et vous
êtes dans un monde vierge. Pendant ce temps, l'ancien serveur est recyclé en fond et un nouveau
remplaçant préchauffe.

Coût : ça double la RAM utilisée (deux JVM). Avec 16 Go, 4 Go par serveur passe sans problème.
Le badge « ⚡ Remplaçant prêt » indique quand le reset instantané est disponible.

> Techniquement, le proxy impose `prevent-proxy-connections=false` dans `server.properties`
> (le serveur voit `127.0.0.1` comme IP client). Le panel s'en charge.

---

## `server.bat` — ligne de commande

```
server.bat panel        Ouvre le panel web (recommandé)
server.bat start        Démarre le serveur (commande par défaut)
server.bat stop         Arrête proprement le serveur de ce port
server.bat restart      Arrêt puis redémarrage
server.bat reset        Monde neuf, config conservée      <-- speedrun
server.bat clean        Supprime mondes, logs et caches
server.bat create       Génère eula / server.properties / whitelist manquants
server.bat status       État, version, Java, adresses
server.bat logs         Console en direct
server.bat ip           IP locale et publique + rappel pare-feu
server.bat install      Télécharge Java + le jar et prépare tout
server.bat jar 1.21.4   Télécharge une version précise
server.bat java         Vérifie / installe Java
server.bat config       Affiche la configuration
```

Configuration dans **`server.conf`** (créé au premier lancement) :

```ini
PORT=25565
RAM=4096
MCVERSION=1.21.4
SERVER_JAR=server.jar
DIFFICULTY=hard
MAXPLAYERS=8
```

### Ce qui a changé par rapport à la v1

- **`delete` ne vide plus tout le dossier.** L'ancienne version supprimait *tous* les fichiers sauf
  `server.bat` et `server.jar` — y compris vos sauvegardes ou notes posées là. `clean` ne touche
  maintenant qu'aux fichiers générés par Minecraft (mondes, logs, caches).
- **`stop` ne tue plus tous les Java de la machine.** L'ancienne version faisait
  `taskkill /F /IM javaw.exe`, ce qui fermait aussi votre client Minecraft. Le script identifie
  maintenant le PID qui écoute sur le port et n'arrête que celui-là.
  Il envoie d'abord un vrai Ctrl+C à la console du serveur pour déclencher la sauvegarde, et
  ne force qu'après 12 secondes sans réponse. **Pour un arrêt propre garanti, utilisez le panel** :
  lui pilote directement la console du serveur et lui envoie la commande `stop`. Un arrêt forcé
  ne corrompt pas le monde (Minecraft sauvegarde toutes les 5 minutes), mais fait perdre les
  dernières minutes de jeu.
- **Java et le jar se téléchargent tout seuls** : JRE portable Temurin dans `.runtime\`
  (aucun droit administrateur), jar officiel Mojang vérifié par SHA-1.
- **`reset`** ajouté : efface le monde sans toucher à la config, contrairement à `reboot`.
- Détection de la version de Java requise selon la version de Minecraft, flags JVM orientés
  démarrage rapide, attente réelle de l'ouverture du port au lieu d'une temporisation fixe.

---

## Jouer à deux

**Vous** : `localhost`

**Votre pote**, trois étapes :

1. `server.bat ip` affiche votre IP publique. C'est celle à lui donner, avec le port.
2. **Ouvrir le port** sur votre box (section *NAT/PAT* ou *Redirection de ports*, souvent sur
   `192.168.1.1`) : port interne et externe `25565`, protocole TCP, destination votre PC.
3. **Pare-feu Windows** — en invite de commandes administrateur :
   ```
   netsh advfirewall firewall add rule name="Minecraft 25565" dir=in action=allow protocol=TCP localport=25565
   ```

Si ça ne passe toujours pas, votre opérateur est peut-être en CGNAT (pas d'IP publique dédiée) :
passez par un tunnel type Playit.gg ou un VPN local type Radmin/ZeroTier.

---

## Réglages du monde

Le bouton ⚙️ ouvre trois onglets.

### Onglet « Serveur »

Ce que gère le panel et non Minecraft : nom, port, RAM, graine. La **graine** est soit
*aléatoire à chaque reset* (défaut, ce que vous voulez en speedrun), soit *fixe* si vous
rejouez la même seed. Ces réglages s'appliquent au prochain démarrage.

### Onglet « server.properties »

**Tous** les réglages du fichier, avec le bon type de contrôle : interrupteur pour les
booléens, menu pour les valeurs à choix, champ numérique borné pour les entiers. Chaque
ligne affiche le nom du réglage, sa clé exacte et une explication. Un champ de recherche
filtre la liste (tapez `distance`, `mob`, `pack`…).

Deux badges à surveiller :

- **Géré par le panel** — `server-port`, `query.port`, `prevent-proxy-connections` et
  `level-seed` sont pilotés ailleurs (onglet Serveur, mode Turbo). Affichés mais non éditables,
  pour éviter qu'un réglage manuel soit écrasé au démarrage suivant sans explication.
- **Redémarrage requis** — la valeur est écrite tout de suite mais Minecraft ne la lira qu'au
  prochain démarrage.

Quatre réglages s'appliquent **en direct** sur un serveur allumé, sans redémarrage, parce que
Minecraft a une commande console pour eux : `difficulty`, `gamemode`, `white-list` et
`player-idle-timeout`. Après enregistrement, le panel vous dit lesquels attendent un redémarrage.

Les clés que le panel ne connaît pas — ajoutées par un mod, un plugin ou une version plus
récente de Minecraft — apparaissent dans un groupe **Clés non standard**, éditables en texte.
Elles ne sont jamais supprimées à l'écriture.

### Onglet « Joueurs »

Whitelist et opérateurs, en chips avec la tête du joueur. Tapez un pseudo, Entrée, c'est ajouté.

Le panel récupère l'**UUID** du joueur chez Mojang — c'est ce que `whitelist.json` exige, et
c'est pour ça qu'éditer ce fichier à la main est pénible. Si le compte est introuvable (hors
ligne, pseudo inexistant), il calcule l'UUID hors-ligne avec le même algorithme que Minecraft
et vous prévient : cet UUID ne fonctionne que sur un serveur en `online-mode=false`.

Serveur allumé, les ajouts et retraits passent par la console (`whitelist add`, `op`…) et
prennent effet immédiatement — c'est Minecraft qui écrit ses fichiers, donc aucun risque de
désynchronisation. Serveur éteint, le panel écrit les JSON lui-même.

L'interrupteur **Whitelist activée** en haut de l'onglet bascule `white-list` en direct.

### À la création

Le formulaire de création a une section **Options avancées** repliée qui contient exactement
la même chose : whitelist, OP et l'éditeur complet de `server.properties`. Vous partez donc
d'un serveur déjà configuré au premier démarrage. Seuls les réglages que vous modifiez sont
envoyés, le reste garde les défauts du panel.

En ligne de commande, tout reste éditable à la main dans `server.properties`, `whitelist.json`
et `ops.json` ; un redémarrage est alors nécessaire.

---

## Structure des fichiers

```
PANEL.bat              lanceur du panel (Windows)
panel.sh               lanceur du panel (Linux / macOS / WSL)
server.bat             gestion en ligne de commande
server.conf            configuration de server.bat
mcpanel/               backend Python (aucune dépendance externe)
  props.py             schéma typé de server.properties (47 réglages documentés)
  players.py           whitelist / OP, résolution des UUID chez Mojang
web/index.html         interface du panel
servers/<nom>/         un dossier par serveur (monde, config, logs)
  .slots/a  .slots/b   les deux serveurs du mode Turbo
.cache/jars/           jars Minecraft téléchargés, partagés entre serveurs
.runtime/              JRE portable installé automatiquement
.trash/                suppressions différées (un reset renomme, puis efface en fond)
```

Le reset est rapide en partie grâce à `.trash/` : effacer un monde de plusieurs centaines de Mo
prend du temps, alors le dossier est *renommé* (instantané) et supprimé dans un thread de fond.

---

## Prérequis

- **Windows 10/11** (le panel tourne aussi sous Linux et macOS via `panel.sh`)
- **Python 3.9+** pour le panel — `PANEL.bat` propose de l'installer si besoin.
  `server.bat` seul n'en a pas besoin.
- Java : téléchargé automatiquement si absent.
- ~1 Go de disque par monde, 4 Go de RAM libres (8 Go pour le mode Turbo).

---

## En cas de pépin

| Symptôme | Cause et solution |
|---|---|
| « Le port est déjà utilisé » | Un serveur tourne déjà, ou une autre application occupe 25565. `server.bat status`, ou changez de port dans les réglages. |
| Le serveur s'arrête tout de suite | Regardez la console du panel : le message d'erreur y est traduit. Le panel réessaie tout seul pour les pannes connues (Java trop ancien, jar corrompu, RAM refusée, EULA). |
| « Impossible de contacter les serveurs Mojang » | Pas de connexion. Les versions déjà téléchargées dans `.cache/jars/` restent utilisables hors ligne. |
| Votre pote ne se connecte pas | Port non ouvert sur la box, ou pare-feu Windows. Voir [Jouer à deux](#jouer-à-deux). |
| Le panel ne s'ouvre pas | Le port 8765 est pris — le panel bascule tout seul sur le suivant, l'adresse exacte est affichée dans la fenêtre. |
| Après un reset en Turbo, Minecraft affiche « Connexion perdue » | Normal : c'est la bascule. Cliquez sur « Se reconnecter ». |

Le panel n'est accessible que depuis votre machine (`localhost`). Pour l'ouvrir depuis votre
téléphone sur le même réseau : `python -m mcpanel --lan` — il n'y a aucun mot de passe, donc
uniquement sur un réseau de confiance.
