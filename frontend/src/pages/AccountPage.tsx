import { Link, useSearchParams } from 'react-router'

import { listFavorites, listPurchased } from '../api/movies'
import { useAuth } from '../auth/useAuth'
import { MovieCatalog } from '../components/MovieCatalog'
import { ProfileSection } from '../components/ProfileSection'
import { Spinner } from '../components/Spinner'
import { Tabs } from '../components/Tabs'

const TABS = [
  { id: 'profile', label: 'Профіль' },
  { id: 'favorites', label: 'Обране' },
  { id: 'purchased', label: 'Придбані' },
] as const

type TabId = (typeof TABS)[number]['id']

export function AccountPage() {
  const { profile } = useAuth()
  const [searchParams] = useSearchParams()
  const tabParam = searchParams.get('tab')
  const tab: TabId = TABS.find((item) => item.id === tabParam)?.id ?? 'profile'

  return (
    <div className="page">
      <h1>Кабінет</h1>
      {/* Switching a tab drops the catalog filters of the previous one. */}
      <Tabs tabs={TABS} activeId={tab} basePath="/account" label="Розділи кабінету" />

      {tab === 'profile' && (profile ? <ProfileSection profile={profile} /> : <Spinner />)}
      {tab === 'favorites' && (
        <MovieCatalog
          fetchMovies={listFavorites}
          queryKey="favorites"
          emptyText={
            <p>
              Обраних фільмів ще немає. Позначайте їх кнопкою «Додати в обране» на сторінці фільму.
            </p>
          }
        />
      )}
      {tab === 'purchased' && (
        <MovieCatalog
          fetchMovies={listPurchased}
          queryKey="purchased"
          emptyText={
            <p>
              Тут будуть фільми, які ви купите. <Link to="/movies">Перейти до каталогу</Link>
            </p>
          }
        />
      )}
    </div>
  )
}
