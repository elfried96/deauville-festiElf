# Développement

Travailler sur le code : les outils, les tests, et comment ajouter une
fonctionnalité sans rien casser.

[← Retour au README](../README.md)

## Sommaire

- [Installer l'environnement](#installer-lenvironnement)
- [Les outils](#les-outils)
- [Les tests](#les-tests)
- [Ajouter une fonctionnalité : un exemple complet](#ajouter-une-fonctionnalité--un-exemple-complet)
- [Avant de pousser](#avant-de-pousser)

## Installer l'environnement

Le projet utilise **uv uniquement** : les dépendances sont dans
`pyproject.toml` et `uv.lock`, jamais dans un `requirements.txt`.

```bash
uv sync                    # crée .venv et installe tout, le projet compris
uv add NOM                 # ajoute une dépendance
uv add --dev NOM           # ajoute un outil de développement
```

`uv sync` installe le package `deauville` en mode éditable : une
modification dans `src/deauville/` est prise en compte tout de suite, sans
réinstaller.

| Fichier | Rôle |
| --- | --- |
| `pyproject.toml` | le nom du projet, ses dépendances, la commande `deauville = "deauville.cli:main"`, la configuration de ruff et de pytest |
| `uv.lock` | les versions exactes installées (à commiter) |
| `.python-version` | Python 3.12 |

## Les outils

```bash
uv run pytest              # les 75 tests
uv run ruff check .        # le style (imports, noms, erreurs probables)
uv run ruff format .       # la mise en forme automatique
uv build                   # dist/deauville-0.1.0-py3-none-any.whl
```

Pour lancer le serveur pendant le développement, avec rechargement
automatique à chaque sauvegarde :

```bash
uv run uvicorn deauville.api:app --reload
```

## Les tests

| Fichier | Tests | Ce qu'il vérifie |
| --- | --- | --- |
| `tests/test_festival.py` | 20 | les règles, directement sur les objets (`Festival`, `SoloShow`, `Lineup`, `Workshop`) |
| `tests/test_api.py` | 30 | tout API.md par HTTP : chaque route, chaque filtre, chaque code d'erreur, le fichier de données |
| `tests/test_side.py`, `B3/side/`, `B5/side/` | 25 | les exemples du cours |

### Aucun test ne touche `data/festival.json`

Les tests de l'API construisent l'application sur un **stockage en
mémoire** :

```python
@pytest.fixture
def storage():
    return MemoryStorage(DATA)            # un petit festival de test

@pytest.fixture
def client(storage):
    return TestClient(create_app(storage))
```

`TestClient` envoie les requêtes à l'application directement, sans démarrer
de serveur. Les tests qui ont besoin d'un vrai fichier en écrivent une copie
dans `tmp_path`, un dossier temporaire neuf pour chaque test.

Après `uv run pytest`, `git status` ne doit montrer aucun changement dans
`data/`.

### Lancer une partie des tests

```bash
uv run pytest tests/test_api.py -v                   # un fichier
uv run pytest tests/test_api.py::test_delete_twice   # un seul test
uv run pytest -k "error" -v                          # ceux dont le nom contient « error »
uv run pytest -x                                     # s'arrêter au premier échec
uv run pytest --lf                                   # relancer seulement les échecs
```

## Ajouter une fonctionnalité : un exemple complet

Objectif : filtrer le programme par type, avec
`GET /api/programme?kind=solo`. On suit l'ordre des modules : d'abord la
règle dans l'objet, puis la route, puis le test.

### 1. Dans `Festival.programme()` (`festival.py`)

Un paramètre de plus, et une condition de plus dans le filtre. Un type
inconnu est une valeur invalide (422) :

```python
def programme(
    self,
    day: date | None = None,
    venue: str | None = None,
    kind: str | None = None,
) -> list[Performance]:
    """Les performances dans l'ordre du programme, filtrées si demandé."""
    if venue is not None:
        self.get_venue(venue)
    if kind is not None and kind not in PERFORMANCE_CLASSES:
        raise FestivalValidationError(f"Unknown kind '{kind}'.")

    return sorted(
        p
        for p in self._performances
        if (day is None or p.festival_day == day)
        and (venue is None or p.venue == venue)
        and (kind is None or p.kind == kind)
    )
```

(Importer `PERFORMANCE_CLASSES` depuis `.models` et
`FestivalValidationError` depuis `.errors`.)

### 2. Dans la route (`api.py`)

FastAPI lit le paramètre de l'adresse grâce à la signature :

```python
@app.get("/api/programme")
def get_programme(
    day: date | None = None,
    venue: str | None = None,
    kind: str | None = None,
) -> list[dict]:
    festival = open_festival()
    return [
        festival.performance_view(p)
        for p in festival.programme(day=day, venue=venue, kind=kind)
    ]
```

### 3. Un test (`tests/test_api.py`)

```python
def test_programme_kind_filter(client):
    workshops = client.get("/api/programme", params={"kind": "workshop"}).json()
    assert {p["kind"] for p in workshops} == {"workshop"}

    unknown = client.get("/api/programme", params={"kind": "concert"})
    assert unknown.status_code == 422
```

### 4. Vérifier, puis documenter

```bash
uv run pytest
uv run ruff check .
```

Puis ajouter le filtre à la ligne `GET /api/programme` d'[API.md](../API.md).
Le site pourrait ensuite passer `&kind=` à l'API au lieu de filtrer
lui-même dans `app.js`.

Le chemin est toujours le même : **la règle dans l'objet, la route ne fait
que transmettre, un test prouve le comportement.**

## Avant de pousser

```bash
uv run ruff format .
uv run ruff check .
uv run pytest
git status                 # data/festival.json ne doit pas avoir changé
```

Et de temps en temps, le test du clone neuf : cloner le dépôt dans un autre
dossier, `uv sync`, puis chaque commande du README.

```bash
git clone https://github.com/elfried96/deauville-festiElf.git /tmp/clone
cd /tmp/clone
uv sync
uv run pytest
uv run deauville programme 2027-06-11
```
