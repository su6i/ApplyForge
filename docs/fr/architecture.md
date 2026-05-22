# Architecture du Système — Version Française

Ce projet comprend plusieurs composants principaux :

- `src/pipeline/` — Le pipeline de traitement qui inclut l'extraction d'offres (`job_scraper`), la classification du rôle (`role_classifier`), la personnalisation du contenu (`content_tailor`) et la génération LaTeX/PDF (`latex_builder`).
- `src/bot/` — L'interface Telegram pour envoyer la commande `/apply` et archiver les résultats.
- `templates/` — Les modèles LaTeX incluant un dossier partagé `templates/shared/` pour les informations personnelles.
- `compile.sh` — Le script qui recherche et compile les modèles.

Flux de traitement général :
1. Réception de l'URL de l'offre → Extraction du texte de l'offre
2. Classification du rôle (AI / IT / PhD)
3. Personnalisation du contenu (compétences cibles, paragraphes pour le CV et la lettre)
4. Remplissage des modèles LaTeX et compilation
5. Sortie : Deux fichiers PDF (le CV et la lettre de motivation) sauvegardés dans `Applied/` et `output/`.
