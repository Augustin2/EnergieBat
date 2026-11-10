"""
Tests de l'API en local, avec des requêtes HTTP.

1) Lancer l'API dans un premier terminal :
       bentoml serve service:EnergieBatiments
2) Lancer les tests dans un second terminal :
       python test_api.py
"""
import requests

URL = "http://localhost:3000"

# Un bâtiment valide (hôtel du centre-ville, consommation réelle mesurée : 7 226 362 kBtu)
BATIMENT_OK = {
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


def modifier(**changements):
    """Copie du bâtiment valide avec quelques champs modifiés."""
    batiment = dict(BATIMENT_OK)
    batiment.update(changements)
    return batiment


def appeler(endpoint, donnees):
    return requests.post(f"{URL}/{endpoint}", json=donnees, timeout=10)


nb_ok = 0
nb_total = 0


def verifier(nom, condition, detail=""):
    global nb_ok, nb_total
    nb_total += 1
    if condition:
        nb_ok += 1
        print(f"[OK]     {nom}")
    else:
        print(f"[ÉCHEC]  {nom} {detail}")


# ---------- 1. Requêtes valides ----------
r = appeler("predict", {"batiment": BATIMENT_OK})
verifier("Bâtiment valide -> 200", r.status_code == 200, r.text)
if r.status_code == 200:
    print("         Prédiction :", r.json())
    verifier("Prédiction positive", r.json()["consommation_kbtu"] > 0)

# Quartier en minuscules : accepté (converti en majuscules)
r = appeler("predict", {"batiment": modifier(neighborhood="downtown")})
verifier("Quartier en minuscules accepté", r.status_code == 200, r.text)

# Champs optionnels absents (surface du 1er usage, 2e et 3e usages)
optionnels = {k: v for k, v in BATIMENT_OK.items()
              if k not in ("largest_use_gfa", "second_largest_use_gfa", "third_largest_use_gfa")}
r = appeler("predict", {"batiment": optionnels})
verifier("Champs optionnels absents acceptés", r.status_code == 200, r.text)

# Un bâtiment plus grand doit consommer plus (test de bon sens)
petit = appeler("predict", {"batiment": modifier(property_gfa_total=20000, largest_use_gfa=20000)}).json()
grand = appeler("predict", {"batiment": modifier(property_gfa_total=500000, largest_use_gfa=500000)}).json()
verifier("Plus grand bâtiment -> plus grande consommation",
         grand["consommation_kbtu"] > petit["consommation_kbtu"])

# Endpoint batch
r = appeler("predict_batch", {"batiments": [BATIMENT_OK, modifier(primary_property_type="Warehouse")]})
verifier("Batch de 2 bâtiments -> 2 prédictions", r.status_code == 200 and len(r.json()) == 2, r.text)

# ---------- 2. Requêtes incohérentes : doivent être refusées (400) ----------
cas_invalides = {
    "Type de bâtiment inconnu": modifier(primary_property_type="Castle"),
    "Quartier inconnu": modifier(neighborhood="PARIS"),
    "Année de construction dans le futur": modifier(year_built=2030),
    "Année de construction trop ancienne": modifier(year_built=1500),
    "0 étage": modifier(number_of_floors=0),
    "Surface négative": modifier(property_gfa_total=-100),
    "Parking plus grand que le bâtiment": modifier(property_gfa_parking=100000),
    "2e usage plus grand que le 1er": modifier(second_largest_use_gfa=90000),
    "3e usage plus grand que le 2e": modifier(second_largest_use_gfa=1000, third_largest_use_gfa=5000),
    "Coordonnées hors de Seattle (Paris)": modifier(latitude=48.85, longitude=2.35),
    "Texte à la place d'un nombre": modifier(number_of_floors="douze"),
    "Booléen invalide": modifier(has_steam="peut-être"),
    "Champ inconnu (fuite de données)": modifier(SiteEnergyUse=123456),
}
for nom, batiment in cas_invalides.items():
    r = appeler("predict", {"batiment": batiment})
    verifier(f"Refusé : {nom}", r.status_code == 400, f"(code {r.status_code})")

champ_manquant = {k: v for k, v in BATIMENT_OK.items() if k != "property_gfa_total"}
r = appeler("predict", {"batiment": champ_manquant})
verifier("Refusé : champ obligatoire manquant", r.status_code == 400, f"(code {r.status_code})")

print(f"\n{nb_ok} / {nb_total} tests réussis")
