# Modèles LaTeX — Version Française

Structure des modèles :

- `templates/<nom_du_modele>/` — Chaque modèle LaTeX se trouve dans son propre dossier.
- `templates/shared/personal_data.tex` et le fichier JSON associé : Les informations de contact et le profil sont centralisés pour être utilisés dans tous les modèles.

Intégration des informations dans les modèles :
- Les fichiers de CV importent les informations personnelles avec `\input{../shared/personal_data}`.

Compilation :
- Utilisez `compile.sh` pour localiser tous les modèles et les compiler.
- Utilisez `xelatex` pour les lettres de motivation (pour la gestion des polices) ; pour les CV, `pdflatex` est généralement suffisant.
