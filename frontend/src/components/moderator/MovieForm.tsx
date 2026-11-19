import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type ChangeEvent, type FormEvent } from 'react'

import {
  createMovie,
  listAllEntities,
  updateMovie,
  uploadPoster,
  type EntityKind,
} from '../../api/movies'
import type { MovieCreate, MovieDetail } from '../../api/types'
import { getErrorMessage } from '../../utils/errors'
import { formText } from '../../utils/forms'
import { Poster } from '../Poster'
import styles from './Moderator.module.css'

// Checkbox list with a local filter (the API has no search in reference lists).
function EntityPicker({
  kind,
  title,
  selected,
  onChange,
}: {
  kind: EntityKind
  title: string
  selected: number[]
  onChange: (ids: number[]) => void
}) {
  const [filter, setFilter] = useState('')
  const { data = [] } = useQuery({
    queryKey: ['entities-all', kind],
    queryFn: () => listAllEntities(kind),
  })
  const visible = data.filter((item) => item.name.toLowerCase().includes(filter.toLowerCase()))

  function toggle(id: number) {
    onChange(selected.includes(id) ? selected.filter((item) => item !== id) : [...selected, id])
  }

  return (
    <fieldset className={styles.picker}>
      <legend>{title}</legend>
      <input
        className="input"
        placeholder="Фільтр"
        aria-label={`Фільтр: ${title}`}
        value={filter}
        onChange={(event) => setFilter(event.target.value)}
      />
      <p className={styles.selected}>
        {data
          .filter((item) => selected.includes(item.id))
          .map((item) => item.name)
          .join(', ') || 'Нічого не вибрано'}
      </p>
      <div className={styles.options}>
        {visible.map((item) => (
          <label key={item.id}>
            <input
              type="checkbox"
              checked={selected.includes(item.id)}
              onChange={() => toggle(item.id)}
            />
            {item.name}
          </label>
        ))}
      </div>
    </fieldset>
  )
}

function PosterUpload({ movie }: { movie: MovieDetail }) {
  const queryClient = useQueryClient()
  const upload = useMutation({
    mutationFn: (file: File) => uploadPoster(movie.id, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['movie', movie.id] }),
  })

  function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (file) upload.mutate(file)
    event.target.value = ''
  }

  return (
    <div className={styles.posterEdit}>
      <Poster url={movie.poster_url} title={movie.name} />
      <div>
        <label className="btn btn-secondary btn-small">
          {upload.isPending ? 'Завантаження…' : 'Завантажити постер'}
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            hidden
            disabled={upload.isPending}
            onChange={handleFile}
          />
        </label>
        <p className="hint">Вертикальний, JPEG / PNG / WebP до 5 МБ.</p>
        {upload.isSuccess && <p className="hint">Постер оновлено.</p>}
        {upload.isError && <p className="error">{getErrorMessage(upload.error)}</p>}
      </div>
    </div>
  )
}

function numberOrNull(value: FormDataEntryValue | null): number | null {
  return value === null || value === '' ? null : Number(value)
}

interface MovieFormProps {
  // Without a movie - creation; with one - editing.
  movie?: MovieDetail
  onDone: () => void
}

export function MovieForm({ movie, onDone }: MovieFormProps) {
  const queryClient = useQueryClient()
  const { data: certifications = [] } = useQuery({
    queryKey: ['entities-all', 'certifications'],
    queryFn: () => listAllEntities('certifications'),
  })
  const [genreIds, setGenreIds] = useState(movie?.genres.map((item) => item.id) ?? [])
  const [directorIds, setDirectorIds] = useState(movie?.directors.map((item) => item.id) ?? [])
  const [starIds, setStarIds] = useState(movie?.stars.map((item) => item.id) ?? [])

  const save = useMutation({
    mutationFn: (data: MovieCreate) => (movie ? updateMovie(movie.id, data) : createMovie(data)),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['movies'] })
      if (movie) await queryClient.invalidateQueries({ queryKey: ['movie', movie.id] })
      onDone()
    },
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    save.mutate({
      name: formText(form, 'name'),
      year: Number(form.get('year')),
      time: Number(form.get('time')),
      imdb: Number(form.get('imdb')),
      votes: Number(form.get('votes')),
      meta_score: numberOrNull(form.get('meta_score')),
      gross: numberOrNull(form.get('gross')),
      description: formText(form, 'description'),
      price: formText(form, 'price'), // Decimal: send as a string, no float rounding
      certification_id: Number(form.get('certification_id')),
      genre_ids: genreIds,
      director_ids: directorIds,
      star_ids: starIds,
    })
  }

  return (
    <form className={styles.movieForm} onSubmit={handleSubmit}>
      <h2>{movie ? `Редагування: ${movie.name}` : 'Новий фільм'}</h2>
      {movie && <PosterUpload movie={movie} />}

      <div className={styles.grid}>
        <div className={`field ${styles.wide}`}>
          <label htmlFor="name">Назва</label>
          <input
            id="name"
            name="name"
            className="input"
            required
            maxLength={255}
            defaultValue={movie?.name}
          />
        </div>
        <div className="field">
          <label htmlFor="year">Рік</label>
          <input
            id="year"
            name="year"
            className="input"
            type="number"
            required
            min={1888}
            defaultValue={movie?.year}
          />
        </div>
        <div className="field">
          <label htmlFor="time">Тривалість, хв</label>
          <input
            id="time"
            name="time"
            className="input"
            type="number"
            required
            min={1}
            defaultValue={movie?.time}
          />
        </div>
        <div className="field">
          <label htmlFor="imdb">IMDb</label>
          <input
            id="imdb"
            name="imdb"
            className="input"
            type="number"
            required
            min={0}
            max={10}
            step={0.1}
            defaultValue={movie?.imdb}
          />
        </div>
        <div className="field">
          <label htmlFor="votes">Голосів IMDb</label>
          <input
            id="votes"
            name="votes"
            className="input"
            type="number"
            required
            min={0}
            defaultValue={movie?.votes}
          />
        </div>
        <div className="field">
          <label htmlFor="meta_score">Metascore</label>
          <input
            id="meta_score"
            name="meta_score"
            placeholder="необовʼязково"
            className="input"
            type="number"
            min={0}
            max={100}
            defaultValue={movie?.meta_score ?? ''}
          />
        </div>
        <div className="field">
          <label htmlFor="gross">Збори, млн $</label>
          <input
            id="gross"
            name="gross"
            placeholder="необовʼязково"
            className="input"
            type="number"
            min={0}
            step={0.01}
            defaultValue={movie?.gross ?? ''}
          />
        </div>
        <div className="field">
          <label htmlFor="price">Ціна, $</label>
          <input
            id="price"
            name="price"
            className="input"
            type="number"
            required
            min={0}
            step={0.01}
            defaultValue={movie?.price}
          />
        </div>
        <div className="field">
          <label htmlFor="certification_id">Сертифікація</label>
          <select
            id="certification_id"
            name="certification_id"
            className="input"
            required
            defaultValue={movie?.certification.id ?? ''}
          >
            <option value="" disabled>
              Оберіть
            </option>
            {certifications.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </div>
        <div className={`field ${styles.wide}`}>
          <label htmlFor="description">Опис</label>
          <textarea
            id="description"
            name="description"
            className="input"
            rows={4}
            required
            defaultValue={movie?.description}
          />
        </div>
      </div>

      <div className={styles.pickers}>
        <EntityPicker kind="genres" title="Жанри" selected={genreIds} onChange={setGenreIds} />
        <EntityPicker
          kind="directors"
          title="Режисери"
          selected={directorIds}
          onChange={setDirectorIds}
        />
        <EntityPicker kind="stars" title="Актори" selected={starIds} onChange={setStarIds} />
      </div>

      {save.isError && <p className="notice notice-error">{getErrorMessage(save.error)}</p>}
      <div className={styles.formButtons}>
        <button type="submit" className="btn" disabled={save.isPending}>
          {movie ? 'Зберегти зміни' : 'Створити фільм'}
        </button>
        <button type="button" className="btn btn-secondary" onClick={onDone}>
          Скасувати
        </button>
      </div>
      {!movie && <p className="hint">Постер можна завантажити після створення фільму.</p>}
    </form>
  )
}
