from datetime import datetime
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
    CheckConstraint,
    SmallInteger,
    DateTime,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class Genre(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)

    movies: Mapped[list["Movie"]] = relationship(
        secondary="movie_genres", back_populates="genres", passive_deletes=True
    )


class Star(Base):
    __tablename__ = "stars"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)

    movies: Mapped[list["Movie"]] = relationship(
        secondary="movie_stars", back_populates="stars", passive_deletes=True
    )


class Director(Base):
    __tablename__ = "directors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)

    movies: Mapped[list["Movie"]] = relationship(
        secondary="movie_directors", back_populates="directors", passive_deletes=True
    )


class Certification(Base):
    __tablename__ = "certifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)

    movies: Mapped[list["Movie"]] = relationship(
        back_populates="certification", passive_deletes="all"
    )


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
        secondary=movie_genres, back_populates="movies", passive_deletes=True
    )
    directors: Mapped[list[Director]] = relationship(
        secondary=movie_directors, back_populates="movies", passive_deletes=True
    )
    stars: Mapped[list[Star]] = relationship(
        secondary=movie_stars, back_populates="movies", passive_deletes=True
    )


class MovieReaction(Base):
    __tablename__ = "movie_reactions"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    is_like: Mapped[bool]


class MovieRating(Base):
    __tablename__ = "movie_ratings"
    __table_args__ = (CheckConstraint("score BETWEEN 1 AND 10", name="score_range"),)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    score: Mapped[int] = mapped_column(SmallInteger)


class MovieComment(Base):
    __tablename__ = "movie_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), index=True
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("movie_comments.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    replies: Mapped[list["MovieComment"]] = relationship(order_by="MovieComment.id")


class CommentLike(Base):
    __tablename__ = "comment_likes"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    comment_id: Mapped[int] = mapped_column(
        ForeignKey("movie_comments.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
