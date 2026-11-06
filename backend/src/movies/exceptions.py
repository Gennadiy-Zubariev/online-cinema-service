class MoviesError(Exception):
    """Base class for movies domain errors."""


class EntityNotFoundError(MoviesError):
    """Raised when a catalog entity with the given id does not exist."""

    def __init__(self, entity: str):
        self.entity = entity
        super().__init__(f"{entity} not found")


class EntityAlreadyExistsError(MoviesError):
    """Raised when a catalog entity with the same unique value exists."""

    def __init__(self, entity: str):
        self.entity = entity
        super().__init__(f"{entity} already exists")


class EntityInUseError(MoviesError):

    def __init__(self, entity: str):
        self.entity = entity
        super().__init__(f"{entity} is in use")
