"""La famille d'erreurs du festival.

Chaque type dit ce qui ne va pas ; l'API le traduit en code HTTP
(404, 409, 422, 500) et la ligne de commande en message.
"""


class FestivalError(Exception):
    """Erreur métier de base du festival."""


class FestivalNotFoundError(FestivalError):
    """Une ressource demandée n'existe pas (404)."""


class FestivalConflictError(FestivalError):
    """Une règle du festival empêche l'opération (409)."""


class FestivalValidationError(FestivalError):
    """Une valeur fournie est invalide (422)."""


class FestivalStorageError(FestivalError):
    """Le fichier de données ne peut pas être lu ou écrit (500)."""
