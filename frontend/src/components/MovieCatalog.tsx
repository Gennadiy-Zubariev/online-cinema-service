import { keepPreviousData, useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'

import type { CatalogParams, MovieList } from '../api/types'
import { useCatalogParams } from '../hooks/useCatalogParams'
import { useLibrary } from '../hooks/useLibrary'
import { getErrorMessage } from '../utils/errors'
import { CatalogFilters, GenreChips } from './CatalogFilters'
import styles from './MovieCatalog.module.css'
import { MovieGrid } from './MovieGrid'
import { Pagination } from './Pagination'
import { Spinner } from './Spinner'

interface MovieCatalogProps {
  // /movies, /favorites or /purchased - all take the same parameters.
  fetchMovies: (params: CatalogParams) => Promise<MovieList>
  queryKey: string
  emptyText: ReactNode
  // Shown above the grid only without filters (e.g. "top by IMDb").
  intro?: ReactNode
}

export function MovieCatalog({ fetchMovies, queryKey, emptyText, intro }: MovieCatalogProps) {
  const { params, updateParams, resetParams, hasFilters } = useCatalogParams()
  const { favoriteIds, purchasedIds } = useLibrary()

  const query = useQuery({
    queryKey: [queryKey, params],
    queryFn: () => fetchMovies(params),
    placeholderData: keepPreviousData, // keep old cards while the next page loads
  })

  return (
    <>
      <GenreChips params={params} updateParams={updateParams} />
      {params.search && (
        <p className={styles.searchLine}>
          Результати пошуку «{params.search}»{' '}
          <button
            type="button"
            className="btn btn-secondary btn-small"
            onClick={() => updateParams({ search: undefined })}
          >
            Скинути пошук
          </button>
        </p>
      )}
      {!hasFilters && !params.page && intro}
      <div className={styles.layout}>
        <CatalogFilters params={params} updateParams={updateParams} />
        <section aria-busy={query.isFetching}>
          {query.isPending && <Spinner />}
          {query.isError && <p className="notice notice-error">{getErrorMessage(query.error)}</p>}
          {query.data && (
            <>
              <p className={styles.total}>Знайдено фільмів: {query.data.total}</p>
              {query.data.items.length === 0 ? (
                <div className={styles.empty}>
                  {hasFilters ? (
                    <>
                      <p>Немає фільмів, що підходять під ці умови.</p>
                      <button type="button" className="btn btn-secondary" onClick={resetParams}>
                        Скинути фільтри
                      </button>
                    </>
                  ) : (
                    emptyText
                  )}
                </div>
              ) : (
                <MovieGrid
                  movies={query.data.items}
                  favoriteIds={favoriteIds}
                  purchasedIds={purchasedIds}
                />
              )}
              <Pagination
                page={query.data.page}
                pageSize={query.data.page_size}
                total={query.data.total}
                onChange={(page) => updateParams({ page })}
              />
            </>
          )}
        </section>
      </div>
    </>
  )
}
