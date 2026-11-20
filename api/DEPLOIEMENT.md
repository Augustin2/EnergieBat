# Étape 2 : déploiement de l'API sur Google Cloud (Cloud Run)

Plateforme choisie : **Google Cloud Platform (GCP)**, avec 300 € de crédits offerts à l'inscription.

Service utilisé : **Cloud Run**, un service « généraliste » qui fait tourner une image Docker et lui donne une adresse HTTPS. Pas besoin de service spécialisé ML (Vertex AI) : notre image BentoML contient déjà l'API. Avec `--min-instances 0`, Cloud Run s'arrête quand personne n'appelle l'API, donc le coût reste quasi nul pendant les tests.

Toutes les commandes sont écrites pour l'invite de commandes Windows (`cmd` ou Anaconda Prompt), une commande par ligne. On les lance depuis le dossier `api\`.

---

## 0. Prérequis (une seule fois)

1. **Docker Desktop** installé et **démarré** (icône de la baleine dans la barre des tâches). Vérification : `docker --version`
2. **Compte GCP** sur https://console.cloud.google.com, avec la facturation activée (nécessaire même avec les crédits gratuits).
3. **gcloud CLI** installé : https://cloud.google.com/sdk/docs/install. Vérification : `gcloud --version`

## 1. Construire le Bento et l'image Docker

```
python figer_versions.py
python -m bentoml build
python -m bentoml containerize energie_batiments:latest -t energie-batiments:v1
```

- `figer_versions.py` écrit `requirements-prod.txt` avec les versions **exactes** installées sur le PC. Ce sont celles qui ont servi à entraîner le modèle, et l'image Docker utilisera les mêmes.
- `bentoml build` assemble le Bento à partir de `bentofile.yaml` : le code, le modèle et les dépendances.
- `bentoml containerize` transforme le Bento en image Docker.

Si le modèle a été ré-entraîné entre-temps, relancer d'abord `python train_and_save.py`.

## 2. Tester l'image Docker en local

Terminal 1 :
```
docker run --rm -p 3000:3000 energie-batiments:v1
```
Terminal 2 :
```
python test_api.py
```
Résultat attendu : `20 / 20 tests réussis`. Arrêter ensuite le conteneur avec Ctrl+C dans le terminal 1.

## 3. Préparer le projet GCP

Remplacer `mon-projet-energie` par un identifiant unique de ton choix (minuscules, chiffres et tirets).

```
gcloud auth login
set PROJECT_ID=mon-projet-energie
set REGION=europe-west1
gcloud projects create %PROJECT_ID%
gcloud config set project %PROJECT_ID%
```

Relier le projet au compte de facturation, dans la console : *Facturation > Associer un compte de facturation*. Ensuite :

```
gcloud services enable run.googleapis.com artifactregistry.googleapis.com
```

Les variables `set` ne durent que le temps du terminal : si tu ouvres un nouveau terminal, refais les deux `set`.

## 4. Publier l'image dans Artifact Registry (le registre Docker de GCP)

```
gcloud artifacts repositories create energie-repo --repository-format=docker --location=%REGION%
gcloud auth configure-docker %REGION%-docker.pkg.dev
docker tag energie-batiments:v1 %REGION%-docker.pkg.dev/%PROJECT_ID%/energie-repo/energie-batiments:v1
docker push %REGION%-docker.pkg.dev/%PROJECT_ID%/energie-repo/energie-batiments:v1
```

## 5. Déployer sur Cloud Run

```
gcloud run deploy energie-batiments --image %REGION%-docker.pkg.dev/%PROJECT_ID%/energie-repo/energie-batiments:v1 --region %REGION% --port 3000 --memory 1Gi --cpu 1 --min-instances 0 --max-instances 1 --allow-unauthenticated
```

| Option | Pourquoi |
|---|---|
| `--port 3000` | BentoML écoute sur le port 3000 dans le conteneur |
| `--memory 1Gi` | De la marge pour charger pandas, scikit-learn et le modèle |
| `--min-instances 0` | Rien ne tourne (donc rien n'est facturé) quand l'API n'est pas appelée |
| `--max-instances 1` | Limite les coûts pendant les tests |
| `--allow-unauthenticated` | L'API est appelable sans compte Google (pratique pour les tests et Swagger) |

À la fin, gcloud affiche l'adresse : `Service URL: https://energie-batiments-xxxxx.europe-west1.run.app`

## 6. Tester l'API déployée

```
python test_api.py https://energie-batiments-xxxxx.europe-west1.run.app
```

Le premier appel peut prendre quelques secondes : c'est le démarrage du conteneur (« cold start »).

Swagger : ouvrir l'adresse du service dans le navigateur, puis faire le même test qu'en local (un cas valide → 200, `year_built: 2030` → 400). Garder des captures d'écran pour la soutenance.

## 7. Arrêter le déploiement (à faire dès que les tests sont terminés)

```
gcloud run services delete energie-batiments --region %REGION%
gcloud artifacts repositories delete energie-repo --location %REGION%
```

La 1re commande supprime l'API, la 2e supprime l'image stockée (le stockage est facturé, même s'il coûte peu). Pour être sûr que plus rien n'est facturé, on peut aussi supprimer le projet entier : `gcloud projects delete %PROJECT_ID%`.

---

## Problèmes fréquents

| Message | Solution |
|---|---|
| `error during connect` / `docker daemon is not running` | Démarrer Docker Desktop et attendre que la baleine soit verte |
| `'gcloud' n'est pas reconnu` | Fermer et rouvrir le terminal après l'installation de gcloud |
| `Billing account ... not found` / `FAILED_PRECONDITION` | Le projet n'est pas relié au compte de facturation (étape 3) |
| `denied: Permission ... artifactregistry` au `docker push` | Relancer `gcloud auth configure-docker %REGION%-docker.pkg.dev` |
| Cloud Run : `container failed to start and listen on the port` | Vérifier `--port 3000` ; lire les logs dans la console (Cloud Run > energie-batiments > Journaux) |
