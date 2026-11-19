// Cart, orders and payments - the purchase flow.
import { api } from './client'
import type { Cart, Checkout, OrderCreate, OrderList } from './types'

export function getCart() {
  return api<Cart>('/cart/items')
}

export function addToCart(movieId: number) {
  return api(`/cart/items/${movieId}`, { method: 'PUT' })
}

export function removeFromCart(movieId: number) {
  return api(`/cart/items/${movieId}`, { method: 'DELETE' })
}

export function clearCart() {
  return api('/cart/items', { method: 'DELETE' })
}

export function createOrder() {
  return api<OrderCreate>('/orders', { method: 'POST' })
}

export function listOrders(page: number, pageSize: number) {
  return api<OrderList>('/orders', { query: { page, page_size: pageSize } })
}

// Returns the Stripe Checkout URL; the browser is redirected there.
export function checkoutOrder(orderId: number) {
  return api<Checkout>(`/orders/${orderId}/checkout`, { method: 'POST' })
}
