# Guide IcueLite

## Installer

1. Télécharge `IcueLite.exe` dans la dernière [version publiée](../../releases/latest).
2. Range-le où tu veux (par exemple `C:\Programmes\IcueLite\`) et double-clique dessus. Rien d'autre à installer.

Windows SmartScreen peut afficher « Windows a protégé votre ordinateur » au premier lancement, car l'exe n'est pas signé : clique sur **Informations complémentaires**, puis **Exécuter quand même**.

## Mises à jour

IcueLite regarde s'il existe une nouvelle version au démarrage puis toutes les 6 heures. Quand c'est le cas, un bandeau jaune apparaît : **Mettre à jour** télécharge la nouvelle version, remplace l'exe et relance l'appli toute seule. Le bouton **Rechercher une mise à jour** en bas à gauche fait la vérification à la demande.

## iCUE et IcueLite

Les deux logiciels parlent aux mêmes appareils : quitte iCUE (et ses services Corsair) avant d'utiliser IcueLite, sinon ils se marchent dessus.

## Diagnostic

Le bouton **Diagnostic** écrit `icuelite-diag.txt` sur le Bureau et l'ouvre. Il ne fait que lire : identifiants USB des appareils Corsair, carte mère, référence des barrettes et logiciels concurrents. Envoie ce fichier si un appareil n'est pas reconnu.

## Version script (sans exe)

Avec Python installé : `IcueLite.bat` ouvre l'appli, `diag.bat` lance le diagnostic. `build-exe.bat` fabrique l'exe toi-même si besoin.

## Réglages

Ouvre un appareil dans la colonne de gauche. Selon l'appareil :

- **Éclairage** : une couleur par zone (« Autre… » ouvre le sélecteur de couleur), « Éteint », ou « D'origine » pour que l'appareil reprenne son propre éclairage. Luminosité en dessous.
- **DPI** (souris) : jusqu'à 5 paliers, le palier coché est celui de départ ; le bouton DPI de la souris passe de l'un à l'autre.
- **Fréquence d'interrogation** : 125 à 1000 Hz (jusqu'à 8000 Hz sur les claviers qui le permettent).
- **Ventilation** (hub iCUE LINK) : « Automatique » laisse le hub suivre sa courbe, « Vitesse fixe » impose une vitesse (jamais sous 20 %). Les régimes et températures s'affichent en direct.

Les réglages sont mémorisés et réappliqués au prochain démarrage. En quittant IcueLite, les appareils reprennent leur fonctionnement autonome.

## Pour les testeurs

Si un réglage ne prend pas : quitte iCUE, essaie le réglage dans IcueLite, puis clique sur **Diagnostic** et envoie le fichier `icuelite-diag.txt` qui s'ouvre. Il contient les derniers échanges avec chaque appareil, ce qui permet de corriger le protocole à distance.

## Ce qu'IcueLite peut piloter

| Appareil | Liaison | Prise en charge |
|---|---|---|
| Ironclaw RGB | USB | éclairage (logo, molette, avant), DPI, fréquence |
| K100 RGB OPX | USB | éclairage uni et luminosité, fréquence (à vérifier) |
| Vanguard Pro 96 Hall Effect | USB | éclairage uni et luminosité, fréquence (à vérifier) ; Hall Effect, écran et molette à venir |
| iCUE LINK 5000T LX RGB | hub iCUE LINK | vitesse des ventilateurs, régimes, températures (à vérifier) ; éclairage à venir |
| Virtuoso RGB Wireless XT | dongle ou câble USB | à venir |
| AX1600i | Corsair Link USB | à venir |
| Nautilus 360 RS ARGB | carte mère | éclairage seulement, via la carte mère |
| Vengeance DDR5 | carte mère (SMBus) | rien à piloter (version sans RGB) |
