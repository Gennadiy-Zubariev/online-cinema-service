import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'

import { ApiError } from '../api/client'
import { getMovie } from '../api/movies'
import { BuyPanel } from '../components/BuyPanel'
import { Comments } from '../components/Comments'
import { MovieVotes } from '../components/MovieVotes'
import { Poster } from '../components/Poster'
import { Spinner } from '../components/Spinner'
import { useLibrary } from '../hooks/useLibrary'
import { getErrorMessage } from '../utils/errors'
import { formatDuration } from '../utils/format'
import { NotFoundPage } from './NotFoundPage'
import styles from './MovieDetailPage.module.css'

export function MovieDetailPage() {
  const movieId = Number(useParams().movieId)
  const { purchasedIds } = useLibrary()

  const query = useQuery({
    queryKey: ['movie', movieId],
    queryFn: () => getMovie(movieId),
    enabled: Number.isInteger(movieId),
  })

  if (
    !Number.isInteger(movieId) ||
    (query.error instanceof ApiError && query.error.status === 404)
  ) {
    return <NotFoundPage />
  }
  if (query.isPending) return <Spinner />
  if (query.isError) {
    return (
      <div className="page">
        <p className="notice notice-error">{getErrorMessage(query.error)}</p>
      </div>
    )
  }

  const movie = query.data
  return (
    <div className="page">
      <div className={styles.layout}>
        <div className={styles.posterColumn}>
          <Poster url={movie.poster_url} title={movie.name} />
          {purchasedIds.has(movie.id) && <span className={styles.purchased}>Придбано</span>}
        </div>

        <div className={styles.info}>
          <h1 className={styles.title}>{movie.name}</h1>
          <p className={styles.meta}>
            <span>{movie.year}</span>
            <span>{formatDuration(movie.time)}</span>
            <span className={styles.certification}>{movie.certification.name}</span>
          </p>

          <dl className={styles.scores}>
            <div>
              <dt>IMDb</dt>
              <dd className={styles.imdb}>{movie.imdb.toFixed(1)}</dd>
            </div>
            <div>
              <dt>Голосів IMDb</dt>
              <dd>{movie.votes.toLocaleString('uk-UA')}</dd>
            </div>
            {movie.meta_score !== null && (
              <div>
                <dt>Metascore</dt>
                <dd>{movie.meta_score}</dd>
              </div>
            )}
            {movie.gross !== null && (
              <div>
                <dt>Касові збори</dt>
                <dd>${movie.gross} млн</dd>
              </div>
            )}
          </dl>

          {movie.genres.length > 0 && (
            <div className={styles.genres}>
              {movie.genres.map((genre) => (
                <Link key={genre.id} to={`/movies?genre_id=${genre.id}`} className="chip">
                  {genre.name}
                </Link>
              ))}
            </div>
          )}

          <p className={styles.description}>{movie.description}</p>

          <dl className={styles.people}>
            {movie.directors.length > 0 && (
              <div>
                <dt>Режисер</dt>
                <dd>{movie.directors.map((person) => person.name).join(', ')}</dd>
              </div>
            )}
            {movie.stars.length > 0 && (
              <div>
                <dt>У ролях</dt>
                <dd>{movie.stars.map((person) => person.name).join(', ')}</dd>
              </div>
            )}
          </dl>

          <BuyPanel movie={movie} />
          <MovieVotes movie={movie} />
        </div>
      </div>

      <Comments movieId={movie.id} />
    </div>
  )
}
