## Installation (Windows)

1. Télécharge **MCSpeedrunPanel.exe** ci-dessous (rien d'autre à installer : Python est inclus, Java et Minecraft sont téléchargés tout seuls).
2. Range-le dans un dossier à lui (ex. `Documents\MC Speedrun Panel`), puis double-clic.
3. Le navigateur s'ouvre sur le panel. Laisse la fenêtre noire ouverte : la fermer arrête le panel et ses serveurs.

Tes mondes et réglages sont dans le dossier `mcpanel-data`, créé à côté de l'exe.

### Si Windows bloque le lancement

L'exe n'est pas signé numériquement (le certificat qui l'éviterait est payant chaque année) :

- **« Windows a protégé votre ordinateur »** (SmartScreen) : *Informations complémentaires* → *Exécuter quand même*.
- **Antivirus** : faux positif fréquent pour les programmes Python empaquetés. Restaure le fichier et ajoute une exception, ou signale le faux positif à ton antivirus.
- **« Contrôle intelligent des applications a bloqué… »** : Windows ne laisse aucun moyen de lancer un exe non signé dans ce mode. Utilise la version source : installe Python depuis le Microsoft Store, télécharge le code (*Source code (zip)* ci-dessous), puis dans le dossier : `py -m mcpanel`.

Linux / macOS : télécharge le code source et lance `./panel.sh`.
