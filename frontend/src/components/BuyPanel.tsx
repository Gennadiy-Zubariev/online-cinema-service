import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useLocation } from 'react-router'

import { addFavorite, removeFavorite } from '../api/movies'
import { addToCart } from '../api/shop'
import type { MovieDetail } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { CART_KEY, FAVORITE_IDS_KEY, PURCHASED_IDS_KEY, useLibrary } from '../hooks/useLibrary'
import { getErrorMessage } from '../utils/errors'
import { formatPrice } from '../utils/format'
import styles from './BuyPanel.module.css'
import { FilmIcon } from './icons'

// Price + "Buy" / "In cart" / "Purchased" + favorites toggle.
export function BuyPanel({ movie }: { movie: MovieDetail }) {
  const { status } = useAuth()
  const location = useLocation()
  const queryClient = useQueryClient()
  const { favoriteIds, purchasedIds, cartIds } = useLibrary()

  const isPurchased = purchasedIds.has(movie.id)
  const inCart = cartIds.has(movie.id)
  const isFavorite = favoriteIds.has(movie.id)

  const buy = useMutation({
    mutationFn: () => addToCart(movie.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CART_KEY }),
    // 409 - bought in another tab meanwhile: refresh "purchased" to show the badge.
    onError: () => queryClient.invalidateQueries({ queryKey: PURCHASED_IDS_KEY }),
  })

  const favorite = useMutation({
    mutationFn: () => (isFavorite ? removeFavorite(movie.id) : addFavorite(movie.id)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: FAVORITE_IDS_KEY }),
  })

  if (status !== 'user') {
    const next = encodeURIComponent(location.pathname)
    return (
      <div className={styles.panel}>
        <p className={styles.price}>{formatPrice(movie.price)}</p>
        <p className="muted">Щоб купити фільм, увійдіть або створіть акаунт.</p>
        <div className={styles.buttons}>
          <Link to={`/register`} className="btn">
            Зареєструватися
          </Link>
          <Link to={`/login?next=${next}`} className="btn btn-secondary">
            Увійти
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.panel}>
      {isPurchased ? (
        <p className={styles.owned}>Фільм придбано — він у вашій бібліотеці.</p>
      ) : (
        <p className={styles.price}>{formatPrice(movie.price)}</p>
      )}
      <div className={styles.buttons}>
        {!isPurchased &&
          (inCart ? (
            <Link to="/cart" className="btn btn-secondary">
              У корзині, перейти до оплати
            </Link>
          ) : (
            <button
              type="button"
              className="btn"
              disabled={buy.isPending}
              onClick={() => buy.mutate()}
            >
              Купити
            </button>
          ))}
        <button
          type="button"
          className={`btn btn-secondary ${isFavorite ? styles.favoriteOn : ''}`}
          aria-pressed={isFavorite}
          disabled={favorite.isPending}
          onClick={() => favorite.mutate()}
        >
          <FilmIcon size={18} />
          {isFavorite ? 'В обраному' : 'Додати в обране'}
        </button>
      </div>
      {buy.isError && <p className="notice notice-error">{getErrorMessage(buy.error)}</p>}
      {favorite.isError && <p className="notice notice-error">{getErrorMessage(favorite.error)}</p>}
    </div>
  )
}
