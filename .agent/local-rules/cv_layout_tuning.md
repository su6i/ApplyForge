# Skill: CV Layout Fine-Tuning (AltaCV / IT French)

## Quand utiliser ce skill
Après chaque génération de CV, vérifier visuellement le PDF et appliquer ces corrections **manuellement sur le .tex** — ne jamais relancer le pipeline pour corriger la mise en page.

---

## 1. Vérification post-génération (checklist)

Après `pdflatex`, toujours vérifier avec `pdfinfo <file>.pdf | grep Pages`.

Ouvrir le PDF et contrôler :
- [ ] 1 seule page
- [ ] Pas de blanc excessif en bas de page (colonne gauche ET droite)
- [ ] Titres des postes en français (`role`, `degree`, `title`)
- [ ] Titres des certifications en français
- [ ] Titres des diplômes en français + établissements traduits
- [ ] Honors du DU présents (ligne `\textit{...}`)
- [ ] Honors du Master présents (5 items)
- [ ] `amirshirali.com` présent dans Coordonnées
- [ ] PostGIS absent de la section Compétences → Données
- [ ] Persan absent des Langues
- [ ] Certifications industrielles absentes (SIAE, PLC, ISO 9001, HSE)

---

## 2. Titres à toujours traduire en français

| Anglais (source) | Français (CV) |
|---|---|
| Network Engineer & Python Developer | Ingénieur Réseaux & Développeur Python |
| AI Research Intern -- LLMs & Multi-Agent Systems | Stagiaire Recherche IA -- LLMs & Systèmes Multi-Agents |
| Master's Degree in Computer Science (Bac+5) | Master en Informatique (Bac+5) |
| University Diploma (DU) in Big Data, Data Science and Risk Analysis with Python | Diplôme Universitaire (DU) en Big Data, Science des Données et Analyse du Risque avec Python |
| Faculty of Economics, University of Montpellier, France | Faculté d'Économie, Université de Montpellier, France |
| Faculty of Sciences, University of Montpellier, France | Faculté des Sciences, Université de Montpellier, France |

Certifications (toujours en français) :
- MCP → "Construire des applications IA à contexte riche avec Anthropic (2025)"
- Multi-Agent Systems with CrewAI → "Systèmes Multi-Agents avec CrewAI"
- Prompt Engineering for Developers → "Ingénierie de prompt pour développeurs"
- OnAcademy & University of Tehran → "OnAcademy & Université de Téhéran"
- Machine Learning Specialist Bootcamp (125h) → "Bootcamp Spécialiste en Machine Learning (125h)"

Honors Master (toujours 5 items, en français) :
```
Réseaux Avancés : 16,33/20 (1er/13) ; Web Avancé : 17,15/20 (2e/17) ; Java Avancé : 16/20 (2e/18) ; Systèmes (Linux \& Python) : 16,5/20 (3e/64) ; Structures de Données : 17,95/20
```

Honors DU (toujours présent) :
```
Modélisation économétrique \& ML sur 922\,000+ dossiers d'assurance ; analyse statistique, modélisation du risque, DataViz interactive (Streamlit)
```

---

## 3. Gestion de l'espace blanc (whitespace)

### Problème : espace blanc en bas d'une ou des deux colonnes

**Solution principale — augmenter `itemsep` dans les listes Experience :**

```latex
% Avant (par défaut pipeline)
\begin{itemize}[leftmargin=1.25em, itemsep=0pt, parsep=0pt]

% Après (pour remplir l'espace)
\begin{itemize}[leftmargin=1.25em, itemsep=3pt, parsep=0pt]
```

Valeurs testées :
- `itemsep=0pt` → défaut pipeline, souvent trop compact
- `itemsep=2pt` → léger remplissage
- `itemsep=3pt` → ✅ validé pour CC Vallée des Baux (June 2026)
- `itemsep=4pt` → risque de débordement sur 2 pages

Changer **uniquement** les `\begin{itemize}` dans la section EXPERIENCE (pas dans Projets ou ailleurs).

### Si itemsep=3pt ne suffit pas
Ajouter un 4e bullet au poste le plus pertinent pour l'offre (généralement NIOC pour les postes IT réseau). Ne pas dépasser 4 bullets par poste.

### Si ça déborde sur 2 pages
1. Retirer PostGIS de la section Données : `SQL (PostgreSQL, MySQL)` au lieu de `SQL (PostgreSQL, MySQL, PostGIS)`
2. Réduire la tech line d'un projet (supprimer 1-2 items)
3. Ne jamais toucher aux honors sans autorisation explicite

---

## 4. Structure des expériences validée

| Poste | Bullets | Ordre dans le CV |
|---|---|---|
| NIOC (Network Engineer) | 3-4 selon pertinence | 1er si poste réseau/infra, 2e si poste IA |
| toHero (AI Research Intern) | 3 | 1er si poste IA, 2e si poste réseau/infra |

**Règle** : le poste le plus pertinent pour l'offre passe en premier.

---

## 5. Ne jamais faire sans autorisation

- Supprimer des honors du Master ou du DU
- Changer le nombre de projets (toujours 2)
- Relancer le pipeline pour corriger la mise en page
- Modifier les technos d'un poste sans vérifier le contenu source
