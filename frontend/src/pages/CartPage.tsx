import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'

import { checkoutOrder, clearCart, createOrder, listOrders, removeFromCart } from '../api/shop'
import type { NamedEntity, Order } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { Spinner } from '../components/Spinner'
import { CART_KEY, PURCHASED_IDS_KEY, useLibrary } from '../hooks/useLibrary'
import { getErrorMessage } from '../utils/errors'
import { formatDateTime, formatPrice } from '../utils/format'
import styles from './CartPage.module.css'

const ORDERS_KEY = ['orders']

// Sum of prices as strings ("9.99"): count in cents so 0.1 + 0.2 stays exact.
function sumPrices(prices: string[]): string {
  const cents = prices.reduce((total, price) => total + Math.round(Number(price) * 100), 0)
  return (cents / 100).toFixed(2)
}

function GuestCart() {
  return (
    <div className="page narrow">
      <h1>Корзина</h1>
      <p>Щоб купувати фільми, створіть акаунт — це займе хвилину.</p>
      <div className={styles.buttons}>
        <Link to="/register" className="btn">
          Зареєструватися
        </Link>
        <Link to="/login?next=%2Fcart" className="btn btn-secondary">
          Увійти
        </Link>
      </div>
    </div>
  )
}

function PendingOrders({ orders }: { orders: Order[] }) {
  const pay = useMutation({
    mutationFn: (orderId: number) => checkoutOrder(orderId),
    // Stripe hosted Checkout: leave our site; Stripe returns to /payment/success.
    onSuccess: ({ checkout_url }) => window.location.assign(checkout_url),
  })

  if (orders.length === 0) return null

  return (
    <section className={styles.section}>
      <h2>Неоплачені замовлення</h2>
      {pay.isError && <p className="notice notice-error">{getErrorMessage(pay.error)}</p>}
      <div className={styles.orders}>
        {orders.map((order) => (
          <article key={order.id} className={styles.order}>
            <header className={styles.orderHeader}>
              <h3>Замовлення #{order.id}</h3>
              <span className="muted">{formatDateTime(order.created_at)}</span>
            </header>
            <ul className={styles.orderItems}>
              {order.items.map((item) => (
                <li key={item.id}>
                  <Link to={`/movies/${item.movie.id}`}>{item.movie.name}</Link>
                  <span>{formatPrice(item.price_at_order)}</span>
                </li>
              ))}
            </ul>
            <footer className={styles.orderFooter}>
              <strong>Разом {formatPrice(order.total_amount)}</strong>
              <button
                type="button"
                className="btn"
                disabled={pay.isPending}
                onClick={() => pay.mutate(order.id)}
              >
                {pay.isPending && pay.variables === order.id ? 'Переходимо до оплати…' : 'Оплатити'}
              </button>
            </footer>
          </article>
        ))}
      </div>
      <p className="hint">
        Оплата проходить на захищеній сторінці Stripe. Перед оплатою вже придбані фільми автоматично
        прибираються із замовлення.
      </p>
    </section>
  )
}

export function CartPage() {
  const { status } = useAuth()
  const queryClient = useQueryClient()
  const { cartItems, cartLoading } = useLibrary()
  const [excluded, setExcluded] = useState<NamedEntity[]>([])

  // All my orders on one page (100 is the API max) - only pending ones are shown.
  const orders = useQuery({
    queryKey: ORDERS_KEY,
    queryFn: () => listOrders(1, 100),
    enabled: status === 'user',
  })
  const pendingOrders = (orders.data?.items ?? []).filter((order) => order.status === 'pending')

  // Movie id -> number of a pending order with it ("already in order #N").
  const orderOfMovie = new Map<number, number>()
  for (const order of pendingOrders) {
    for (const item of order.items) orderOfMovie.set(item.movie.id, order.id)
  }

  const remove = useMutation({
    mutationFn: removeFromCart,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CART_KEY }),
  })
  const clear = useMutation({
    mutationFn: clearCart,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CART_KEY }),
  })
  const order = useMutation({
    mutationFn: createOrder,
    onSuccess: async (created) => {
      setExcluded(created.excluded_movies)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: CART_KEY }),
        queryClient.invalidateQueries({ queryKey: ORDERS_KEY }),
      ])
    },
    // e.g. all movies already purchased: the list of purchased ids is outdated.
    onError: () => queryClient.invalidateQueries({ queryKey: PURCHASED_IDS_KEY }),
  })

  if (status === 'loading') return <Spinner />
  if (status === 'guest') return <GuestCart />

  return (
    <div className="page">
      <h1>Корзина</h1>
      <div className={styles.layout}>
        <section className={styles.section}>
          {order.isSuccess && (
            <div className="notice notice-success">
              <p>Замовлення оформлено — його можна оплатити нижче.</p>
              {excluded.length > 0 && (
                <p>
                  Не включено, бо вже придбано: {excluded.map((movie) => movie.name).join(', ')}.
                </p>
              )}
            </div>
          )}
          {order.isError && <p className="notice notice-error">{getErrorMessage(order.error)}</p>}

          {cartLoading && <Spinner />}
          {!cartLoading && cartItems.length === 0 && (
            <div className={styles.empty}>
              <p>У корзині поки немає фільмів.</p>
              <Link to="/movies" className="btn btn-secondary">
                Перейти до каталогу
              </Link>
            </div>
          )}

          {cartItems.length > 0 && (
            <>
              <ul className={styles.items}>
                {cartItems.map((movie) => (
                  <li key={movie.id} className={styles.item}>
                    <div>
                      <Link to={`/movies/${movie.id}`} className={styles.itemTitle}>
                        {movie.name}
                      </Link>
                      <p className="muted">
                        {movie.year}
                        {movie.genres.length > 0 &&
                          `, ${movie.genres.map((genre) => genre.name).join(', ')}`}
                      </p>
                      {orderOfMovie.has(movie.id) && (
                        <p className={styles.inOrder}>
                          Вже в замовленні #{orderOfMovie.get(movie.id)}
                        </p>
                      )}
                    </div>
                    <span className={styles.itemPrice}>{formatPrice(movie.price)}</span>
                    <button
                      type="button"
                      className="btn btn-secondary btn-small"
                      disabled={remove.isPending}
                      onClick={() => remove.mutate(movie.id)}
                    >
                      Прибрати
                    </button>
                  </li>
                ))}
              </ul>
              <div className={styles.summary}>
                <p className={styles.total}>
                  Разом <strong>{formatPrice(sumPrices(cartItems.map((m) => m.price)))}</strong>
                </p>
                <div className={styles.buttons}>
                  <button
                    type="button"
                    className="btn btn-danger"
                    disabled={clear.isPending}
                    onClick={() => clear.mutate()}
                  >
                    Очистити корзину
                  </button>
                  <button
                    type="button"
                    className="btn"
                    disabled={order.isPending}
                    onClick={() => order.mutate()}
                  >
                    Оформити замовлення
                  </button>
                </div>
              </div>
            </>
          )}
        </section>

        <PendingOrders orders={pendingOrders} />
      </div>
    </div>
  )
}
