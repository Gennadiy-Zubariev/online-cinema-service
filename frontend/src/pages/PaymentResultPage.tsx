import { useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { Link } from 'react-router'

import { AuthCard } from '../components/AuthCard'
import { CART_KEY, PURCHASED_IDS_KEY } from '../hooks/useLibrary'

// Stripe redirects here after payment. The redirect is NOT a proof of payment and
// comes before the webhook - so "purchased" is refreshed a few seconds later.
export function PaymentSuccessPage() {
  const queryClient = useQueryClient()

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void queryClient.invalidateQueries({ queryKey: PURCHASED_IDS_KEY })
      void queryClient.invalidateQueries({ queryKey: ['orders'] })
      void queryClient.invalidateQueries({ queryKey: CART_KEY })
    }, 4000)
    return () => window.clearTimeout(timer)
  }, [queryClient])

  return (
    <AuthCard title="Оплата пройшла">
      <p>
        Дякуємо! Фільми зʼявляться в розділі «Придбані» за кілька секунд — щойно Stripe підтвердить
        платіж. Підтвердження також прийде на пошту.
      </p>
      <Link to="/account?tab=purchased" className="btn">
        Мої придбані фільми
      </Link>
    </AuthCard>
  )
}

export function PaymentCancelPage() {
  return (
    <AuthCard title="Оплату скасовано">
      <p>Гроші не списано. Замовлення збережене — його можна оплатити пізніше.</p>
      <p className="muted">Якщо картку відхилили, спробуйте інший спосіб оплати або іншу картку.</p>
      <Link to="/cart" className="btn">
        Повернутися до корзини
      </Link>
    </AuthCard>
  )
}
