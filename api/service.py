"""
Service BentoML : API de prédiction de la consommation d'énergie des bâtiments de Seattle.

On utilise la syntaxe actuelle de BentoML (@bentoml.service / @bentoml.api),
PAS les "Runners", qui sont un concept archivé.

Lancement en local (depuis le dossier api/) :
    bentoml serve service:EnergieBatiments
Puis ouvrir http://localhost:3000 pour l'interface Swagger.
"""
import bentoml
import numpy as np
import pandas as pd

from preprocessing import creer_features
from schemas import Batiment, Prediction, Quartier, TypeBatiment

NOM_MODELE = "energie_batiments_seattle:latest"

# Erreur moyenne du modèle : MAE de 0,22 en log10, soit un facteur 10**0.22 ≈ 1,7
FACTEUR_ERREUR = 1.7


def batiments_vers_dataframe(batiments: list[Batiment]) -> pd.DataFrame:
    """Transforme les objets Pydantic en DataFrame avec les noms de colonnes du jeu de données."""
    lignes = []
    for b in batiments:
        lignes.append({
            "PrimaryPropertyType": b.primary_property_type,
            "Neighborhood": b.neighborhood,
            "YearBuilt": b.year_built,
            "NumberofFloors": b.number_of_floors,
            "PropertyGFATotal": b.property_gfa_total,
            "PropertyGFAParking": b.property_gfa_parking,
            "LargestPropertyUseTypeGFA": b.largest_use_gfa,
            "SecondLargestPropertyUseTypeGFA": b.second_largest_use_gfa,
            "ThirdLargestPropertyUseTypeGFA": b.third_largest_use_gfa,
            "Latitude": b.latitude,
            "Longitude": b.longitude,
            "a_du_gaz": b.has_natural_gas,
            "a_de_la_vapeur": b.has_steam,
        })
    df = pd.DataFrame(lignes)
    # None -> NaN pour que fillna fonctionne dans creer_features
    df["LargestPropertyUseTypeGFA"] = df["LargestPropertyUseTypeGFA"].astype(float)
    return df


@bentoml.service(resources={"cpu": "1"}, traffic={"timeout": 10})
class EnergieBatiments:
    # Référence vers le modèle sauvegardé par train_and_save.py
    modele_ref = bentoml.models.BentoModel(NOM_MODELE)

    def __init__(self):
        self.modele = bentoml.sklearn.load_model(self.modele_ref)

        # Features sauvegardées avec le modèle (custom_objects) : on les réutilise à l'inférence
        infos = bentoml.models.get(NOM_MODELE).custom_objects
        self.features = infos["features"]

        # Sécurité : les catégories autorisées par l'API doivent être celles vues par le modèle
        categories = infos["categories"]
        assert sorted(TypeBatiment.__args__) == categories["PrimaryPropertyType"], \
            "Les types de bâtiments de schemas.py ne correspondent pas au modèle"
        assert sorted(Quartier.__args__) == categories["Neighborhood"], \
            "Les quartiers de schemas.py ne correspondent pas au modèle"

    def _predire(self, batiments: list[Batiment]) -> list[Prediction]:
        donnees = batiments_vers_dataframe(batiments)
        # Mêmes features, dans le même ordre, qu'à l'entraînement
        X = creer_features(donnees)[self.features]
        log_predictions = self.modele.predict(X)

        resultats = []
        for log_pred in log_predictions:
            conso = float(10 ** log_pred)
            resultats.append(Prediction(
                consommation_kbtu=round(conso),
                log10_consommation=round(float(log_pred), 4),
                intervalle_kbtu=(round(conso / FACTEUR_ERREUR), round(conso * FACTEUR_ERREUR)),
            ))
        return resultats

    @bentoml.api
    def predict(self, batiment: Batiment) -> Prediction:
        """Prédit la consommation d'énergie annuelle (kBtu) d'un bâtiment."""
        return self._predire([batiment])[0]

    @bentoml.api
    def predict_batch(self, batiments: list[Batiment]) -> list[Prediction]:
        """Prédit la consommation de plusieurs bâtiments en une seule requête."""
        if len(batiments) == 0:
            return []
        return self._predire(batiments)
