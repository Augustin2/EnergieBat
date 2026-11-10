"""
Validation des données envoyées à l'API, avec Pydantic.

L'utilisateur de l'API ne connaît pas notre preprocessing (log, one-hot, ratios...).
Il envoie donc les caractéristiques "brutes" d'un bâtiment, telles qu'on les trouve
dans un relevé, et c'est l'API qui calcule les features.

Chaque champ a des règles pour refuser les valeurs incohérentes (HTTP 400 si invalide).
Les plages viennent du jeu de données d'entraînement (Seattle, relevés 2016).
"""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Catégories vues par le modèle pendant l'entraînement.
# Avec Literal, Pydantic refuse toute autre valeur, et Swagger affiche une liste déroulante.
TypeBatiment = Literal[
    "Distribution Center", "Hospital", "Hotel", "K-12 School", "Laboratory",
    "Large Office", "Medical Office", "Mixed Use Property", "Other",
    "Refrigerated Warehouse", "Restaurant", "Retail Store", "Self-Storage Facility",
    "Senior Care Community", "Small- and Mid-Sized Office",
    "Supermarket / Grocery Store", "University", "Warehouse", "Worship Facility",
]

Quartier = Literal[
    "BALLARD", "CENTRAL", "DELRIDGE", "DELRIDGE NEIGHBORHOODS", "DOWNTOWN", "EAST",
    "GREATER DUWAMISH", "LAKE UNION", "MAGNOLIA / QUEEN ANNE", "NORTH", "NORTHEAST",
    "NORTHWEST", "SOUTHEAST", "SOUTHWEST",
]

# Limites géographiques de Seattle (avec une petite marge autour des bâtiments du jeu de données)
LAT_MIN, LAT_MAX = 47.49, 47.74
LON_MIN, LON_MAX = -122.44, -122.22


class Batiment(BaseModel):
    """Caractéristiques structurelles d'un bâtiment non résidentiel de Seattle."""

    # extra="forbid" : on refuse les champs inconnus (ex : quelqu'un qui enverrait sa consommation)
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "primary_property_type": "Hotel",
                "neighborhood": "DOWNTOWN",
                "year_built": 1927,
                "number_of_floors": 12,
                "property_gfa_total": 88434,
                "property_gfa_parking": 0,
                "largest_use_gfa": 88434,
                "second_largest_use_gfa": 0,
                "third_largest_use_gfa": 0,
                "latitude": 47.6122,
                "longitude": -122.33799,
                "has_natural_gas": True,
                "has_steam": True,
            }
        },
    )

    # --- Usage et localisation ---
    primary_property_type: TypeBatiment = Field(description="Usage principal du bâtiment")
    neighborhood: Quartier = Field(description="Quartier de Seattle (majuscules ou minuscules)")
    latitude: float = Field(ge=LAT_MIN, le=LAT_MAX, description="Latitude (doit être dans Seattle)")
    longitude: float = Field(ge=LON_MIN, le=LON_MAX, description="Longitude (doit être dans Seattle)")

    # --- Construction ---
    # Les relevés datent de 2016 : le modèle ne connaît pas les bâtiments construits après
    year_built: int = Field(ge=1900, le=2016, description="Année de construction (1900 à 2016)")
    number_of_floors: int = Field(ge=1, le=89, description="Nombre d'étages (1 à 89)")

    # --- Surfaces (en pieds carrés, comme dans les relevés) ---
    property_gfa_total: float = Field(
        ge=1_000, le=10_000_000, description="Surface totale, parking compris (sq ft)"
    )
    property_gfa_parking: float = Field(ge=0, description="Surface de parking (sq ft)")
    largest_use_gfa: Optional[float] = Field(
        default=None, gt=0, description="Surface de l'usage principal (sq ft). Si absent : surface hors parking"
    )
    second_largest_use_gfa: float = Field(default=0, ge=0, description="Surface du 2e usage (0 si aucun)")
    third_largest_use_gfa: float = Field(default=0, ge=0, description="Surface du 3e usage (0 si aucun)")

    # --- Équipement (oui / non, jamais la quantité consommée) ---
    has_natural_gas: bool = Field(description="Le bâtiment est-il raccordé au gaz ?")
    has_steam: bool = Field(description="Le bâtiment est-il raccordé au réseau de vapeur ?")

    @field_validator("neighborhood", mode="before")
    @classmethod
    def quartier_en_majuscules(cls, valeur):
        # Dans les données, "North" et "NORTH" existent : on accepte les deux
        if isinstance(valeur, str):
            return valeur.strip().upper()
        return valeur

    @model_validator(mode="after")
    def verifier_coherence(self):
        """Règles qui portent sur plusieurs champs à la fois."""
        if self.property_gfa_parking >= self.property_gfa_total:
            raise ValueError("La surface de parking doit être plus petite que la surface totale.")

        principal = self.largest_use_gfa or (self.property_gfa_total - self.property_gfa_parking)
        if self.second_largest_use_gfa > principal:
            raise ValueError("La surface du 2e usage ne peut pas dépasser celle de l'usage principal.")
        if self.third_largest_use_gfa > self.second_largest_use_gfa:
            raise ValueError("La surface du 3e usage ne peut pas dépasser celle du 2e usage.")
        return self


class Prediction(BaseModel):
    """Réponse de l'API."""

    consommation_kbtu: float = Field(description="Consommation d'énergie prédite (kBtu / an)")
    log10_consommation: float = Field(description="Sortie brute du modèle (log10 de la consommation)")
    intervalle_kbtu: tuple[float, float] = Field(
        description="Ordre de grandeur : prédiction divisée / multipliée par 1,7 (erreur moyenne du modèle)"
    )
