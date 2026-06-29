<div align="center">
  <img src="assets/project_logo.jpg" width="350" alt="Logo ApplyForge">
  <h1>ApplyForge - Créateur Automatisé de CV et Lettres de Motivation</h1>

  <br>

  <p align="center" style="white-space: nowrap;">
    <img src="https://img.shields.io/badge/Version-0.1.0-blue.svg" alt="Version">&nbsp;<img src="https://img.shields.io/badge/Python-3.12+-yellow.svg" alt="Python">&nbsp;<img src="https://img.shields.io/badge/Licence-MIT-green.svg" alt="Licence">&nbsp;<a href="https://www.linkedin.com/in/su6i/"><img src="assets/linkedin_su6i.svg" height="20" alt="LinkedIn"></a>
  </p>
</div>

Ce dépôt contient l'outil de génération et d'envoi automatique de CV et de lettres de motivation à partir d'offres d'emploi.

## Installation des Dépendances

```bash
uv sync
```

## Configuration

- Créez un fichier `.env` à partir de `.env.example` et complétez les valeurs :
  - `OPENAI_API_KEY` — Votre clé API OpenAI
  - `TELEGRAM_BOT_TOKEN` — Jeton du bot Telegram (optionnel si vous n'utilisez pas le bot)
  - `TELEGRAM_CHAT_ID` — Identifiant de discussion pour les notifications

## Instructions Courantes

- Génération de test :

```bash
uv run main.py test
```

- Générer un CV et une lettre de motivation pour une offre d'emploi :

```bash
uv run main.py apply <JOB_URL>
```

- Lancer le bot Telegram (si configuré) :

```bash
uv run main.py bot
```

## Compilation LaTeX

Le script `compile.sh` trouve et compile tous les modèles ; nécessite d'avoir `pdflatex`/`xelatex` installé dans votre PATH.

## Emplacement de Sortie

Les versions générées sont enregistrées dans les dossiers `Applied/` et `output/` (les règles de nommage sont détaillées dans la documentation).

## Documentation Technique

Consultez la documentation technique et d'architecture dans le dossier `docs/`.
