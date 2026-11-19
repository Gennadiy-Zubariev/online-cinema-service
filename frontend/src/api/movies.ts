import { api } from './client'
import type {
  CatalogParams,
  Comment,
  CommentList,
  GenreList,
  Movie,
  MovieCreate,
  MovieDetail,
  MovieList,
  MovieUpdate,
  NamedEntity,
  NamedEntityList,
} from './types'

// --- catalog ---

export function listMovies(params: CatalogParams) {
  return api<MovieList>('/movies', { query: { ...params } })
}

export function listFavorites(params: CatalogParams) {
  return api<MovieList>('/favorites', { query: { ...params } })
}

export function listPurchased(params: CatalogParams) {
  return api<MovieList>('/purchased', { query: { ...params } })
}

export function getMovie(movieId: number) {
  return api<MovieDetail>(`/movies/${movieId}`)
}

export function listGenres() {
  return api<GenreList>('/genres', { query: { page_size: 100 } })
}

// --- user actions ---

export function addFavorite(movieId: number) {
  return api(`/movies/${movieId}/favorite`, { method: 'PUT' })
}

export function removeFavorite(movieId: number) {
  return api(`/movies/${movieId}/favorite`, { method: 'DELETE' })
}

export function setReaction(movieId: number, isLike: boolean) {
  return api(`/movies/${movieId}/reaction`, { method: 'PUT', body: { is_like: isLike } })
}

export function removeReaction(movieId: number) {
  return api(`/movies/${movieId}/reaction`, { method: 'DELETE' })
}

export function setRating(movieId: number, score: number) {
  return api(`/movies/${movieId}/rating`, { method: 'PUT', body: { score } })
}

export function removeRating(movieId: number) {
  return api(`/movies/${movieId}/rating`, { method: 'DELETE' })
}

// --- comments ---

export function listComments(movieId: number, page: number, pageSize: number) {
  return api<CommentList>(`/movies/${movieId}/comments`, {
    query: { page, page_size: pageSize },
  })
}

export function addComment(movieId: number, text: string, parentId: number | null = null) {
  return api<Comment>(`/movies/${movieId}/comments`, {
    method: 'POST',
    body: { text, parent_id: parentId },
  })
}

export function likeComment(commentId: number) {
  return api(`/comments/${commentId}/like`, { method: 'PUT' })
}

// --- moderator: movies ---

export function createMovie(data: MovieCreate) {
  return api<Movie>('/movies', { method: 'POST', body: data })
}

export function updateMovie(movieId: number, data: MovieUpdate) {
  return api<Movie>(`/movies/${movieId}`, { method: 'PATCH', body: data })
}

export function deleteMovie(movieId: number) {
  return api(`/movies/${movieId}`, { method: 'DELETE' })
}

export function uploadPoster(movieId: number, file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return api<Movie>(`/movies/${movieId}/poster`, { method: 'PUT', formData })
}

// --- moderator: reference lists (genres, stars, directors, certifications) ---

export type EntityKind = 'genres' | 'stars' | 'directors' | 'certifications'

export function listEntities(kind: EntityKind, page: number, pageSize: number) {
  return api<NamedEntityList>(`/${kind}`, { query: { page, page_size: pageSize } })
}

export function createEntity(kind: EntityKind, name: string) {
  return api<NamedEntity>(`/${kind}`, { method: 'POST', body: { name } })
}

export function updateEntity(kind: EntityKind, entityId: number, name: string) {
  return api<NamedEntity>(`/${kind}/${entityId}`, { method: 'PATCH', body: { name } })
}

export function deleteEntity(kind: EntityKind, entityId: number) {
  return api(`/${kind}/${entityId}`, { method: 'DELETE' })
}
