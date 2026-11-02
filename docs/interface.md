# Interface : le site et l'admin

Le site public et l'admin sont du HTML, du CSS et du JavaScript sans
framework, servis par le même serveur que l'API. Ils ne contiennent **aucune
règle du festival** : ils affichent ce que l'API renvoie et lui envoient les
demandes.

[← Retour au README](../README.md)

## Sommaire

- [Les fichiers](#les-fichiers)
- [Qui appelle quoi](#qui-appelle-quoi)
- [Le design](#le-design)
- [Les photos](#les-photos)
- [Téléphone et ordinateur](#téléphone-et-ordinateur)
- [Comment l'admin gère une erreur](#comment-ladmin-gère-une-erreur)

## Les fichiers

```
web/
├── public/
│   ├── index.html     l'accueil : image d'ouverture, « Live now », programme, artistes, lieux
│   ├── artist.html    la page d'un artiste (artist.html?slug=max-pellerin)
│   ├── app.js         tout le JavaScript du site
│   └── style.css      les styles, partagés avec l'admin
└── admin/
    ├── index.html     le planning et les formulaires
    ├── admin.js       tout le JavaScript de l'admin
    └── admin.css      ce qui est propre à l'admin
```

`api.py` les sert avec `StaticFiles` : `web/admin/` sur `/admin`, puis
`web/public/` sur `/`. L'ordre compte : `/` attrape tout, donc `/admin` est
monté avant.

## Qui appelle quoi

| Écran | Appels à l'API |
| --- | --- |
| Accueil | `GET /api/festival` (dates, jours), `GET /api/venues` (filtre et section « Venues »), `GET /api/artists` (section « Artists » et photos), `GET /api/now` (bandeau « Live now ») |
| Programme | `GET /api/programme?day=…&venue=…` à chaque changement de jour ou de lieu ; le filtre par type est fait dans le navigateur |
| Page artiste | `GET /api/artists/{slug}` (l'artiste et ses passages), `GET /api/artists` (photos des artistes liés) |
| Admin, chargement | `GET /api/venues`, `GET /api/artists`, `GET /api/programme` |
| Admin, actions | `POST /api/performances`, `PUT /api/performances/{id}`, `DELETE /api/performances/{id}`, `POST /api/performances/{id}/participants`, `POST /api/artists` |

Le contrat complet de ces routes est dans [API.md](../API.md).

### « Live now » et le paramètre `?at=`

Le bandeau appelle `/api/now`. Ajouté à l'adresse de la page, `?at=` est
transmis à l'API pour simuler un moment :

```
http://127.0.0.1:8000/?at=2027-06-11T21:00   →   GET /api/now?at=2027-06-11T21:00
```

Selon la réponse, le bandeau montre le spectacle en cours et le suivant, la
date d'ouverture (avant le festival) ou « The festival is over » (après).

## Le design

Inspiré des sites de festivals actuels (Festival d'Avignon, Sónar) : les
images d'abord, une typographie calme, beaucoup d'espace, très peu d'effets.

| Élément | Choix |
| --- | --- |
| Police | une seule, [Instrument Sans](https://fonts.google.com/specimen/Instrument+Sans) (400, 500, 600), chargée depuis Google Fonts |
| Couleurs | noir `#111111` sur blanc, gris pour le texte secondaire, une seule couleur d'accent (bleu `#2F3BFF`) réservée au point « Live now » et au survol des liens |
| Titres | grands mais en poids moyen, lettres resserrées (`letter-spacing: -0.04em`) |
| Boutons | en pilule ; noir pour l'action principale, contour gris pour les autres |
| Séparateurs | filets gris fins de 1 px, sans cartes ni ombres |

Toutes les couleurs sont des variables CSS au début de
[style.css](../web/public/style.css) (`--ink`, `--muted`, `--accent`…) :
changer une couleur partout, c'est changer une ligne.

## Les photos

Le projet n'a pas encore de photos. Chaque emplacement est un rectangle d'une
teinte douce, toujours la même pour un même nom, avec une légende
(« Photo · Max Pellerin »).

```js
function photoHtml(name, photoUrl, caption = true) {
  if (photoUrl) {
    return `<div class="photo"><img src="${photoUrl}" alt="" /></div>`;
  }
  // sinon : un rectangle teinté avec sa légende
}
```

Dès qu'un artiste a un `photo_url` (champ « Photo URL » du formulaire
« New artist » de l'admin), sa vraie photo remplace l'emplacement, partout :
programme, liste des artistes, page de l'artiste. Les lieux et l'image
d'ouverture attendent encore leurs photos.

## Téléphone et ordinateur

| Ordinateur | Téléphone |
| --- | --- |
| ![Programme sur ordinateur](images/programme.png) | ![Programme sur téléphone](images/phone-programme.png) |

Une seule feuille de styles ; en dessous de 820 px de large :

- le bouton « See the programme » de l'en-tête disparaît (le lien
  « Programme » reste) ;
- les titres passent de 64 à 40 px ;
- chaque ligne du programme passe sur deux colonnes, vignette à droite ;
- les filtres se partagent la largeur ;
- dans l'admin, les champs côte à côte passent l'un sous l'autre, et le
  tableau défile horizontalement.

Aucune page ne défile horizontalement à 375 px de large.

## Comment l'admin gère une erreur

`admin.js` n'essaie jamais de deviner si une demande est valide. Il envoie la
demande, et si le serveur refuse, il affiche la phrase reçue :

```js
async function callApi(method, url, body) {
  // … envoie la requête …
  const data = await response.json();
  if (!response.ok) {
    throw new Error(errorText(data));   // la phrase de l'API
  }
  return data;
}
```

`errorText` gère les deux formes de `detail` décrites dans API.md : une
phrase (erreur du festival) ou une liste de problèmes (corps de mauvaise
forme, refusé par FastAPI).

![Le message rouge affiche la phrase du serveur](images/admin-refused.png)

Une règle n'existe donc qu'à un seul endroit, dans les classes Python. Si une
règle change, l'admin n'a rien à modifier.
