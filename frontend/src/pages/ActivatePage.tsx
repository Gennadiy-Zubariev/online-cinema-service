import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router'

import { activate } from '../api/accounts'
import { AuthCard } from '../components/AuthCard'
import { ResendActivation } from '../components/ResendActivation'
import { Spinner } from '../components/Spinner'
import { getErrorMessage } from '../utils/errors'

// Opened from the email: /activate?token=...
export function ActivatePage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') ?? ''

  // useQuery, not useEffect: the request is sent once even in React StrictMode
  // (a second call would fail - the token is single-use).
  const query = useQuery({
    queryKey: ['activate', token],
    queryFn: () => activate(token),
    enabled: token !== '',
    staleTime: Infinity,
  })

  if (query.isLoading) {
    return (
      <AuthCard title="Активація акаунта">
        <Spinner />
      </AuthCard>
    )
  }

  if (query.isSuccess) {
    return (
      <AuthCard title="Акаунт активовано">
        <p>Тепер можна увійти й купувати фільми.</p>
        <Link to="/login" className="btn">
          Увійти
        </Link>
      </AuthCard>
    )
  }

  return (
    <AuthCard title="Не вдалося активувати">
      <p className="notice notice-error">
        {token ? getErrorMessage(query.error) : 'У посиланні немає токена активації.'}
      </p>
      <p>Вкажіть email — надішлемо нове посилання.</p>
      <ResendActivation />
    </AuthCard>
  )
}
