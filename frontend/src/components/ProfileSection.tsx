import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type ChangeEvent, type FormEvent } from 'react'

import { changePassword, updateProfile, uploadAvatar } from '../api/accounts'
import type { Gender, Profile } from '../api/types'
import { getErrorMessage } from '../utils/errors'
import { PasswordHint } from './PasswordHint'
import styles from './ProfileSection.module.css'
import { UserIcon } from './icons'

const GROUP_NAMES = { user: 'Користувач', moderator: 'Модератор', admin: 'Адміністратор' }

// Empty field -> null: the API clears the value (an empty string would be saved).
function orNull(value: FormDataEntryValue | null): string | null {
  const text = typeof value === 'string' ? value.trim() : ''
  return text === '' ? null : text
}

function AvatarUpload({ profile }: { profile: Profile }) {
  const queryClient = useQueryClient()
  const upload = useMutation({
    mutationFn: uploadAvatar,
    onSuccess: (updated) => queryClient.setQueryData(['profile'], updated),
  })

  function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (file) upload.mutate(file)
    event.target.value = '' // the same file can be chosen again
  }

  return (
    <div className={styles.avatarBlock}>
      {profile.avatar_url ? (
        <img className={styles.avatar} src={profile.avatar_url} alt="Ваш аватар" />
      ) : (
        <div className={styles.avatar}>
          <UserIcon size={48} />
        </div>
      )}
      <div>
        <label className="btn btn-secondary btn-small">
          {upload.isPending ? 'Завантаження…' : 'Змінити аватар'}
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            hidden
            disabled={upload.isPending}
            onChange={handleFile}
          />
        </label>
        <p className="hint">JPEG, PNG або WebP до 2 МБ.</p>
        {upload.isError && <p className="error">{getErrorMessage(upload.error)}</p>}
      </div>
    </div>
  )
}

function ProfileForm({ profile }: { profile: Profile }) {
  const queryClient = useQueryClient()
  const save = useMutation({
    mutationFn: updateProfile,
    onSuccess: (updated) => queryClient.setQueryData(['profile'], updated),
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    save.mutate({
      first_name: orNull(form.get('first_name')),
      last_name: orNull(form.get('last_name')),
      gender: orNull(form.get('gender')) as Gender | null,
      date_of_birth: orNull(form.get('date_of_birth')),
      info: orNull(form.get('info')),
    })
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <div className={styles.twoColumns}>
        <div className="field">
          <label htmlFor="first_name">Імʼя</label>
          <input
            id="first_name"
            name="first_name"
            className="input"
            maxLength={100}
            defaultValue={profile.first_name ?? ''}
          />
        </div>
        <div className="field">
          <label htmlFor="last_name">Прізвище</label>
          <input
            id="last_name"
            name="last_name"
            className="input"
            maxLength={100}
            defaultValue={profile.last_name ?? ''}
          />
        </div>
        <div className="field">
          <label htmlFor="gender">Стать</label>
          <select id="gender" name="gender" className="input" defaultValue={profile.gender ?? ''}>
            <option value="">Не вказано</option>
            <option value="woman">Жіноча</option>
            <option value="man">Чоловіча</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="date_of_birth">Дата народження</label>
          <input
            id="date_of_birth"
            name="date_of_birth"
            className="input"
            type="date"
            max={new Date().toISOString().slice(0, 10)}
            defaultValue={profile.date_of_birth ?? ''}
          />
        </div>
      </div>
      <div className="field">
        <label htmlFor="info">Про себе</label>
        <textarea
          id="info"
          name="info"
          className="input"
          rows={3}
          maxLength={1000}
          defaultValue={profile.info ?? ''}
        />
      </div>
      <p className="hint">Імʼя та прізвище показуються біля ваших коментарів.</p>
      {save.isSuccess && <p className="notice notice-success">Профіль збережено.</p>}
      {save.isError && <p className="notice notice-error">{getErrorMessage(save.error)}</p>}
      <div>
        <button type="submit" className="btn" disabled={save.isPending}>
          Зберегти профіль
        </button>
      </div>
    </form>
  )
}

function PasswordForm() {
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const change = useMutation({
    mutationFn: () => changePassword(oldPassword, newPassword),
    onSuccess: () => {
      setOldPassword('')
      setNewPassword('')
    },
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    change.mutate()
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <div className="field">
        <label htmlFor="old_password">Поточний пароль</label>
        <input
          id="old_password"
          className="input"
          type="password"
          autoComplete="current-password"
          required
          value={oldPassword}
          onChange={(event) => setOldPassword(event.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor="new_password">Новий пароль</label>
        <input
          id="new_password"
          className="input"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          maxLength={128}
          value={newPassword}
          onChange={(event) => setNewPassword(event.target.value)}
        />
        <PasswordHint />
      </div>
      {change.isSuccess && <p className="notice notice-success">Пароль змінено.</p>}
      {change.isError && <p className="notice notice-error">{getErrorMessage(change.error)}</p>}
      <div>
        <button type="submit" className="btn btn-secondary" disabled={change.isPending}>
          Змінити пароль
        </button>
      </div>
    </form>
  )
}

export function ProfileSection({ profile }: { profile: Profile }) {
  return (
    <div className={styles.layout}>
      <section className={styles.card}>
        <AvatarUpload profile={profile} />
        <dl className={styles.account}>
          <dt>Email</dt>
          <dd>{profile.email}</dd>
          <dt>Роль</dt>
          <dd>{GROUP_NAMES[profile.group]}</dd>
        </dl>
      </section>
      <section className={styles.card}>
        <h2>Профіль</h2>
        <ProfileForm profile={profile} />
      </section>
      <section className={styles.card}>
        <h2>Пароль</h2>
        <PasswordForm />
      </section>
    </div>
  )
}
