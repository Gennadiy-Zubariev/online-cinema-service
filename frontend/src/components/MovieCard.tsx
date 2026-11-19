import { Link } from 'react-router'

import type { MovieListItem } from '../api/types'
import { formatDuration, formatPrice } from '../utils/format'
import { FilmIcon } from './icons'
import styles from './MovieCard.module.css'
import { Poster } from './Poster'

interface MovieCardProps {
  movie: MovieListItem
  isFavorite: boolean
  isPurchased: boolean
}

// On hover the card grows and shows a panel with details (no description -
// the list API does not return it; it is on the movie page).
export function MovieCard({ movie, isFavorite, isPurchased }: MovieCardProps) {
  return (
    <Link to={`/movies/${movie.id}`} className={styles.card}>
      <div className={styles.posterWrap}>
        <Poster url={movie.poster_url} title={movie.name} />
        {isPurchased && <span className={styles.purchased}>Придбано</span>}
        {isFavorite && (
          <span className={styles.favorite} title="В обраному">
            <FilmIcon size={16} />
          </span>
        )}
      </div>
      <div className={styles.panel}>
        <h3 className={styles.title}>{movie.name}</h3>
        <p className={styles.meta}>
          {movie.year}, {formatDuration(movie.time)}
        </p>
        <p className={styles.extra}>
          <span className={styles.imdb}>IMDb {movie.imdb.toFixed(1)}</span>
          {!isPurchased && <span className={styles.price}>{formatPrice(movie.price)}</span>}
        </p>
        {movie.genres.length > 0 && (
          <p className={styles.genres}>{movie.genres.map((genre) => genre.name).join(', ')}</p>
        )}
      </div>
    </Link>
  )
}
