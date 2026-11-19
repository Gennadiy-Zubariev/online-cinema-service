import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import {
  createEntity,
  deleteEntity,
  listEntities,
  updateEntity,
  type EntityKind,
} from '../../api/movies'
import type { NamedEntity } from '../../api/types'
import { getErrorMessage } from '../../utils/errors'
import { Pagination } from '../Pagination'
import styles from './Moderator.module.css'

const PAGE_SIZE = 20

function EntityRow({ kind, entity }: { kind: EntityKind; entity: NamedEntity }) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(entity.name)

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['entities', kind] })
  const rename = useMutation({
    mutationFn: () => updateEntity(kind, entity.id, name),
    onSuccess: async () => {
      setEditing(false)
      await refresh()
    },
  })
  const remove = useMutation({
    mutationFn: () => deleteEntity(kind, entity.id),
    onSuccess: refresh,
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    rename.mutate()
  }

  function handleDelete() {
    if (window.confirm(`Видалити «${entity.name}»?`)) remove.mutate()
  }

  const error = rename.error ?? remove.error
  return (
    <li className={styles.row}>
      <span className={styles.id}>#{entity.id}</span>
      {editing ? (
        <form className={styles.inlineForm} onSubmit={handleSubmit}>
          <input
            className="input"
            aria-label="Нова назва"
            required
            maxLength={255}
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <button type="submit" className="btn btn-small" disabled={rename.isPending}>
            Зберегти
          </button>
          <button
            type="button"
            className="btn btn-secondary btn-small"
            onClick={() => {
              setEditing(false)
              setName(entity.name)
            }}
          >
            Скасувати
          </button>
        </form>
      ) : (
        <>
          <span className={styles.name}>{entity.name}</span>
          <button
            type="button"
            className="btn btn-secondary btn-small"
            onClick={() => setEditing(true)}
          >
            Перейменувати
          </button>
          <button
            type="button"
            className="btn btn-danger btn-small"
            disabled={remove.isPending}
            onClick={handleDelete}
          >
            Видалити
          </button>
        </>
      )}
      {error && <p className={`error ${styles.rowError}`}>{getErrorMessage(error)}</p>}
    </li>
  )
}

// One manager for genres, stars, directors and certifications (same API shape).
export function EntityManager({ kind, title }: { kind: EntityKind; title: string }) {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [newName, setNewName] = useState('')

  const query = useQuery({
    queryKey: ['entities', kind, page],
    queryFn: () => listEntities(kind, page, PAGE_SIZE),
    placeholderData: keepPreviousData,
  })

  const create = useMutation({
    mutationFn: () => createEntity(kind, newName),
    onSuccess: async () => {
      setNewName('')
      await queryClient.invalidateQueries({ queryKey: ['entities', kind] })
      // Genres also feed the catalog chips.
      if (kind === 'genres') await queryClient.invalidateQueries({ queryKey: ['genres'] })
    },
  })

  function handleCreate(event: FormEvent) {
    event.preventDefault()
    create.mutate()
  }

  return (
    <section className={styles.panel}>
      <form className={styles.createForm} onSubmit={handleCreate}>
        <input
          className="input"
          placeholder={`Нова назва: ${title.toLowerCase()}`}
          aria-label="Назва нового запису"
          required
          maxLength={255}
          value={newName}
          onChange={(event) => setNewName(event.target.value)}
        />
        <button type="submit" className="btn" disabled={create.isPending}>
          Додати
        </button>
      </form>
      {create.isError && <p className="notice notice-error">{getErrorMessage(create.error)}</p>}

      {query.isError && <p className="notice notice-error">{getErrorMessage(query.error)}</p>}
      {query.data?.items.length === 0 && <p className="muted">Записів ще немає.</p>}
      <ul className={styles.list}>
        {query.data?.items.map((entity) => (
          <EntityRow key={entity.id} kind={kind} entity={entity} />
        ))}
      </ul>
      {query.data && (
        <Pagination page={page} pageSize={PAGE_SIZE} total={query.data.total} onChange={setPage} />
      )}
    </section>
  )
}
