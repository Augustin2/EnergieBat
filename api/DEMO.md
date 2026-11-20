# Procédure de démonstration (soutenance)

Toutes les commandes utilisent des **valeurs écrites en dur** (pas de `$env:` ni de `%...%`) : elles marchent aussi bien dans PowerShell que dans `cmd` ou dans le « Google Cloud SDK Shell ».

| Élément | Valeur |
|---|---|
| Projet GCP | `energiebat-2016` |
| Région | `europe-west1` |
| Image | `europe-west1-docker.pkg.dev/energiebat-2016/energie-repo/energie-batiments:v1` |
| Adresse de l'API | `https://energie-batiments-t34tkfwllq-ew.a.run.app` (elle reste la même si on redéploie le même service, dans le même projet et la même région) |

---

## A. La veille : vérifier que tout est prêt (10 min)

```
cd C:\Users\Admin\EnergieBat\api
docker images energie-batiments
gcloud config get-value project
```

- `docker images` doit afficher `energie-batiments   v1`. Sinon, reconstruire l'image (voir l'annexe 1).
- `gcloud config get-value project` doit afficher `energiebat-2016`. Sinon : `gcloud config set project energiebat-2016`

Tester l'image en local (terminal 1), puis lancer les tests (terminal 2) :
```
docker run --rm -p 3000:3000 energie-batiments:v1
```
```
python test_api.py
```
Résultat attendu : `20 / 20 tests réussis`. Ctrl+C dans le terminal 1 pour arrêter.

## B. 30 minutes avant la soutenance : redéployer sur le Cloud (5 min)

On ne déploie **pas** en direct devant le jury : c'est long et il peut y avoir un imprévu. On déploie avant, et on montre pendant la démo comment ça a été fait.

```
gcloud artifacts repositories create energie-repo --repository-format=docker --location=europe-west1
gcloud auth configure-docker europe-west1-docker.pkg.dev
docker tag energie-batiments:v1 europe-west1-docker.pkg.dev/energiebat-2016/energie-repo/energie-batiments:v1
docker push europe-west1-docker.pkg.dev/energiebat-2016/energie-repo/energie-batiments:v1
gcloud run deploy energie-batiments --image europe-west1-docker.pkg.dev/energiebat-2016/energie-repo/energie-batiments:v1 --region europe-west1 --port 3000 --memory 1Gi --cpu 1 --min-instances 1 --max-instances 1 --allow-unauthenticated
```

**`--min-instances 1`** (et non 0) : pendant la soutenance, une instance reste allumée, donc il n'y a pas d'attente au premier appel (« cold start »). Cela coûte quelques centimes de l'heure : il faut tout supprimer juste après (partie D).

Vérification :
```
python test_api.py https://energie-batiments-t34tkfwllq-ew.a.run.app
```
Résultat attendu : `20 / 20 tests réussis`.

**À préparer à l'écran :**
- un terminal PowerShell ouvert dans `C:\Users\Admin\EnergieBat\api` ;
- VS Code (ou un éditeur) avec `service.py`, `schemas.py` et `bentofile.yaml` ouverts ;
- le navigateur sur https://energie-batiments-t34tkfwllq-ew.a.run.app (Swagger), plus un onglet sur la console Cloud Run : https://console.cloud.google.com/run?project=energiebat-2016 ;
- ce fichier ouvert, pour copier-coller les JSON de la partie C.

## C. Pendant la soutenance : déroulé de la démo (environ 7 min)

### 1. Le code de l'API (2 min)

| Fichier | Ce qu'il faut montrer et dire |
|---|---|
| `service.py` | `@bentoml.service` / `@bentoml.api` (pas de Runner, concept archivé). Le modèle est chargé depuis le model store. L'utilisateur envoie des données brutes, et l'API calcule les features avec `preprocessing.py`, le même code qu'à l'entraînement. |
| `schemas.py` | La validation Pydantic : listes fermées pour l'usage et le quartier, plages de valeurs, règles de cohérence (parking < surface totale, 2e usage ≤ 1er usage), champs inconnus refusés. |
| `bentofile.yaml` | Les 4 éléments : le service, le code source (3 fichiers seulement, pour une image légère), le modèle, les dépendances de production avec les versions exactes. |

### 2. La chaîne de déploiement (1 min)

Montrer dans le terminal les commandes de la partie B (sans les relancer) et expliquer :

> `bentoml build` crée le Bento → `bentoml containerize` crée l'image Docker → `docker push` l'envoie dans Artifact Registry → `gcloud run deploy` la lance sur Cloud Run, qui lui donne une adresse HTTPS.

Montrer l'onglet de la console Cloud Run : le service `energie-batiments` est actif.

### 3. Démo dans Swagger sur le Cloud (3 min)

Dans le navigateur, sur l'adresse de l'API : **POST /predict** → **Try it out** → coller le JSON → **Execute**.

**Requête 1 : un bâtiment valide (hôtel du centre-ville)**
```json
{
  "batiment": {
    "primary_property_type": "Hotel",
    "neighborhood": "DOWNTOWN",
    "year_built": 1927,
    "number_of_floors": 12,
    "property_gfa_total": 88434,
    "property_gfa_parking": 0,
    "largest_use_gfa": 88434,
    "latitude": 47.6122,
    "longitude": -122.33799,
    "has_natural_gas": true,
    "has_steam": true
  }
}
```
Attendu : **200**, `consommation_kbtu` ≈ **6 059 576**. À dire : « La consommation réellement mesurée de ce bâtiment est de 7 226 362 kBtu. L'intervalle donné correspond à l'erreur moyenne du modèle, un facteur 1,7. »

**Requête 2 : le même bâtiment, mais en entrepôt.** Remplacer `"Hotel"` par `"Warehouse"`.
Attendu : **200**, ≈ **1 622 070** kBtu. À dire : « Même surface, usage différent : environ 4 fois moins. C'est cohérent avec la feature importance : après la surface, c'est l'usage qui compte le plus. »

(Variante possible avec `"Hospital"` : ≈ **8 080 225** kBtu.)

**Requête 3 : une donnée incohérente.** Remettre `"Hotel"` et remplacer `1927` par `2030`.
Attendu : **400**, avec le message `Input should be less than or equal to 2016`. À dire : « La validation Pydantic bloque les données incohérentes avant qu'elles n'arrivent au modèle, et dit précisément quel champ pose problème. »

**Requête 4 (si le temps le permet) : règle de cohérence entre deux champs.** Remettre `1927` et mettre `"property_gfa_parking": 100000`.
Attendu : **400**, `La surface de parking doit être plus petite que la surface totale.`

### 4. Les tests automatiques sur le Cloud (1 min)

```
python test_api.py https://energie-batiments-t34tkfwllq-ew.a.run.app
```
Attendu : `20 / 20 tests réussis`. À dire : « 6 cas valides et 14 cas incohérents, qui sont tous refusés. »

## D. Juste après la soutenance : tout supprimer

```
gcloud run services delete energie-batiments --region europe-west1
gcloud artifacts repositories delete energie-repo --location europe-west1
gcloud run services list --region europe-west1
gcloud artifacts repositories list --location europe-west1
```
Les deux dernières commandes doivent afficher `Listed 0 items.`

---

## Plan B : si le Cloud ne répond pas le jour J

Faire exactement la même démo **en local avec l'image Docker** : c'est la même image que celle déployée sur le Cloud.

```
docker run --rm -p 3000:3000 energie-batiments:v1
```
Puis Swagger sur http://localhost:3000, et `python test_api.py` dans un second terminal. Montrer ensuite les **captures d'écran** de Swagger et des tests faites sur le Cloud, comme preuve que le déploiement a fonctionné.

Plan C (sans Docker) : `python -m bentoml serve service:EnergieBatiments`, puis la même démo sur http://localhost:3000.

## Questions probables du jury

| Question | Éléments de réponse |
|---|---|
| Pourquoi Cloud Run ? | Service généraliste qui fait tourner une image Docker telle quelle et donne une adresse HTTPS. Pas besoin d'un service spécialisé ML (Vertex AI), qui demanderait d'adapter l'image. Avec 0 instance minimum, il ne coûte rien quand l'API n'est pas utilisée. |
| Pourquoi l'utilisateur n'envoie-t-il pas directement les features ? | Il ne connaît pas le preprocessing (log, one-hot, ratios). L'API calcule les features avec le même code qu'à l'entraînement, ce qui évite les erreurs et garantit le même ordre de colonnes. |
| Comment être sûr que le modèle se comporte pareil dans Docker ? | Les versions exactes (scikit-learn, pandas…) sont figées dans `requirements-prod.txt`, et les 20 tests passent en local, dans le conteneur et sur le Cloud avec les mêmes prédictions. |
| Pourquoi refuser les années après 2016 ? | Le modèle n'a vu que des bâtiments relevés en 2016 : au-delà, il sortirait de son domaine de validité. |
| Qu'est-ce que le « cold start » ? | Avec 0 instance minimum, le premier appel démarre le conteneur (quelques secondes). C'est pourquoi on met 1 instance minimum pendant une démo. |
| Comment faire évoluer le modèle ? | Ré-entraîner avec `train_and_save.py`, puis `bentoml build`, `containerize`, `push` et `deploy` avec une nouvelle étiquette (`v2`). Cloud Run garde les anciennes révisions, ce qui permet de revenir en arrière. |

---

## Annexe 1 : reconstruire l'image si elle n'existe plus

```
python train_and_save.py
python figer_versions.py
python -m bentoml build
python -m bentoml containerize energie_batiments:latest -t energie-batiments:v1
```
