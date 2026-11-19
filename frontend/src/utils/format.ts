// Prices come from the API as strings ("9.99") - Decimal is not a float.
export function formatPrice(price: string | null | undefined): string {
  return price ? `$${price}` : '—'
}

export function formatDuration(minutes: number): string {
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  if (hours === 0) return `${rest} хв`
  return rest ? `${hours} год ${rest} хв` : `${hours} год`
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('uk-UA', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('uk-UA', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}
