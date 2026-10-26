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

## Ce qu'IcueLite peut piloter

| Appareil | Liaison | Prise en charge |
|---|---|---|
| Vanguard Pro 96 Hall Effect | USB | prévue, protocole à capturer |
| K100 RGB OPX | USB | prévue |
| Ironclaw RGB | USB | prévue |
| Virtuoso RGB Wireless XT | dongle ou câble USB | prévue (rien en Bluetooth ni en jack) |
| iCUE LINK 5000T LX RGB | hub iCUE LINK | prévue |
| AX1600i | Corsair Link USB | prévue |
| Nautilus 360 RS ARGB | carte mère | éclairage seulement, via la carte mère |
| Vengeance DDR5 | carte mère (SMBus) | rien à piloter (version sans RGB) |
