import { Link, useSearchParams } from 'react-router'

import { useAuth } from '../auth/useAuth'
import { EntityManager } from '../components/moderator/EntityManager'
import { MoviesManager } from '../components/moderator/MoviesManager'
import { UsersManager } from '../components/moderator/UsersManager'
import { Spinner } from '../components/Spinner'
import { Tabs } from '../components/Tabs'

const TABS = [
  { id: 'movies', label: 'Фільми' },
  { id: 'genres', label: 'Жанри' },
  { id: 'stars', label: 'Актори' },
  { id: 'directors', label: 'Режисери' },
  { id: 'certifications', label: 'Сертифікації' },
  { id: 'users', label: 'Користувачі' }, // admin only
] as const

export function ModeratorPage() {
  const { profile, isModerator, isAdmin } = useAuth()
  const [searchParams] = useSearchParams()

  if (!profile) return <Spinner />
  // The backend checks rights anyway (403); this only hides the page.
  if (!isModerator) {
    return (
      <div className="page narrow">
        <h1>Немає доступу</h1>
        <p className="muted">Цей розділ — лише для модераторів.</p>
        <Link to="/movies">Перейти до фільмів</Link>
      </div>
    )
  }

  const tabs = TABS.filter((item) => item.id !== 'users' || isAdmin)
  const tabParam = searchParams.get('tab')
  const tab = tabs.find((item) => item.id === tabParam) ?? tabs[0]

  return (
    <div className="page">
      <h1>Модератор</h1>
      <Tabs tabs={tabs} activeId={tab.id} basePath="/moderator" label="Розділи модератора" />
      {tab.id === 'movies' && <MoviesManager />}
      {tab.id === 'users' && <UsersManager />}
      {tab.id !== 'movies' && tab.id !== 'users' && (
        // key: a fresh manager (page 1, empty form) for each reference list
        <EntityManager key={tab.id} kind={tab.id} title={tab.label} />
      )}
    </div>
  )
}
