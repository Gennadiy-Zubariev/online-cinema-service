// Catalog filters live in the URL (?genre_id=3&sort_by=imdb&page=2): the page can be
// reloaded, shared or opened with "back" and shows the same movies.
import { useSearchParams } from 'react-router'

import type { CatalogParams } from '../api/types'

// Divides by 2, 3, 4 and 6 - full rows for any number of columns.
export const CATALOG_PAGE_SIZE = 24

const NUMBER_KEYS = ['genre_id', 'year_from', 'year_to', 'imdb_min', 'imdb_max', 'page'] as const
const SORT_VALUES = ['id', 'price', 'year', 'votes', 'imdb'] as const

function toNumber(value: string | null): number | undefined {
  if (value === null || value === '') return undefined
  const number = Number(value)
  return Number.isFinite(number) ? number : undefined
}

export function useCatalogParams() {
  const [searchParams, setSearchParams] = useSearchParams()

  const params: CatalogParams = { page_size: CATALOG_PAGE_SIZE }
  for (const key of NUMBER_KEYS) {
    params[key] = toNumber(searchParams.get(key))
  }
  params.search = searchParams.get('search') ?? undefined
  const sortBy = searchParams.get('sort_by')
  params.sort_by = SORT_VALUES.find((value) => value === sortBy)
  params.order = searchParams.get('order') === 'desc' ? 'desc' : undefined

  // Change some params; any change except the page itself returns to page 1.
  function updateParams(changes: Partial<CatalogParams>) {
    setSearchParams((current) => {
      const next = new URLSearchParams(current)
      for (const [key, value] of Object.entries(changes)) {
        if (value === undefined || value === null || value === '') {
          next.delete(key)
        } else {
          next.set(key, String(value))
        }
      }
      if (!('page' in changes)) {
        next.delete('page')
      }
      return next
    })
  }

  // Remove all catalog params but keep others (e.g. ?tab= in the account page).
  function resetParams() {
    setSearchParams((current) => {
      const next = new URLSearchParams(current)
      for (const key of [...NUMBER_KEYS, 'search', 'sort_by', 'order']) {
        next.delete(key)
      }
      return next
    })
  }

  const hasFilters = Boolean(
    params.search ||
    params.genre_id ||
    params.year_from ||
    params.year_to ||
    params.imdb_min ||
    params.imdb_max,
  )

  return { params, updateParams, resetParams, hasFilters }
}
