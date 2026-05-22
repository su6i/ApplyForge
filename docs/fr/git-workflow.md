# Flux de Travail Git — Version Française

Règles et processus recommandés :

- Utilisez la branche `main` pour le code validé.
- Créez une branche `feature/...` pour chaque nouvelle fonctionnalité.
- Avant de valider (commit), exécutez `compile.sh` et les tests locaux.
- Un hook de pre-commit est suggéré pour des vérifications rapides (formatage, lint, verify.py).

Étapes de fusion (merge) :
1. Ouvrir une Pull Request depuis la branche feature.
2. Vérifier le code et la documentation.
3. Fusionner après approbation.
