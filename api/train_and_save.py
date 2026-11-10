"""
Étape 1 - Entraîne le modèle final de la partie 1 et le sauvegarde dans le "model store" de BentoML.

On reprend exactement le nettoyage et le feature engineering du notebook, puis le
Gradient Boosting avec les meilleurs hyperparamètres trouvés par la GridSearch.

Différence avec le notebook : l'encodage one-hot est fait par un OneHotEncoder DANS
un Pipeline scikit-learn (et non plus par pd.get_dummies). Comme ça, le modèle sauvegardé
contient aussi l'encodage : l'utilisateur de l'API envoie "Hospital" et pas une colonne 0/1.

Lancement (depuis le dossier api/) :
    python train_and_save.py
"""
from pathlib import Path

import bentoml
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from preprocessing import FEATURES, FEATURES_CATEGORIELLES, FEATURES_NUMERIQUES, creer_features

CHEMIN_CSV = Path(__file__).resolve().parent.parent / "2016_Building_Energy_Benchmarking.csv"
NOM_MODELE = "energie_batiments_seattle"

# Meilleurs hyperparamètres trouvés par la GridSearch du notebook
MEILLEURS_PARAMS = {
    "n_estimators": 500,
    "learning_rate": 0.02,
    "max_depth": 3,
    "min_samples_leaf": 1,
    "subsample": 0.7,
}


def charger_et_nettoyer(chemin: Path) -> pd.DataFrame:
    """Même nettoyage que dans l'analyse exploratoire du notebook."""
    df = pd.read_csv(chemin)

    # Bâtiments non résidentiels uniquement
    df = df[~df["BuildingType"].str.contains("Multifamily")]
    df = df[~df["PrimaryPropertyType"].isin(["Low-Rise Multifamily", "Residence Hall"])]

    # Relevés fiables uniquement
    df = df[df["Outlier"].isna()]
    df = df[df["ComplianceStatus"] == "Compliant"]
    df = df[df["SiteEnergyUse(kBtu)"] > 0]
    df = df[df["NumberofFloors"] < 90]

    # Erreurs de saisie : 0 étage -> 1
    df = df.copy()
    df.loc[df["NumberofFloors"] == 0, "NumberofFloors"] = 1

    # Pas de 2e / 3e usage -> surface 0
    df["SecondLargestPropertyUseTypeGFA"] = df["SecondLargestPropertyUseTypeGFA"].fillna(0)
    df["ThirdLargestPropertyUseTypeGFA"] = df["ThirdLargestPropertyUseTypeGFA"].fillna(0)

    # Raccordement gaz / vapeur (oui/non seulement, jamais la quantité)
    df["a_du_gaz"] = (df["NaturalGas(kBtu)"] > 0).astype(int)
    df["a_de_la_vapeur"] = (df["SteamUse(kBtu)"] > 0).astype(int)

    # Retrait des relevés aberrants : consommation par m² incohérente avec le type de bâtiment
    log_eui = np.log10(df["SiteEUI(kBtu/sf)"])
    groupe = log_eui.groupby(df["PrimaryPropertyType"])
    mediane_type = groupe.transform("median")
    mad_type = groupe.transform(lambda s: (s - s.median()).abs().median())
    score = 0.6745 * (log_eui - mediane_type) / mad_type
    df = df[score.abs() <= 3.5]

    return df


def construire_pipeline() -> Pipeline:
    """Encodage one-hot des catégories + Gradient Boosting, dans un seul objet."""
    encodage = ColumnTransformer(
        transformers=[
            # handle_unknown="ignore" : sécurité si une catégorie inconnue arrivait quand même
            ("categories", OneHotEncoder(handle_unknown="ignore"), FEATURES_CATEGORIELLES),
            ("numeriques", "passthrough", FEATURES_NUMERIQUES),
        ]
    )
    modele = GradientBoostingRegressor(random_state=42, **MEILLEURS_PARAMS)
    return Pipeline([("encodage", encodage), ("modele", modele)])


def main():
    df = charger_et_nettoyer(CHEMIN_CSV)
    print("Nombre de bâtiments après nettoyage :", len(df))

    X = creer_features(df)
    y = np.log10(df["SiteEnergyUse(kBtu)"])

    # 1) Évaluation sur le même découpage que le notebook
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    pipeline = construire_pipeline()
    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)

    metriques = {
        "r2_test": round(r2_score(y_test, y_pred), 3),
        "mae_test_log10": round(mean_absolute_error(y_test, y_pred), 3),
        "rmse_test_log10": round(float(np.sqrt(mean_squared_error(y_test, y_pred))), 3),
    }
    print("Métriques sur le jeu de test :", metriques)

    # 2) Modèle final : on ré-entraîne sur TOUS les bâtiments avant la mise en production
    pipeline_final = construire_pipeline()
    pipeline_final.fit(X, y)

    # Catégories connues du modèle (utiles pour la validation des données envoyées à l'API)
    categories = {
        col: sorted(X[col].unique().tolist()) for col in FEATURES_CATEGORIELLES
    }

    # 3) Sauvegarde dans le model store de BentoML.
    # custom_objects : on sauvegarde AVEC le modèle la liste et l'ordre des features,
    # pour les réutiliser au moment de l'inférence.
    modele_sauve = bentoml.sklearn.save_model(
        NOM_MODELE,
        pipeline_final,
        signatures={"predict": {"batchable": True}},
        custom_objects={
            "features": FEATURES,
            "categories": categories,
        },
        metadata=metriques,
        labels={"projet": "seattle-energie", "cible": "log10(SiteEnergyUse_kBtu)"},
    )
    print("Modèle sauvegardé :", modele_sauve.tag)


if __name__ == "__main__":
    main()
