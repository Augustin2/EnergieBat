"""
Écrit requirements-prod.txt avec les versions EXACTES installées sur ce PC.

Pourquoi ? Le modèle est sauvegardé avec la version de scikit-learn de ce PC.
L'image Docker doit utiliser exactement la même version, sinon le modèle peut
mal se charger ou donner des prédictions différentes.

À lancer avec le même Python que celui qui a servi à entraîner le modèle :
    python figer_versions.py
"""
from importlib.metadata import version

# Dépendances de PRODUCTION uniquement : ce qui est nécessaire pour faire tourner l'API.
# (requests, jupyter, matplotlib... sont des dépendances de développement : pas dans l'image)
PAQUETS_PROD = ["bentoml", "scikit-learn", "pandas", "numpy", "pydantic"]

lignes = [f"{paquet}=={version(paquet)}" for paquet in PAQUETS_PROD]

with open("requirements-prod.txt", "w", encoding="utf-8") as fichier:
    fichier.write("# Généré par figer_versions.py - dépendances de production (image Docker)\n")
    fichier.write("\n".join(lignes) + "\n")

print("requirements-prod.txt écrit :")
print("\n".join(lignes))
