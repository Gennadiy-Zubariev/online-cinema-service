import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { activateUser, changeUserGroup, listUsers } from '../../api/accounts'
import type { AdminUser, UserGroup } from '../../api/types'
import { getErrorMessage } from '../../utils/errors'
import { formatDate } from '../../utils/format'
import { Pagination } from '../Pagination'
import styles from './Moderator.module.css'

const PAGE_SIZE = 20
const GROUPS: { value: UserGroup; label: string }[] = [
  { value: 'user', label: 'Користувач' },
  { value: 'moderator', label: 'Модератор' },
  { value: 'admin', label: 'Адміністратор' },
]

function UserRow({ user }: { user: AdminUser }) {
  const queryClient = useQueryClient()
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['users'] })

  const group = useMutation({
    mutationFn: (value: UserGroup) => changeUserGroup(user.id, value),
    onSuccess: refresh,
  })
  const activate = useMutation({ mutationFn: () => activateUser(user.id), onSuccess: refresh })
  const error = group.error ?? activate.error

  return (
    <li className={styles.row}>
      <span className={styles.id}>#{user.id}</span>
      <span className={styles.name}>
        {user.email}
        <span className="muted"> · з {formatDate(user.created_at)}</span>
      </span>
      {user.is_active ? (
        <span className={styles.badge}>Активний</span>
      ) : (
        <>
          <span className={`${styles.badge} ${styles.badgeWarn}`}>Не активований</span>
          <button
            type="button"
            className="btn btn-secondary btn-small"
            disabled={activate.isPending}
            onClick={() => activate.mutate()}
          >
            Активувати
          </button>
        </>
      )}
      <select
        className="input"
        style={{ width: 'auto' }}
        aria-label={`Роль ${user.email}`}
        value={user.group.name}
        disabled={group.isPending}
        onChange={(event) => group.mutate(event.target.value as UserGroup)}
      >
        {GROUPS.map((item) => (
          <option key={item.value} value={item.value}>
            {item.label}
          </option>
        ))}
      </select>
      {error && <p className={`error ${styles.rowError}`}>{getErrorMessage(error)}</p>}
    </li>
  )
}

// Admin only: users list, role change and manual activation.
export function UsersManager() {
  const [page, setPage] = useState(1)
  const query = useQuery({
    queryKey: ['users', page],
    queryFn: () => listUsers(page, PAGE_SIZE),
    placeholderData: keepPreviousData,
  })

  return (
    <section className={styles.panel}>
      {query.isError && <p className="notice notice-error">{getErrorMessage(query.error)}</p>}
      <ul className={styles.list}>
        {query.data?.items.map((user) => (
          <UserRow key={user.id} user={user} />
        ))}
      </ul>
      {query.data && (
        <Pagination page={page} pageSize={PAGE_SIZE} total={query.data.total} onChange={setPage} />
      )}
    </section>
  )
}
