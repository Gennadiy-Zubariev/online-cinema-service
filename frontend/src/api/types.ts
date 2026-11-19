// Short names for backend schemas. schema.d.ts is generated: `npm run gen:api`
// (the backend must be running) - never edit it by hand.
import type { components } from './schema'

type Schemas = components['schemas']

export type MessageResponse = Schemas['MessageResponse']
export type AccessTokenResponse = Schemas['AccessTokenResponse']
export type Profile = Schemas['ProfileResponse']
export type ProfileUpdate = Schemas['ProfileUpdateRequest']
export type Gender = Schemas['GenderEnum']
export type UserGroup = Schemas['UserGroupEnum']
export type AdminUser = Schemas['UserAdminResponse']
export type UserList = Schemas['UserListResponse']

export type NamedEntity = Schemas['NamedEntityResponse']
export type NamedEntityList = Schemas['NamedEntityListResponse']
export type Genre = Schemas['GenreResponse']
export type GenreList = Schemas['GenreListResponse']

export type MovieListItem = Schemas['MovieListItemResponse']
export type MovieList = Schemas['MovieListResponse']
export type Movie = Schemas['MovieResponse']
export type MovieDetail = Schemas['MovieDetailResponse']
export type MovieCreate = Schemas['MovieCreateRequest']
export type MovieUpdate = Schemas['MovieUpdateRequest']

export type Comment = Schemas['CommentResponse']
export type CommentWithReplies = Schemas['CommentWithRepliesResponse']
export type CommentList = Schemas['CommentListResponse']

export type CartMovie = Schemas['CartMovieResponse']
export type Cart = Schemas['CartResponse']

export type Order = Schemas['OrderResponse']
export type OrderCreate = Schemas['OrderCreateResponse']
export type OrderList = Schemas['OrderListResponse']
export type Checkout = Schemas['CheckoutResponse']

// Every paginated list of the API has the same shape.
export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

// Catalog query: the same parameters for /movies, /favorites and /purchased.
export interface CatalogParams {
  search?: string
  genre_id?: number
  year_from?: number
  year_to?: number
  imdb_min?: number
  imdb_max?: number
  sort_by?: 'id' | 'price' | 'year' | 'votes' | 'imdb'
  order?: 'asc' | 'desc'
  page?: number
  page_size?: number
}
