import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router'

import { completePasswordReset } from '../api/accounts'
import { AuthCard } from '../components/AuthCard'
import { PasswordHint } from '../components/PasswordHint'
import { getErrorMessage } from '../utils/errors'

// Opened from the email: /reset-password?token=...
export function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') ?? ''
  const [password, setPassword] = useState('')
  const [passwordAgain, setPasswordAgain] = useState('')
  const [mismatch, setMismatch] = useState(false)

  const mutation = useMutation({ mutationFn: () => completePasswordReset(token, password) })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (password !== passwordAgain) {
      setMismatch(true)
      return
    }
    setMismatch(false)
    mutation.mutate()
  }

  if (!token) {
    return (
      <AuthCard title="Посилання недійсне">
        <p>У посиланні немає токена.</p>
        <Link to="/forgot-password">Надіслати нове посилання</Link>
      </AuthCard>
    )
  }

  if (mutation.isSuccess) {
    return (
      <AuthCard title="Пароль змінено">
        <p>Увійдіть з новим паролем.</p>
        <Link to="/login" className="btn">
          Увійти
        </Link>
      </AuthCard>
    )
  }

  return (
    <AuthCard title="Новий пароль">
      <form className="form" onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="password">Новий пароль</label>
          <input
            id="password"
            className="input"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            maxLength={128}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <PasswordHint />
        </div>
        <div className="field">
          <label htmlFor="password-again">Новий пароль ще раз</label>
          <input
            id="password-again"
            className="input"
            type="password"
            autoComplete="new-password"
            required
            value={passwordAgain}
            onChange={(event) => setPasswordAgain(event.target.value)}
          />
        </div>
        {mismatch && <p className="notice notice-error">Паролі не збігаються.</p>}
        {mutation.isError && (
          <>
            <p className="notice notice-error">{getErrorMessage(mutation.error)}</p>
            <Link to="/forgot-password">Надіслати нове посилання</Link>
          </>
        )}
        <button className="btn" type="submit" disabled={mutation.isPending}>
          Зберегти пароль
        </button>
      </form>
    </AuthCard>
  )
}
