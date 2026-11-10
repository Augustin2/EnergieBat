"""
Fonctions de préparation des données, partagées entre :
  - l'entraînement (train_and_save.py)
  - l'inférence (service.py)

Ainsi on est sûr que les features sont calculées EXACTEMENT de la même façon
au moment de l'entraînement et au moment de la prédiction.
"""
import numpy as np
import pandas as pd

# Année des relevés : l'âge du bâtiment est calculé par rapport à 2016 (comme dans le notebook)
ANNEE_RELEVES = 2016

# Ordre des features vues par le modèle (doit rester identique entre entraînement et inférence)
FEATURES_NUMERIQUES = [
    "log_surface", "NumberofFloors", "Age", "surface_par_etage",
    "part_parking", "part_usage_principal", "Latitude", "Longitude",
    "a_du_gaz", "a_de_la_vapeur",
]
FEATURES_CATEGORIELLES = ["PrimaryPropertyType", "Neighborhood"]
FEATURES = FEATURES_NUMERIQUES + FEATURES_CATEGORIELLES


def creer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Crée les features du notebook à partir des colonnes "brutes" d'un bâtiment.

    Colonnes attendues dans df :
      PrimaryPropertyType, Neighborhood, YearBuilt, NumberofFloors,
      PropertyGFATotal, PropertyGFAParking, LargestPropertyUseTypeGFA,
      SecondLargestPropertyUseTypeGFA, ThirdLargestPropertyUseTypeGFA,
      Latitude, Longitude, a_du_gaz, a_de_la_vapeur
    """
    df = df.copy()

    # La surface des bâtiments = surface totale - parking (vérifié sur tout le jeu de données)
    surface_batiment = df["PropertyGFATotal"] - df["PropertyGFAParking"]

    df["Neighborhood"] = df["Neighborhood"].str.upper()
    df["Age"] = ANNEE_RELEVES - df["YearBuilt"]
    df["log_surface"] = np.log10(df["PropertyGFATotal"])
    df["surface_par_etage"] = surface_batiment / df["NumberofFloors"]
    df["part_parking"] = df["PropertyGFAParking"] / df["PropertyGFATotal"]

    # Si la surface de l'usage principal n'est pas connue, on prend la surface du bâtiment
    usage_principal = df["LargestPropertyUseTypeGFA"].fillna(surface_batiment)
    surface_usages = (usage_principal
                      + df["SecondLargestPropertyUseTypeGFA"].fillna(0)
                      + df["ThirdLargestPropertyUseTypeGFA"].fillna(0))
    df["part_usage_principal"] = usage_principal / surface_usages

    df["a_du_gaz"] = df["a_du_gaz"].astype(int)
    df["a_de_la_vapeur"] = df["a_de_la_vapeur"].astype(int)

    return df[FEATURES]
