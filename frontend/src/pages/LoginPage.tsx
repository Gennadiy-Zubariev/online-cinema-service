import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'

import { ApiError } from '../api/client'
import { translateMessage } from '../api/messages'
import { useAuth } from '../auth/useAuth'
import { AuthCard } from '../components/AuthCard'
import { ResendActivation } from '../components/ResendActivation'
import { getErrorMessage } from '../utils/errors'

// Only local paths: "next" from the URL must not send the user to another site.
function safeNext(next: string | null): string {
  return next?.startsWith('/') && !next.startsWith('//') ? next : '/movies'
}

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const mutation = useMutation({
    mutationFn: () => login(email, password),
    onSuccess: () => void navigate(safeNext(searchParams.get('next')), { replace: true }),
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    mutation.mutate()
  }

  // 403 - right password, but the account is not activated yet (or deactivated by
  // an admin: then resending the activation email would not help).
  const notActivated =
    mutation.error instanceof ApiError &&
    mutation.error.status === 403 &&
    mutation.error.message !== translateMessage('Account is deactivated.')

  return (
    <AuthCard title="Вхід">
      <form className="form" onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            className="input"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="password">Пароль</label>
          <input
            id="password"
            className="input"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <Link to="/forgot-password" className="hint">
            Забули пароль?
          </Link>
        </div>
        {mutation.isError && (
          <p className="notice notice-error">{getErrorMessage(mutation.error)}</p>
        )}
        {notActivated && <ResendActivation email={email} />}
        <button className="btn" type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? 'Входимо…' : 'Увійти'}
        </button>
      </form>
      <p>
        Немає акаунта? <Link to="/register">Зареєструватися</Link>
      </p>
    </AuthCard>
  )
}
