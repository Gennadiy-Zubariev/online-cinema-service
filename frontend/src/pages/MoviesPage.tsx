import { useQuery } from '@tanstack/react-query'

import { listMovies } from '../api/movies'
import { MovieCatalog } from '../components/MovieCatalog'
import { MovieGrid } from '../components/MovieGrid'
import { useLibrary } from '../hooks/useLibrary'
import styles from './MoviesPage.module.css'

function TopByImdb() {
  const { favoriteIds, purchasedIds } = useLibrary()
  const { data } = useQuery({
    queryKey: ['movies-top'],
    queryFn: () => listMovies({ sort_by: 'imdb', order: 'desc', page_size: 8 }),
  })
  if (!data || data.items.length < 4) return null // a short "top" looks broken

  return (
    <section className={styles.top}>
      <h2>Найвищий рейтинг IMDb</h2>
      <MovieGrid movies={data.items} favoriteIds={favoriteIds} purchasedIds={purchasedIds} />
    </section>
  )
}

export function MoviesPage() {
  return (
    <div className="page">
      <h1>Фільми</h1>
      <MovieCatalog
        fetchMovies={listMovies}
        queryKey="movies"
        emptyText={<p>Каталог поки порожній.</p>}
        intro={<TopByImdb />}
      />
    </div>
  )
}
