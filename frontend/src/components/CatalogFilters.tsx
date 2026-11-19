import { useQuery } from '@tanstack/react-query'
import type { FormEvent } from 'react'

import { listGenres } from '../api/movies'
import type { CatalogParams } from '../api/types'
import styles from './CatalogFilters.module.css'

// One select = sort field + direction ("price:asc").
const SORT_OPTIONS = [
  { value: 'id:desc', label: 'Нещодавно додані' },
  { value: 'imdb:desc', label: 'Рейтинг IMDb' },
  { value: 'votes:desc', label: 'Популярні' },
  { value: 'year:desc', label: 'Новіші за роком' },
  { value: 'year:asc', label: 'Старіші за роком' },
  { value: 'price:asc', label: 'Спершу дешевші' },
  { value: 'price:desc', label: 'Спершу дорожчі' },
  { value: 'id:asc', label: 'Як у каталозі' },
]

interface FiltersProps {
  params: CatalogParams
  updateParams: (changes: Partial<CatalogParams>) => void
}

export function GenreChips({ params, updateParams }: FiltersProps) {
  const { data } = useQuery({ queryKey: ['genres'], queryFn: listGenres })
  if (!data || data.items.length === 0) return null

  return (
    <div className={styles.chips}>
      <button
        type="button"
        className={`chip ${params.genre_id ? '' : 'chip-active'}`}
        onClick={() => updateParams({ genre_id: undefined })}
      >
        Усі жанри
      </button>
      {data.items.map((genre) => (
        <button
          key={genre.id}
          type="button"
          className={`chip ${params.genre_id === genre.id ? 'chip-active' : ''}`}
          onClick={() => updateParams({ genre_id: genre.id })}
        >
          {genre.name}
          <span className={styles.count}>{genre.movies_count}</span>
        </button>
      ))}
    </div>
  )
}

function readNumber(form: FormData, name: string): number | undefined {
  const value = form.get(name)
  return value ? Number(value) : undefined
}

export function CatalogFilters({ params, updateParams }: FiltersProps) {
  const sortValue = `${params.sort_by ?? 'id'}:${params.order ?? 'asc'}`

  function handleSort(value: string) {
    const [sortBy, order] = value.split(':') as [CatalogParams['sort_by'], 'asc' | 'desc']
    updateParams({ sort_by: sortBy, order })
  }

  // Ranges are applied together by the button, not on every keystroke.
  function handleRanges(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    updateParams({
      year_from: readNumber(form, 'year_from'),
      year_to: readNumber(form, 'year_to'),
      imdb_min: readNumber(form, 'imdb_min'),
      imdb_max: readNumber(form, 'imdb_max'),
    })
  }

  const rangesKey = [params.year_from, params.year_to, params.imdb_min, params.imdb_max].join()

  return (
    <aside className={styles.filters}>
      <div className="field">
        <label htmlFor="sort">Сортування</label>
        <select
          id="sort"
          className="input"
          value={sortValue}
          onChange={(event) => handleSort(event.target.value)}
        >
          {SORT_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {/* key: when the URL changes (e.g. "reset"), the inputs show the new values */}
      <form key={rangesKey} className={styles.ranges} onSubmit={handleRanges}>
        <fieldset>
          <legend>Рік випуску</legend>
          <input
            name="year_from"
            className="input"
            type="number"
            min={1888}
            placeholder="від"
            aria-label="Рік від"
            defaultValue={params.year_from}
          />
          <input
            name="year_to"
            className="input"
            type="number"
            min={1888}
            placeholder="до"
            aria-label="Рік до"
            defaultValue={params.year_to}
          />
        </fieldset>
        <fieldset>
          <legend>Рейтинг IMDb</legend>
          <input
            name="imdb_min"
            className="input"
            type="number"
            min={0}
            max={10}
            step={0.1}
            placeholder="від"
            aria-label="IMDb від"
            defaultValue={params.imdb_min}
          />
          <input
            name="imdb_max"
            className="input"
            type="number"
            min={0}
            max={10}
            step={0.1}
            placeholder="до"
            aria-label="IMDb до"
            defaultValue={params.imdb_max}
          />
        </fieldset>
        <button type="submit" className="btn btn-secondary">
          Застосувати
        </button>
      </form>
    </aside>
  )
}
