import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'

import { requestPasswordReset } from '../api/accounts'
import { AuthCard } from '../components/AuthCard'
import { getErrorMessage } from '../utils/errors'

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const mutation = useMutation({ mutationFn: () => requestPasswordReset(email) })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    mutation.mutate()
  }

  if (mutation.isSuccess) {
    return (
      <AuthCard title="Перевірте пошту">
        <p>
          Якщо <strong>{email}</strong> зареєстрований і активований, ми надіслали посилання для
          нового пароля. Воно діє 1 годину.
        </p>
        <Link to="/login">Повернутися до входу</Link>
      </AuthCard>
    )
  }

  return (
    <AuthCard title="Скидання пароля">
      <form className="form" onSubmit={handleSubmit}>
        <p className="muted">Вкажіть email акаунта — надішлемо посилання для нового пароля.</p>
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
        {mutation.isError && (
          <p className="notice notice-error">{getErrorMessage(mutation.error)}</p>
        )}
        <button className="btn" type="submit" disabled={mutation.isPending}>
          Надіслати посилання
        </button>
      </form>
      <p>
        Згадали пароль? <Link to="/login">Увійти</Link>
      </p>
    </AuthCard>
  )
}
