import { ApiError } from '../api/client'

// Text for the user from any error of a request.
export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message
  }
  return 'Не вдалося зʼєднатися з сервером. Спробуйте ще раз.'
}
