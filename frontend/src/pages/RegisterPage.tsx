import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'

import { register } from '../api/accounts'
import { AuthCard } from '../components/AuthCard'
import { PasswordHint } from '../components/PasswordHint'
import { ResendActivation } from '../components/ResendActivation'
import { getErrorMessage } from '../utils/errors'

export function RegisterPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [passwordAgain, setPasswordAgain] = useState('')
  const [mismatch, setMismatch] = useState(false)

  const mutation = useMutation({ mutationFn: () => register(email, password) })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    // Checked only here: the backend gets one password.
    if (password !== passwordAgain) {
      setMismatch(true)
      return
    }
    setMismatch(false)
    mutation.mutate()
  }

  if (mutation.isSuccess) {
    return (
      <AuthCard title="Перевірте пошту">
        <p>
          Ми надіслали лист на <strong>{email}</strong>. Відкрийте посилання з нього, щоб активувати
          акаунт — воно діє 24 години.
        </p>
        <ResendActivation email={email} />
        <p>
          Уже активували? <Link to="/login">Увійти</Link>
        </p>
      </AuthCard>
    )
  }

  return (
    <AuthCard title="Реєстрація">
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
          <label htmlFor="password-again">Пароль ще раз</label>
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
          <p className="notice notice-error">{getErrorMessage(mutation.error)}</p>
        )}
        <button className="btn" type="submit" disabled={mutation.isPending}>
          Створити акаунт
        </button>
      </form>
      <p>
        Уже є акаунт? <Link to="/login">Увійти</Link>
      </p>
    </AuthCard>
  )
}
