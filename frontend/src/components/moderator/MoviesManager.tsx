import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'

import { deleteMovie, getMovie, listMovies } from '../../api/movies'
import type { MovieListItem } from '../../api/types'
import { getErrorMessage } from '../../utils/errors'
import { formText } from '../../utils/forms'
import { formatPrice } from '../../utils/format'
import { Pagination } from '../Pagination'
import { Spinner } from '../Spinner'
import { MovieForm } from './MovieForm'
import styles from './Moderator.module.css'

const PAGE_SIZE = 20

// Editing needs the full movie (description, people) - the list item has less.
function EditMovie({ movieId, onDone }: { movieId: number; onDone: () => void }) {
  const query = useQuery({ queryKey: ['movie', movieId], queryFn: () => getMovie(movieId) })
  if (query.isPending) return <Spinner />
  if (query.isError) {
    return (
      <div className={styles.panel}>
        <p className="notice notice-error">{getErrorMessage(query.error)}</p>
        <button type="button" className="btn btn-secondary" onClick={onDone}>
          Назад
        </button>
      </div>
    )
  }
  return <MovieForm key={movieId} movie={query.data} onDone={onDone} />
}

function MovieRow({ movie, onEdit }: { movie: MovieListItem; onEdit: () => void }) {
  const queryClient = useQueryClient()
  const remove = useMutation({
    mutationFn: () => deleteMovie(movie.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['movies'] }),
  })

  function handleDelete() {
    // The backend refuses (409) if the movie is in any order or purchased.
    if (window.confirm(`Видалити фільм «${movie.name}»? Його також буде прибрано з корзин.`)) {
      remove.mutate()
    }
  }

  return (
    <li className={styles.row}>
      <span className={styles.id}>#{movie.id}</span>
      <span className={styles.name}>
        <Link to={`/movies/${movie.id}`}>{movie.name}</Link>
        <span className="muted">
          {' '}
          · {movie.year} · {formatPrice(movie.price)}
          {movie.poster_url ? '' : ' · без постера'}
        </span>
      </span>
      <button type="button" className="btn btn-secondary btn-small" onClick={onEdit}>
        Редагувати
      </button>
      <button
        type="button"
        className="btn btn-danger btn-small"
        disabled={remove.isPending}
        onClick={handleDelete}
      >
        Видалити
      </button>
      {remove.isError && (
        <p className={`error ${styles.rowError}`}>{getErrorMessage(remove.error)}</p>
      )}
    </li>
  )
}

export function MoviesManager() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [mode, setMode] = useState<'list' | 'create' | number>('list') // number = edited id
  const [idToOpen, setIdToOpen] = useState('')

  const query = useQuery({
    queryKey: ['movies', 'moderator', search, page],
    queryFn: () => listMovies({ search, page, page_size: PAGE_SIZE, sort_by: 'id', order: 'desc' }),
    placeholderData: keepPreviousData,
  })

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSearch(formText(new FormData(event.currentTarget), 'search'))
    setPage(1)
  }

  function handleOpenById(event: FormEvent) {
    event.preventDefault()
    if (idToOpen) setMode(Number(idToOpen))
  }

  if (mode === 'create') return <MovieForm onDone={() => setMode('list')} />
  if (typeof mode === 'number') return <EditMovie movieId={mode} onDone={() => setMode('list')} />

  return (
    <section className={styles.panel}>
      <div className={styles.toolbar}>
        <button type="button" className="btn" onClick={() => setMode('create')}>
          Додати фільм
        </button>
        <form className={styles.toolbarForm} onSubmit={handleSearch}>
          <input
            name="search"
            className="input"
            placeholder="Пошук за назвою, людьми"
            aria-label="Пошук фільмів"
          />
          <button type="submit" className="btn btn-secondary">
            Знайти
          </button>
        </form>
        <form className={styles.toolbarForm} onSubmit={handleOpenById}>
          <input
            className="input"
            type="number"
            min={1}
            placeholder="id фільму"
            aria-label="Відкрити фільм за id"
            style={{ width: 130 }}
            value={idToOpen}
            onChange={(event) => setIdToOpen(event.target.value)}
          />
          <button type="submit" className="btn btn-secondary">
            Відкрити
          </button>
        </form>
      </div>
      {query.isError && <p className="notice notice-error">{getErrorMessage(query.error)}</p>}
      {query.data?.items.length === 0 && <p className="muted">Фільмів не знайдено.</p>}
      <ul className={styles.list}>
        {query.data?.items.map((movie) => (
          <MovieRow key={movie.id} movie={movie} onEdit={() => setMode(movie.id)} />
        ))}
      </ul>
      {query.data && (
        <Pagination page={page} pageSize={PAGE_SIZE} total={query.data.total} onChange={setPage} />
      )}
    </section>
  )
}
