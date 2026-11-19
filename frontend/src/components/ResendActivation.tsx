import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { resendActivation } from '../api/accounts'
import { getErrorMessage } from '../utils/errors'

// "Send the activation link again". With `email` - one button; without - an email field.
export function ResendActivation({ email }: { email?: string }) {
  const [typedEmail, setTypedEmail] = useState('')
  const mutation = useMutation({
    mutationFn: () => resendActivation(email ?? typedEmail),
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    mutation.mutate()
  }

  if (mutation.isSuccess) {
    return (
      <p className="notice notice-success">
        Якщо акаунт існує й ще не активований, ми надіслали новий лист. Посилання діє 24 години.
      </p>
    )
  }

  // Not a <form> when the email is known: this block can sit inside another form.
  if (email !== undefined) {
    return (
      <button
        type="button"
        className="btn btn-secondary"
        disabled={mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        Надіслати лист активації ще раз
      </button>
    )
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <div className="field">
        <label htmlFor="resend-email">Email</label>
        <input
          id="resend-email"
          className="input"
          type="email"
          required
          value={typedEmail}
          onChange={(event) => setTypedEmail(event.target.value)}
        />
      </div>
      {mutation.isError && <p className="notice notice-error">{getErrorMessage(mutation.error)}</p>}
      <button className="btn btn-secondary" type="submit" disabled={mutation.isPending}>
        Надіслати нове посилання
      </button>
    </form>
  )
}
