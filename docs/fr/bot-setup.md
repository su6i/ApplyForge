# Configuration du Bot Telegram — Version Française

Étapes initiales :
1. Créez un bot avec `@BotFather` et récupérez le jeton (token).
2. Configurez `TELEGRAM_BOT_TOKEN` dans votre fichier `.env`.
3. Définissez `TELEGRAM_CHAT_ID` (chat privé ou canal).

Démarrage du bot :

```bash
uv run main.py bot
```

Commandes courantes :
- `/apply <url> [--template altacv]` — Générer le CV et la lettre et recevoir les fichiers dans le chat.

Remarque : Pour que le bot fonctionne correctement, une connexion Internet, l'API OpenAI (si vous utilisez le LLM) et l'accès aux outils LaTeX sur la machine sont nécessaires.
