## Nouveautés

- **Textes plus propres** : « 1 serveur », « 2 serveurs », « 3 joueurs »… au lieu de « serveur(s) ».
- **Nouvelle icône** pour l'exe (Explorateur, barre des tâches, raccourcis) et pour l'onglet du navigateur.
- **Nouveau nom : MC Servers Panel** (avant : MC Speedrun Panel). Le panel ne sert plus seulement au speedrun : l'exe s'appelle maintenant `MCServersPanel.exe`.
- **Panel Aventure & mini-jeux** :
  - catalogue de maps parkour (les 11 maps de Hielke) installées en un clic, téléchargées depuis le site de l'auteur ;
  - import de ta propre map Java : fichier `.zip` glissé dans la page, ou lien direct ;
  - la version de Minecraft est lue dans la map et choisie toute seule ; blocs de commande, vol et mode aventure réglés ;
  - **Recommencer la map** en un clic (retour à l'état d'origine) ;
  - mini-jeux Modrinth (Manhunt, OneBlock, BedWars…) en datapacks ou en plugins.

**Mise à jour depuis `MCSpeedrunPanel.exe`** : pose `MCServersPanel.exe` dans le même dossier et supprime l'ancien. Le dossier `mcpanel-data` est repris tel quel (serveurs, mondes, sauvegardes).

## Installation (Windows)

1. Télécharge **MCServersPanel.exe** ci-dessous (rien d'autre à installer : Python est inclus, Java et Minecraft sont téléchargés tout seuls).
2. Range-le dans un dossier à lui (ex. `Documents\MC Servers Panel`), puis double-clic.
3. Le navigateur s'ouvre sur le panel. Laisse la fenêtre noire ouverte : la fermer arrête le panel et ses serveurs.

Tes mondes et réglages sont dans le dossier `mcpanel-data`, créé à côté de l'exe.

### Si Windows bloque le lancement

L'exe n'est pas signé numériquement (le certificat qui l'éviterait est payant chaque année) :

- **« Windows a protégé votre ordinateur »** (SmartScreen) : *Informations complémentaires* → *Exécuter quand même*.
- **Antivirus** : faux positif fréquent pour les programmes Python empaquetés. Restaure le fichier et ajoute une exception, ou signale le faux positif à ton antivirus.
- **« Contrôle intelligent des applications a bloqué… »** : Windows ne laisse aucun moyen de lancer un exe non signé dans ce mode. Utilise la version source : installe Python depuis le Microsoft Store, télécharge le code (*Source code (zip)* ci-dessous), puis dans le dossier : `py -m mcpanel`.

Linux / macOS : télécharge le code source et lance `./panel.sh`.
