# Mon Entre-Deux — Prototype V2

Application de démonstration avec **espace mairie authentifié**, **base de données SQLite centralisée**, **carte des signalements filtrable** et interface web responsive.

## Lancer localement

Python 3.10+ :

```bash
cd mon-entre-deux-v2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export ADMIN_PASSWORD='Remplacez-Par-Un-Secret-Tres-Long-2026!'
export SECRET_KEY='Remplacez-Par-Une-Cle-Aleatoire-De-32-Caracteres-Minimum'
python app.py
```

Ouvrir http://127.0.0.1:8080. Onglet **Mairie** : utilisateur `admin`, mot de passe `ADMIN_PASSWORD`. L'admin peut créer des comptes agents. Les citoyens peuvent envoyer des signalements sans compte. La base `mon_entre_deux.sqlite3` est créée automatiquement au premier lancement. **Conservez ADMIN_PASSWORD** : elle n'est utilisée que pour créer le compte initial.

Sur Windows, activer l'environnement avec `.venv\\Scripts\\activate` et définir les variables avec PowerShell `$env:ADMIN_PASSWORD='...'` et `$env:SECRET_KEY='...'`.

## Ce que couvre cette version

- API REST Flask : session, connexion/déconnexion, création et lecture des dossiers, affectation, statut, photos, création d'utilisateurs.
- Mots de passe hachés, cookies HttpOnly, protection CSRF basique, séparation des accès administrateur / responsable / agent.
- SQLite partagée entre navigateurs **connectés au même serveur** (pas de synchronisation entre installations distinctes).
- Carte Leaflet / OpenStreetMap filtrable par catégorie et statut ; géolocalisation navigateur et positionnement manuel.
- Photo optionnelle jusqu'à 1 Mo ; accessible aux agents authentifiés.

## Limites impératives avant ouverture publique

**Ne pas exposer directement cette version à Internet et ne pas collecter de données réelles.** Il manque notamment : serveur WSGI de production, HTTPS et reverse proxy, secret persistant correctement géré, protection anti-bruteforce et anti-spam/rate limiting, vérification/normalisation des photos, antivirus et stockage objet privé, sauvegardes et restauration testées, journal d'audit complet, validation des coordonnées dans le territoire, modération, workflow des compétences, tests de sécurité, gestion RGPD (information, durées, droits), RGAA, tests de charge et d'accessibilité. Les photos sont actuellement stockées dans SQLite en data URI : choix de prototype seulement. Pas de notification e-mail ni de suivi citoyen authentifié.

Pour un déploiement municipal, migrer vers PostgreSQL/PostGIS, stockage privé de médias, hébergement UE, comptes institutionnels et gestion des habilitations, observabilité, sauvegardes, audit et tests.
