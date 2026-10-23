# Deauville Festival du Rire — le programme

Le programme du **Deauville Festival du Rire** (10-13 juin 2027) en Python :
des classes pour les lieux, les artistes et les performances, une ligne de
commande, et une API JSON (FastAPI) qui sert le site public et l'admin des
organisateurs. Toutes les règles du festival sont vérifiées au même endroit,
et chaque refus est un message clair.

Projet du cours de programmation orientée objet, ECE Paris 2026-2027. Les
fiches du cours sont dans `B1/` à `B5/` (voir [COURSE.md](COURSE.md)) ; le
contrat de l'API est [API.md](API.md).

## Installer

Il faut [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/elfried96/deauville-festiElf.git
cd deauville-festiElf
uv sync
```

## Lancer

### La ligne de commande

```bash
uv run deauville                              # résumé du festival
uv run deauville venues                       # les lieux et leurs places
uv run deauville programme 2027-06-11         # le programme d'une journée
uv run deauville artist max-pellerin          # les passages d'un artiste, avec son rôle
uv run deauville now 2027-06-11T21:00         # sur scène à ce moment, et la suite
uv run deauville stats                        # les questions de l'étape 01
uv run deauville add                          # ajouter un solo (questions posées)
uv run deauville cancel le-kiosque-2027-06-12-0100
```

Chaque commande accepte `--data FICHIER` pour travailler sur un autre fichier
de données que `data/festival.json`.

### Le serveur

```bash
uv run deauville serve                        # http://127.0.0.1:8000
uv run deauville serve --data copie.json --port 8001
```

- le site : <http://127.0.0.1:8000/>
- l'admin : <http://127.0.0.1:8000/admin/>
- la documentation interactive de l'API : <http://127.0.0.1:8000/docs>

### Les tests et les outils

```bash
uv run pytest -v          # tous les tests (ils ne touchent jamais data/festival.json)
uv run ruff check .       # le style
uv run ruff format .      # la mise en forme
uv build                  # dist/deauville-0.1.0-py3-none-any.whl
```

## Structure

```
src/deauville/
├── errors.py     la famille d'erreurs du festival
├── storage.py    Storage (interface), JSONStorage, MemoryStorage
├── models.py     Venue, Artist, Performance et ses trois sous-classes
├── festival.py   Festival : les collections et les règles ; load/save
├── api.py        create_app(storage) : les routes d'API.md, le site, l'admin
└── cli.py        main() : la commande `deauville`
tests/
├── test_festival.py   les règles, directement sur les objets
└── test_api.py        tout API.md par HTTP (TestClient), sans serveur
```

Chaque module ne dépend que de ceux du dessus de la liste : `errors` ne
dépend de rien, `api` et `cli` sont tout en bas et ne contiennent aucune
règle.

### Les classes, et pourquoi

- **`Venue`, `Artist`** (dataclasses) : des données simples. Le slug est une
  propriété calculée à partir du nom, il ne peut donc pas être faux. Deux
  artistes au même slug sont égaux (`Zoé Tanguy` = `zoe tanguy`).
- **`Performance`** (classe abstraite) : ce qui est commun à toutes les
  performances (horaires, `end`, `festival_day` — une journée finit à 06:00,
  l'ordre du programme, la vue JSON). Ses méthodes abstraites —
  `artist_slugs()`, `role_of()`, `summary()`, `kind_fields()` — obligent
  chaque type à dire ce qui lui est propre.
- **`SoloShow`, `Lineup`, `Workshop`** héritent de `Performance` et
  appellent `super().__init__()`. Chacune vérifie ses propres règles à la
  construction (âge 0-18 ; au moins deux numéros, sans doublon, animateur
  hors des numéros, durée minimale ; au moins une place). Grâce au
  polymorphisme, le reste du code n'écrit jamais `if kind == ...` : la table
  `PERFORMANCE_CLASSES` et `performance_from_data()` choisissent la classe,
  puis on appelle simplement `performance.summary()`,
  `performance.artist_slugs()`…
- **`Festival`** garde ses collections privées (`_venues`, `_artists`,
  `_performances`). On les lit par des propriétés qui renvoient une **copie**,
  et on les change seulement par des méthodes qui vérifient les règles :
  `add_artist`, `add_performance`, `replace_performance`,
  `cancel_performance`, `register_participant`. De même, les numéros d'un
  plateau et les participants d'un atelier ne changent pas de l'extérieur.
- **`Storage`** (interface abstraite `load()` / `save()`) : le festival ne
  sait pas où il est stocké. `JSONStorage` lit et écrit le fichier,
  `MemoryStorage` garde les données en mémoire pour les tests.

### Où vivent les règles

Dans les objets, jamais dans les routes ni dans la ligne de commande :

| Règle                                                        | Où                                   |
| ------------------------------------------------------------ | ------------------------------------ |
| durée de 1 à 360 minutes, titre non vide                     | `Performance.__init__`               |
| règles propres à un solo, un plateau, un atelier             | `__init__` de chaque sous-classe     |
| lieu et artistes connus, jour du festival, 30 min d'écart entre deux performances d'un même lieu ou d'un même artiste, pas deux fois le même id | `Festival.validate_performance` |
| un déplacement refusé ne change rien                         | `Festival.replace_performance`       |
| inscription : pas deux fois le même nom, pas au-delà des places, seulement un atelier | `Workshop.register` (et `Performance.register`, qui refuse) |
| un artiste n'existe qu'une fois                              | `Festival.add_artist`                |

L'API et la ligne de commande construisent les objets et appellent ces
méthodes : elles ne peuvent pas contourner les règles.

### Comment une erreur dit quelle règle

Toutes les erreurs du festival héritent de `FestivalError`. Le **type** dit
ce qui ne va pas, le **message** dit quelle règle, en une phrase :

| Exception                 | Sens                     | HTTP |
| ------------------------- | ------------------------ | ---- |
| `FestivalNotFoundError`   | lieu, artiste, performance inconnu | 404 |
| `FestivalConflictError`   | lieu ou artiste occupé, hors festival, atelier complet, déjà existant | 409 |
| `FestivalValidationError` | valeur invalide          | 422  |
| `FestivalStorageError`    | fichier illisible ou impossible à écrire | 500 |

Dans l'API, un seul gestionnaire (`@app.exception_handler(FestivalError)`)
traduit le type en code HTTP : les routes n'écrivent jamais `try`. La ligne
de commande attrape toute la famille avec `except FestivalError` et affiche
le message. Un corps ou un paramètre de mauvaise forme est refusé avant
par FastAPI et pydantic (422, avec une liste de problèmes).

### Une route, de l'URL à la règle

`POST /api/performances` avec un solo de Nora Lebrun au Kiosque à 11:30,
alors qu'elle y joue déjà à 11:00 :

1. FastAPI vérifie la forme du corps avec `PerformanceBody` (pydantic).
2. `create_performance` charge le festival depuis le stockage.
3. `performance_from_data()` choisit `SoloShow` dans `PERFORMANCE_CLASSES`
   et la construit : l'id `le-kiosque-2027-06-13-1130` est calculé.
4. `Festival.add_performance` → `validate_performance` trouve un
   chevauchement au même lieu et lève `FestivalConflictError("Le Kiosque is
   already booked for …")`.
5. Le gestionnaire d'erreurs répond `409 {"detail": "Le Kiosque is already
   booked for …"}`. Rien n'a été enregistré.

### Avec une base de données

Il suffirait d'écrire une nouvelle classe, par exemple `SQLiteStorage(Storage)`,
avec ses propres `load()` et `save()`, et de la choisir dans `cli.py` (une
option `--db`). `create_app(storage)` la reçoit comme les autres : aucune
classe du festival ni aucune route ne change. Pour une vraie base, on
voudrait ensuite ne pas tout recharger et tout réécrire à chaque requête,
mais lire et modifier une seule ligne : l'interface `Storage` grandirait
(`add_performance`, `delete_performance`…).

## Ce qui est fait, ce qui ne l'est pas

Fait (étapes 00 à 13) :

- toutes les commandes de la ligne de commande, avec `--data` et `--port` ;
- tout `API.md` : lecture, écriture (admin), erreurs ;
- le site et l'admin servis par le même serveur ;
- 75 tests (règles et API), `ruff` propre, annotations et docstrings,
  `uv build`.

Pas fait :

- l'extension SQLite ;
- `deauville add` n'ajoute que des solos (plateaux et ateliers passent par
  l'admin).

Limites connues :

- Le fichier de données et le dossier `web/` sont cherchés à côté du code
  (`uv sync` installe le projet en mode éditable, donc tout marche depuis le
  dépôt). Installée ailleurs avec la wheel, la commande a besoin de
  `--data`, et le site ne serait pas trouvé.
- Chaque requête recharge et réécrit tout le fichier, sans verrou : deux
  écritures exactement simultanées, la dernière gagne.
- `/api/now` sans `?at=` utilise l'heure de la machine, sans fuseau horaire.
