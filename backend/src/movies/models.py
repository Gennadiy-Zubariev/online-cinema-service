from decimal import Decimal
from uuid import uuid4, UUID

from sqlalchemy import (
    String,
    UniqueConstraint,
    Numeric,
    Text,
    Column,
    ForeignKey,
    Table,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class Genre(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)

    movies: Mapped[list["Movie"]] = relationship(
        secondary="movie_genres", back_populates="genres"
    )


class Star(Base):
    __tablename__ = "stars"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)

    movies: Mapped[list["Movie"]] = relationship(
        secondary="movie_stars", back_populates="stars"
    )


class Director(Base):
    __tablename__ = "directors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)

    movies: Mapped[list["Movie"]] = relationship(
        secondary="movie_directors", back_populates="directors"
    )


class Certification(Base):
    __tablename__ = "certifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)

    movies: Mapped[list["Movie"]] = relationship(back_populates="certification")


movie_genres = Table(
    "movie_genres",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "genre_id",
        ForeignKey("genres.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
)

movie_directors = Table(
    "movie_directors",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "director_id",
        ForeignKey("directors.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
)

movie_stars = Table(
    "movie_stars",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "star_id",
        ForeignKey("stars.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
)


class Movie(Base):
    __tablename__ = "movies"
    __table_args__ = (UniqueConstraint("name", "year", "time"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[UUID] = mapped_column(unique=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))
    year: Mapped[int]
    time: Mapped[int]  # duration in minutes
    imdb: Mapped[float]
    votes: Mapped[int]
    meta_score: Mapped[float | None]
    gross: Mapped[float | None]
    description: Mapped[str] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    certification_id: Mapped[int] = mapped_column(
        ForeignKey("certifications.id", ondelete="RESTRICT")
    )
    poster: Mapped[str | None] = mapped_column(String(255))

    certification: Mapped[Certification] = relationship(back_populates="movies")
    genres: Mapped[list[Genre]] = relationship(
        secondary=movie_genres, back_populates="movies"
    )
    directors: Mapped[list[Director]] = relationship(
        secondary=movie_directors, back_populates="movies"
    )
    stars: Mapped[list[Star]] = relationship(
        secondary=movie_stars, back_populates="movies"
    )
