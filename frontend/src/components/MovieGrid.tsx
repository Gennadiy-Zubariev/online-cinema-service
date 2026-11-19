import type { MovieListItem } from '../api/types'
import { MovieCard } from './MovieCard'
import styles from './MovieGrid.module.css'

interface MovieGridProps {
  movies: MovieListItem[]
  favoriteIds: Set<number>
  purchasedIds: Set<number>
}

export function MovieGrid({ movies, favoriteIds, purchasedIds }: MovieGridProps) {
  return (
    <div className={styles.grid}>
      {movies.map((movie) => (
        <MovieCard
          key={movie.id}
          movie={movie}
          isFavorite={favoriteIds.has(movie.id)}
          isPurchased={purchasedIds.has(movie.id)}
        />
      ))}
    </div>
  )
}
