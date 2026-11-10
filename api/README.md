# API de prédiction de la consommation d'énergie des bâtiments de Seattle

Étape 1 de la mise en production : la logique de l'API est définie avec **BentoML** et testée en local.

## Contenu du dossier

| Fichier | Rôle |
|---|---|
| `preprocessing.py` | Calcul des features (âge, log de la surface, ratios…). Partagé entre l'entraînement et l'API, pour que les features soient calculées exactement de la même façon. |
| `train_and_save.py` | Reprend le nettoyage du notebook, entraîne le Gradient Boosting optimisé et le sauvegarde dans le model store de BentoML (avec la liste des features dans `custom_objects`). |
| `schemas.py` | Validation des données envoyées à l'API avec **Pydantic**. |
| `service.py` | Le service BentoML et ses deux endpoints : `/predict` et `/predict_batch`. |
| `test_api.py` | 20 tests par requêtes HTTP : 6 cas valides, 14 cas incohérents qui doivent être refusés. |
| `bentofile.yaml` | Configuration pour construire le Bento (étape suivante : conteneurisation). |

## Lancer l'API en local

Toutes les commandes se lancent depuis le dossier `api/` (le CSV doit être dans le dossier parent).

```bash
pip install -r requirements.txt

# 1. Entraîner et sauvegarder le modèle (une seule fois)
python train_and_save.py

# 2. Démarrer l'API
bentoml serve service:EnergieBatiments
```

Interface **Swagger** : http://localhost:3000

```bash
# 3. Dans un second terminal : lancer les tests
python test_api.py
```

## Ce que l'utilisateur envoie

L'utilisateur ne connaît pas le preprocessing (log, one-hot, ratios). Il envoie donc les **caractéristiques brutes** d'un bâtiment, et l'API calcule les features elle-même.

```bash
curl -X POST http://localhost:3000/predict \
  -H "Content-Type: application/json" \
  -d '{"batiment": {
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
      }}'
```

Sous Windows (PowerShell), il est plus simple d'utiliser `python test_api.py` ou l'interface Swagger.

Réponse :

```json
{"consommation_kbtu": 6059576.0, "log10_consommation": 6.7824, "intervalle_kbtu": [3564457.0, 10301280.0]}
```

La consommation réelle de ce bâtiment est de 7 226 362 kBtu. L'intervalle correspond à l'erreur moyenne du modèle (facteur 1,7).

## Règles de validation (Pydantic)

Une requête qui ne respecte pas ces règles est refusée avec une erreur **400** qui indique le champ en cause.

| Champ | Règle |
|---|---|
| `primary_property_type` | Un des 19 types vus à l'entraînement (liste déroulante dans Swagger) |
| `neighborhood` | Un des 14 quartiers de Seattle (majuscules ou minuscules acceptées) |
| `year_built` | Entre 1900 et 2016 (les relevés datent de 2016) |
| `number_of_floors` | Entre 1 et 89 |
| `property_gfa_total` | Entre 1 000 et 10 000 000 sq ft |
| `property_gfa_parking` | ≥ 0 et **plus petite que la surface totale** |
| `largest_use_gfa` | Optionnel, > 0 (si absent : surface totale − parking) |
| `second_largest_use_gfa`, `third_largest_use_gfa` | Optionnels (0 par défaut), 2e usage ≤ 1er usage, 3e usage ≤ 2e usage |
| `latitude`, `longitude` | Dans les limites de Seattle |
| `has_natural_gas`, `has_steam` | Vrai / faux |
| Tout autre champ | Refusé (`extra="forbid"`), par exemple une consommation envoyée par erreur |

## Choix techniques

- **Pas de Runner** : on utilise `@bentoml.service` / `@bentoml.api`, la syntaxe actuelle de BentoML.
- **Encodage dans le modèle** : le one-hot est fait par un `OneHotEncoder` dans un `Pipeline` scikit-learn (au lieu de `pd.get_dummies`). Le modèle sauvegardé contient donc l'encodage.
- **Ordre des features** : la liste des features est sauvegardée avec le modèle (`custom_objects`) et réutilisée par l'API au moment de la prédiction.
- **Vérification au démarrage** : l'API vérifie que les catégories de `schemas.py` sont bien celles vues par le modèle.
- **Modèle final** : il est évalué sur le même découpage que le notebook (R² test 0,736, MAE 0,218), puis ré-entraîné sur les 1 503 bâtiments avant la sauvegarde.
- **Nombre de features** : le modèle utilise 12 features (10 numériques, 2 catégorielles), calculées à partir de 13 champs saisis par l'utilisateur. Les règles de validation couvrent tous les champs, donc on garde le modèle complet. Une version allégée (surface, usage, gaz, âge) reste possible si on veut simplifier l'API.
- **Limite** : le modèle n'a vu que des bâtiments construits avant 2016. C'est pour ça que l'API refuse les années plus récentes.
