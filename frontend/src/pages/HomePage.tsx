import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'

import { listGenres, listMovies } from '../api/movies'
import { useAuth } from '../auth/useAuth'
import { MovieGrid } from '../components/MovieGrid'
import { Poster } from '../components/Poster'
import { useLibrary } from '../hooks/useLibrary'
import styles from './HomePage.module.css'

// Posters of the highest-rated movies, tilted wall behind the headline.
function PosterCollage() {
  const { data } = useQuery({
    queryKey: ['home-collage'],
    queryFn: () => listMovies({ sort_by: 'imdb', order: 'desc', page_size: 18 }),
  })
  const movies = data?.items ?? []

  return (
    <div className={styles.collage} aria-hidden="true">
      {movies.map((movie) => (
        <Poster key={movie.id} url={movie.poster_url} title={movie.name} />
      ))}
    </div>
  )
}

function RecentMovies() {
  const { favoriteIds, purchasedIds } = useLibrary()
  const { data } = useQuery({
    queryKey: ['home-recent'],
    queryFn: () => listMovies({ sort_by: 'id', order: 'desc', page_size: 6 }),
  })
  if (!data || data.items.length === 0) return null

  return (
    <section className={styles.section}>
      <div className={styles.sectionHeader}>
        <h2>Нещодавно додані</h2>
        <Link to="/movies?sort_by=id&order=desc">Усі фільми</Link>
      </div>
      <MovieGrid movies={data.items} favoriteIds={favoriteIds} purchasedIds={purchasedIds} />
    </section>
  )
}

function Genres() {
  const { data } = useQuery({ queryKey: ['genres'], queryFn: listGenres })
  if (!data || data.items.length === 0) return null

  return (
    <section className={styles.section}>
      <h2>Жанри</h2>
      <div className={styles.genres}>
        {data.items.map((genre) => (
          <Link key={genre.id} to={`/movies?genre_id=${genre.id}`} className={styles.genre}>
            <span>{genre.name}</span>
            <span className="muted">Фільмів: {genre.movies_count}</span>
          </Link>
        ))}
      </div>
    </section>
  )
}

export function HomePage() {
  const { status } = useAuth()

  return (
    <>
      <section className={styles.hero}>
        <PosterCollage />
        <div className={styles.heroContent}>
          <h1 className={styles.headline}>Фільми, які залишаються з вами</h1>
          <p className={styles.lead}>
            Купуйте фільм один раз — і він назавжди у вашій бібліотеці. Фільтри за роком і рейтингом
            IMDb, обране, оцінки та коментарі глядачів.
          </p>
          <div className={styles.actions}>
            {status === 'user' ? (
              <Link to="/movies" className="btn">
                Перейти до фільмів
              </Link>
            ) : (
              <>
                <Link to="/register" className="btn">
                  Створити акаунт
                </Link>
                <Link to="/login" className="btn btn-secondary">
                  Увійти
                </Link>
                <Link to="/movies" className={styles.browse}>
                  Переглянути каталог
                </Link>
              </>
            )}
          </div>
        </div>
      </section>
      <div className="page">
        <RecentMovies />
        <Genres />
      </div>
    </>
  )
}
