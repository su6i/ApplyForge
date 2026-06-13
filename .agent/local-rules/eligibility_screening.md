# Règle : Critères d'éligibilité — Vérification obligatoire avant toute candidature

Avant de générer un CV, **extraire ces critères** et vérifier les bloquants.

---

## 1. Critères BLOQUANTS (arrêt immédiat, aucun CV généré)

| Critère | Signaux dans le texte | Raison |
|---|---|---|
| **Permis B obligatoire** | "permis b obligatoire", "permis b exigé", "permis b requis", "permis b indispensable", "permis de conduire obligatoire", "driving license required" | Candidat sans permis |
| **Fonctionnaire/titulaire requis** | "être fonctionnaire", "titulaire de la fonction publique", "réservé aux agents titulaires", "fonctionnaire de catégorie", "mutation", "détachement uniquement" | Candidat non-fonctionnaire |
| **Nationalité française obligatoire** | "nationalité française obligatoire", "réservé aux ressortissants français", "nationalité française exigée", "être de nationalité française" | Candidat de nationalité iranienne |
| **Habilitation Secret/Confidentiel Défense** | "habilitation secret défense", "habilitation confidentiel défense", "secret-défense", "accès à des informations classifiées SECRET" | Nécessite la nationalité française |
| **Expérience > 3 ans exigée** | "X ans d'expérience minimum" avec X > 3, "expérience confirmée de X ans exigée" | Candidat : ~3 ans réseau + 6 mois IA |

**Note :** "souhaité", "apprécié", "un plus" = PAS bloquant, continuer.

---

## 2. Critères À EXTRAIRE et AFFICHER (informationnel, pas bloquant)

Le pipeline doit toujours extraire et afficher ces champs pour que l'utilisateur puisse décider :

| Champ | Ce qu'on extrait |
|---|---|
| **Niveau de français** | Niveau exigé (B1, B2, C1, C2, bilingue, natif) |
| **Niveau d'anglais** | Niveau exigé |
| **Autre langue** | Langue + niveau si mentionné |
| **Niveau d'études** | Bac+2 / Bac+3 / Bac+5 / Doctorat |
| **Expérience** | Nombre d'années souhaitées ou exigées |
| **Type de contrat** | CDI / CDD / Stage / Alternance + durée |
| **Rémunération** | Grille indiciaire, salaire brut ou fourchette si mentionné |
| **Télétravail** | Oui / Non / Partiel (X jours/semaine) |
| **Déplacements** | Fréquents / Occasionnels / Non mentionné |
| **Astreintes / horaires décalés** | Nuit, week-end, horaires atypiques — **signal positif** : moins de concurrence française |
| **Temps de travail** | 100% / 80% / 50% etc. |
| **Date de clôture** | Date limite de candidature |
| **Habilitation souhaitée** | "souhaitée" ou "en mesure d'obtenir" (pas bloquant) |
| **Aptitude médicale spéciale** | Police, SNCF, pompiers — visite médicale imposée |
| **Technologies imposées** | Si l'offre exige une techno absente du profil (SAP, COBOL, etc.) |

---

## 3. Format de sortie attendu du scraper

Pour chaque offre, afficher un bloc de synthèse **avant** de lancer la génération du CV :

```
══════════════════════════════════════════
VÉRIFICATION ÉLIGIBILITÉ
══════════════════════════════════════════
🚫 Permis B          : [obligatoire ← BLOQUANT | souhaité | non mentionné]
🚫 Fonctionnaire     : [titulaire requis ← BLOQUANT | contractuel OK | non mentionné]
🚫 Nationalité       : [française obligatoire ← BLOQUANT | toutes | non mentionné]
🚫 Habilitation      : [Secret Défense ← BLOQUANT | souhaitée | non mentionnée]
⚠️  Expérience        : [X ans exigés | X ans souhaités | non mentionnée]
──────────────────────────────────────────
ℹ️  Contrat           : [CDI | CDD X mois | Stage | Alternance]
ℹ️  Temps de travail  : [100% | 80% | 50%]
ℹ️  Rémunération      : [grille X | fourchette X–Y€ | non mentionnée]
ℹ️  Télétravail       : [X jours/sem | non | non mentionné]
✅  Astreintes/nuit   : [mentionnées = signal positif (moins de concurrence) | non mentionnées]
ℹ️  Déplacements      : [fréquents | occasionnels | non mentionnés]
ℹ️  Niveau FR         : [B2 | C1 | bilingue | non mentionné]
ℹ️  Niveau EN         : [B2 | C1 | non mentionné]
ℹ️  Études min.       : [Bac+2 | Bac+5 | non mentionné]
ℹ️  Date clôture      : [JJ/MM/AAAA | non mentionnée]
ℹ️  Technologies imp. : [liste | aucune imposée]
──────────────────────────────────────────
🎯 FIT SCORE          : XX/100
   [≥70 → générer CV | 50-69 → décision utilisateur | <50 → déconseillé]
══════════════════════════════════════════
```

Si un critère 🚫 est BLOQUANT → arrêter et ne pas générer le CV.
Le fit score (`match_score`) est calculé par le LLM dans `content_tailor.py`.
Idéalement calculé avant la génération complète pour que l'utilisateur décide sans perdre de temps.

---

## 4. Intégration dans le pipeline

Ce check est implémenté dans `src/pipeline/service.py` (after scraping, before tailor).
Les signaux Permis B et habilitation Secret Défense sont déjà codés.
Les autres critères bloquants (fonctionnaire, nationalité) sont à ajouter.
