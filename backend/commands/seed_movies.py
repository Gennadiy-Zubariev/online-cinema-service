"""Fill the dev database with demo movies (and posters, if the files exist).

Run from the repo root:
    docker compose exec web python -m commands.seed_movies

Safe to run again: existing movies (same name, year, time) are skipped,
reference entities are reused by name. A poster is uploaded only for a movie
that has none yet - so you can add files later and run the script again.

Posters: commands/seed_posters/<poster>.jpg (or .jpeg / .png / .webp),
where <poster> is the "poster" value of the movie below.
"""

from decimal import Decimal
from pathlib import Path
from typing import Any, TypeVar
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.accounts import models as _accounts_models  # noqa: F401 (User mapper)
from src.database.sync_session import SyncSessionLocal
from src.movies.models import Certification, Director, Genre, Movie, Star
from src.storage.client import ensure_bucket_exists, upload_file

POSTERS_DIR = Path(__file__).parent / "seed_posters"
POSTER_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

NamedModel = TypeVar("NamedModel", Genre, Star, Director, Certification)

MOVIES: list[dict[str, Any]] = [
    {
        "name": "The Shawshank Redemption",
        "poster": "shawshank-redemption",
        "year": 1994,
        "time": 142,
        "imdb": 9.3,
        "votes": 2343110,
        "meta_score": 80,
        "gross": 28.34,
        "price": "7.99",
        "certification": "R",
        "genres": ["Drama"],
        "directors": ["Frank Darabont"],
        "stars": ["Tim Robbins", "Morgan Freeman"],
        "description": "Банкір Енді Дюфрейн отримує довічний строк за вбивство, "
        "якого не скоював, і роками зберігає надію у в'язниці Шоушенк.",
    },
    {
        "name": "The Godfather",
        "poster": "godfather",
        "year": 1972,
        "time": 175,
        "imdb": 9.2,
        "votes": 1620367,
        "meta_score": 100,
        "gross": 134.97,
        "price": "7.99",
        "certification": "R",
        "genres": ["Crime", "Drama"],
        "directors": ["Francis Ford Coppola"],
        "stars": ["Marlon Brando", "Al Pacino"],
        "description": "Старіючий глава мафіозного клану Корлеоне передає "
        "владу молодшому синові, який ніколи не хотів сімейної справи.",
    },
    {
        "name": "The Dark Knight",
        "poster": "dark-knight",
        "year": 2008,
        "time": 152,
        "imdb": 9.0,
        "votes": 2303232,
        "meta_score": 84,
        "gross": 534.86,
        "price": "6.99",
        "certification": "PG-13",
        "genres": ["Action", "Crime", "Drama"],
        "directors": ["Christopher Nolan"],
        "stars": ["Christian Bale", "Heath Ledger"],
        "description": "Бетмен, комісар Гордон і прокурор Гарві Дент "
        "протистоять Джокеру, який хоче занурити Готем у хаос.",
    },
    {
        "name": "Pulp Fiction",
        "poster": "pulp-fiction",
        "year": 1994,
        "time": 154,
        "imdb": 8.9,
        "votes": 1826188,
        "meta_score": 94,
        "gross": 107.93,
        "price": "5.99",
        "certification": "R",
        "genres": ["Crime", "Drama"],
        "directors": ["Quentin Tarantino"],
        "stars": ["John Travolta", "Uma Thurman", "Samuel L. Jackson"],
        "description": "Кілька переплетених історій про гангстерів, боксера "
        "і пару грабіжників у Лос-Анджелесі.",
    },
    {
        "name": "The Lord of the Rings: The Return of the King",
        "poster": "lord-of-the-rings-return-of-the-king",
        "year": 2003,
        "time": 201,
        "imdb": 8.9,
        "votes": 1642758,
        "meta_score": 94,
        "gross": 377.85,
        "price": "8.99",
        "certification": "PG-13",
        "genres": ["Action", "Adventure", "Drama"],
        "directors": ["Peter Jackson"],
        "stars": ["Elijah Wood", "Viggo Mortensen"],
        "description": "Фродо і Сем наближаються до Мордору з Перснем, "
        "а Арагорн веде вільні народи на останню битву з Сауроном.",
    },
    {
        "name": "Forrest Gump",
        "poster": "forrest-gump",
        "year": 1994,
        "time": 142,
        "imdb": 8.8,
        "votes": 1809221,
        "meta_score": 82,
        "gross": 330.25,
        "price": "5.99",
        "certification": "PG-13",
        "genres": ["Drama", "Romance"],
        "directors": ["Robert Zemeckis"],
        "stars": ["Tom Hanks", "Robin Wright"],
        "description": "Простодушний Форрест Гамп випадково стає учасником "
        "ключових подій історії США, не забуваючи про своє кохання.",
    },
    {
        "name": "Inception",
        "poster": "inception",
        "year": 2010,
        "time": 148,
        "imdb": 8.8,
        "votes": 2067042,
        "meta_score": 74,
        "gross": 292.58,
        "price": "6.99",
        "certification": "PG-13",
        "genres": ["Action", "Adventure", "Sci-Fi"],
        "directors": ["Christopher Nolan"],
        "stars": ["Leonardo DiCaprio", "Joseph Gordon-Levitt"],
        "description": "Злодій, що краде секрети зі снів, отримує зворотне "
        "завдання — непомітно вкласти ідею у свідомість людини.",
    },
    {
        "name": "Fight Club",
        "poster": "fight-club",
        "year": 1999,
        "time": 139,
        "imdb": 8.8,
        "votes": 1854740,
        "meta_score": 66,
        "gross": 37.03,
        "price": "4.99",
        "certification": "R",
        "genres": ["Drama"],
        "directors": ["David Fincher"],
        "stars": ["Brad Pitt", "Edward Norton"],
        "description": "Офісний працівник, що страждає від безсоння, разом "
        "із харизматичним продавцем мила засновує підпільний бійцівський клуб.",
    },
    {
        "name": "The Matrix",
        "poster": "matrix",
        "year": 1999,
        "time": 136,
        "imdb": 8.7,
        "votes": 1676426,
        "meta_score": 73,
        "gross": 171.48,
        "price": "4.99",
        "certification": "R",
        "genres": ["Action", "Sci-Fi"],
        "directors": ["Lana Wachowski", "Lilly Wachowski"],
        "stars": ["Keanu Reeves", "Laurence Fishburne"],
        "description": "Хакер Нео дізнається, що світ навколо — симуляція, "
        "і приєднується до повстання проти машин.",
    },
    {
        "name": "Interstellar",
        "poster": "interstellar",
        "year": 2014,
        "time": 169,
        "imdb": 8.6,
        "votes": 1512360,
        "meta_score": 74,
        "gross": 188.02,
        "price": "7.49",
        "certification": "PG-13",
        "genres": ["Adventure", "Drama", "Sci-Fi"],
        "directors": ["Christopher Nolan"],
        "stars": ["Matthew McConaughey", "Anne Hathaway"],
        "description": "Група дослідників летить крізь червоточину, щоб знайти "
        "людству новий дім, поки Земля вмирає.",
    },
    {
        "name": "Spirited Away",
        "poster": "spirited-away",
        "year": 2001,
        "time": 125,
        "imdb": 8.6,
        "votes": 651376,
        "meta_score": 96,
        "gross": 10.06,
        "price": "5.49",
        "certification": "PG",
        "genres": ["Animation", "Adventure", "Family"],
        "directors": ["Hayao Miyazaki"],
        "stars": ["Rumi Hiiragi", "Miyu Irino"],
        "description": "Десятирічна Тіхіро потрапляє у світ духів і має "
        "врятувати батьків, перетворених на свиней.",
    },
    {
        "name": "The Silence of the Lambs",
        "poster": "silence-of-the-lambs",
        "year": 1991,
        "time": 118,
        "imdb": 8.6,
        "votes": 1270197,
        "meta_score": 85,
        "gross": 130.74,
        "price": "4.99",
        "certification": "R",
        "genres": ["Crime", "Drama", "Thriller"],
        "directors": ["Jonathan Demme"],
        "stars": ["Jodie Foster", "Anthony Hopkins"],
        "description": "Курсантка ФБР звертається по допомогу до ув'язненого "
        "психіатра-канібала, щоб упіймати серійного вбивцю.",
    },
    {
        "name": "Gladiator",
        "poster": "gladiator",
        "year": 2000,
        "time": 155,
        "imdb": 8.5,
        "votes": 1341460,
        "meta_score": 67,
        "gross": 187.71,
        "price": "5.99",
        "certification": "R",
        "genres": ["Action", "Adventure", "Drama"],
        "directors": ["Ridley Scott"],
        "stars": ["Russell Crowe", "Joaquin Phoenix"],
        "description": "Зраджений римський генерал стає гладіатором і шукає "
        "помсти імператору, який убив його родину.",
    },
    {
        "name": "The Lion King",
        "poster": "lion-king",
        "year": 1994,
        "time": 88,
        "imdb": 8.5,
        "votes": 942045,
        "meta_score": 88,
        "gross": 422.78,
        "price": "3.99",
        "certification": "G",
        "genres": ["Animation", "Adventure", "Drama"],
        "directors": ["Roger Allers", "Rob Minkoff"],
        "stars": ["Matthew Broderick", "Jeremy Irons"],
        "description": "Левеня Сімба тікає після загибелі батька і через "
        "роки повертається, щоб забрати своє королівство.",
    },
    {
        "name": "Back to the Future",
        "poster": "back-to-the-future",
        "year": 1985,
        "time": 116,
        "imdb": 8.5,
        "votes": 1058081,
        "meta_score": 87,
        "gross": 210.61,
        "price": "3.99",
        "certification": "PG",
        "genres": ["Adventure", "Comedy", "Sci-Fi"],
        "directors": ["Robert Zemeckis"],
        "stars": ["Michael J. Fox", "Christopher Lloyd"],
        "description": "Підліток Марті Макфлай на машині часу потрапляє "
        "в 1955 рік і мусить звести разом власних батьків.",
    },
    {
        "name": "Parasite",
        "poster": "parasite",
        "year": 2019,
        "time": 132,
        "imdb": 8.6,
        "votes": 552778,
        "meta_score": 96,
        "gross": 53.37,
        "price": "8.49",
        "certification": "R",
        "genres": ["Comedy", "Drama", "Thriller"],
        "directors": ["Bong Joon Ho"],
        "stars": ["Song Kang-ho", "Lee Sun-kyun"],
        "description": "Бідна родина Кім крок за кроком влаштовується "
        "на роботу в дім багатих Паків — доки не з'являється таємниця.",
    },
    {
        "name": "Whiplash",
        "poster": "whiplash",
        "year": 2014,
        "time": 106,
        "imdb": 8.5,
        "votes": 717585,
        "meta_score": 88,
        "gross": 13.09,
        "price": "4.49",
        "certification": "R",
        "genres": ["Drama", "Music"],
        "directors": ["Damien Chazelle"],
        "stars": ["Miles Teller", "J.K. Simmons"],
        "description": "Молодий барабанщик потрапляє до викладача, який "
        "доводить учнів до межі заради величі.",
    },
    {
        "name": "Alien",
        "poster": "alien",
        "year": 1979,
        "time": 117,
        "imdb": 8.4,
        "votes": 787806,
        "meta_score": 89,
        "gross": 78.90,
        "price": "3.49",
        "certification": "R",
        "genres": ["Horror", "Sci-Fi"],
        "directors": ["Ridley Scott"],
        "stars": ["Sigourney Weaver", "Tom Skerritt"],
        "description": "Екіпаж вантажного корабля приймає сигнал лиха "
        "і бере на борт смертоносну інопланетну істоту.",
    },
    {
        "name": "WALL-E",
        "poster": "wall-e",
        "year": 2008,
        "time": 98,
        "imdb": 8.4,
        "votes": 999790,
        "meta_score": 95,
        "gross": 223.81,
        "price": "3.99",
        "certification": "G",
        "genres": ["Animation", "Adventure", "Family"],
        "directors": ["Andrew Stanton"],
        "stars": ["Ben Burtt", "Elissa Knight"],
        "description": "Самотній робот-прибиральник на покинутій Землі "
        "закохується і вирушає за роботом EVE у космос.",
    },
    {
        "name": "Toy Story",
        "poster": "toy-story",
        "year": 1995,
        "time": 81,
        "imdb": 8.3,
        "votes": 887429,
        "meta_score": 95,
        "gross": 191.80,
        "price": "2.99",
        "certification": "G",
        "genres": ["Animation", "Adventure", "Comedy"],
        "directors": ["John Lasseter"],
        "stars": ["Tom Hanks", "Tim Allen"],
        "description": "Ковбой Вуді ревнує хлопчика Енді до нової іграшки — "
        "космічного рейнджера Базза Лайтера.",
    },
]


def get_or_create(session: Session, model: type[NamedModel], name: str) -> NamedModel:
    """Return the entity with this name, creating it if needed."""
    entity = session.scalars(select(model).where(model.name == name)).first()
    if entity is None:
        entity = model(name=name)
        session.add(entity)
        session.flush()
    return entity


def find_poster(poster: str) -> Path | None:
    """Return the poster file with any supported extension, if it exists."""
    for extension in POSTER_TYPES:
        path = POSTERS_DIR / f"{poster}{extension}"
        if path.exists():
            return path
    return None


def upload_poster(movie: Movie, path: Path) -> None:
    """Upload the file to S3 under the same key format as the API uses."""
    extension = "jpg" if path.suffix == ".jpeg" else path.suffix[1:]
    key = f"posters/{movie.id}/{uuid4().hex}.{extension}"
    upload_file(key, path.read_bytes(), POSTER_TYPES[path.suffix])
    movie.poster = key


def seed_movie(session: Session, data: dict[str, Any]) -> str:
    """Create one movie (or reuse the existing one) and attach a poster."""
    movie = session.scalars(
        select(Movie).where(
            Movie.name == data["name"],
            Movie.year == data["year"],
            Movie.time == data["time"],
        )
    ).first()
    status = "exists"
    if movie is None:
        movie = Movie(
            name=data["name"],
            year=data["year"],
            time=data["time"],
            imdb=data["imdb"],
            votes=data["votes"],
            meta_score=data["meta_score"],
            gross=data["gross"],
            description=data["description"],
            price=Decimal(data["price"]),
            certification=get_or_create(session, Certification, data["certification"]),
            genres=[get_or_create(session, Genre, name) for name in data["genres"]],
            directors=[
                get_or_create(session, Director, name) for name in data["directors"]
            ],
            stars=[get_or_create(session, Star, name) for name in data["stars"]],
        )
        session.add(movie)
        session.flush()  # movie.id is needed for the poster key
        status = "created"

    if movie.poster is None:
        path = find_poster(data["poster"])
        if path is None:
            return f"{status}, no poster file"
        upload_poster(movie, path)
        return f"{status}, poster uploaded"
    return f"{status}, has poster"


def main() -> None:
    ensure_bucket_exists()
    with SyncSessionLocal() as session:
        for data in MOVIES:
            print(f"{data['name']}: {seed_movie(session, data)}")
        session.commit()


if __name__ == "__main__":
    main()
