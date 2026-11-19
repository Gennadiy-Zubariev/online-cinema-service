import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, NavLink, useNavigate, useSearchParams } from 'react-router'

import { useAuth } from '../auth/useAuth'
import { useLibrary } from '../hooks/useLibrary'
import { CartIcon, SearchIcon, UserIcon } from './icons'
import styles from './Navbar.module.css'

function navClass({ isActive }: { isActive: boolean }) {
  return isActive ? `${styles.link} ${styles.linkActive}` : styles.link
}

function SearchForm({ initialText }: { initialText: string }) {
  const navigate = useNavigate()
  const [text, setText] = useState(initialText)

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const search = text.trim()
    void navigate(search ? `/movies?search=${encodeURIComponent(search)}` : '/movies')
  }

  return (
    <form className={styles.search} role="search" onSubmit={handleSubmit}>
      <SearchIcon size={18} />
      <input
        type="search"
        placeholder="Назва, опис, актор, режисер"
        aria-label="Пошук фільмів"
        value={text}
        onChange={(event) => setText(event.target.value)}
      />
    </form>
  )
}

function ProfileMenu() {
  const { status, profile, logout } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  // Close the menu on a click outside it.
  useEffect(() => {
    if (!open) return
    function handleClick(event: MouseEvent) {
      if (!menuRef.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('click', handleClick)
    return () => document.removeEventListener('click', handleClick)
  }, [open])

  async function handleLogout() {
    setOpen(false)
    await logout()
    void navigate('/')
  }

  return (
    <div className={styles.menuWrap} ref={menuRef}>
      <button
        type="button"
        className={styles.iconButton}
        aria-label="Меню профілю"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        {profile?.avatar_url ? (
          <img className={styles.avatar} src={profile.avatar_url} alt="" />
        ) : (
          <UserIcon />
        )}
      </button>
      {open && (
        <div className={styles.menu} onClick={() => setOpen(false)}>
          {status === 'user' ? (
            <>
              <p className={styles.menuEmail}>{profile?.email}</p>
              <Link to="/account">Кабінет</Link>
              <button type="button" onClick={() => void handleLogout()}>
                Вийти
              </button>
            </>
          ) : (
            <>
              <Link to="/login">Увійти</Link>
              <Link to="/register">Зареєструватися</Link>
            </>
          )}
        </div>
      )}
    </div>
  )
}

export function Navbar() {
  const { isModerator } = useAuth()
  const { cartItems } = useLibrary()
  const [searchParams] = useSearchParams()
  const search = searchParams.get('search') ?? ''

  return (
    <header className={styles.header}>
      <nav className={styles.nav}>
        <Link to="/" className={styles.logo}>
          <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
            <path d="M7 4.5v15l12-7.5z" fill="currentColor" />
          </svg>
          Сеанс
        </Link>
        <div className={styles.links}>
          <NavLink to="/" end className={navClass}>
            Головна
          </NavLink>
          <NavLink to="/movies" className={navClass}>
            Фільми
          </NavLink>
          {isModerator && (
            <NavLink to="/moderator" className={navClass}>
              Модератор
            </NavLink>
          )}
        </div>
        {/* key: the field follows the URL (e.g. after "reset search") */}
        <SearchForm key={search} initialText={search} />
        <div className={styles.actions}>
          <Link to="/cart" className={styles.iconButton} aria-label="Корзина">
            <CartIcon />
            {cartItems.length > 0 && <span className={styles.badge}>{cartItems.length}</span>}
          </Link>
          <ProfileMenu />
        </div>
      </nav>
    </header>
  )
}
