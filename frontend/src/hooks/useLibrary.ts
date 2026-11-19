// What the logged-in user already has: favorites, purchased movies, cart.
// The API has no "is favorite / is purchased" flags in movie lists, so after login
// we load the ids once and mark cards and buttons from memory.
import { useQuery } from '@tanstack/react-query'

import { listFavorites, listPurchased } from '../api/movies'
import { getCart } from '../api/shop'
import type { CatalogParams, MovieList } from '../api/types'
import { useAuth } from '../auth/useAuth'

const MAX_PAGE_SIZE = 100

// Walk through all pages (100 movies each) and collect movie ids.
async function fetchAllIds(fetchPage: (params: CatalogParams) => Promise<MovieList>) {
  const ids = new Set<number>()
  for (let page = 1; ; page++) {
    const data = await fetchPage({ page, page_size: MAX_PAGE_SIZE })
    data.items.forEach((movie) => ids.add(movie.id))
    if (page * MAX_PAGE_SIZE >= data.total) {
      return ids
    }
  }
}

// Query keys - also used to refresh the data after an action (invalidateQueries).
export const FAVORITE_IDS_KEY = ['favorite-ids']
export const PURCHASED_IDS_KEY = ['purchased-ids']
export const CART_KEY = ['cart']

const EMPTY = new Set<number>()

export function useLibrary() {
  const { status } = useAuth()
  const enabled = status === 'user'

  const favorites = useQuery({
    queryKey: FAVORITE_IDS_KEY,
    queryFn: () => fetchAllIds(listFavorites),
    enabled,
  })
  const purchased = useQuery({
    queryKey: PURCHASED_IDS_KEY,
    queryFn: () => fetchAllIds(listPurchased),
    enabled,
  })
  const cart = useQuery({ queryKey: CART_KEY, queryFn: getCart, enabled })

  const cartItems = cart.data?.items ?? []
  return {
    favoriteIds: favorites.data ?? EMPTY,
    purchasedIds: purchased.data ?? EMPTY,
    cartIds: new Set(cartItems.map((movie) => movie.id)),
    cartItems,
    cartLoading: cart.isLoading,
  }
}
