import styles from './Pagination.module.css'

interface PaginationProps {
  page: number
  pageSize: number
  total: number
  onChange: (page: number) => void
}

// Page numbers to show: first, last and two around the current one; null = "…".
function visiblePages(current: number, last: number): (number | null)[] {
  const pages: (number | null)[] = []
  for (let page = 1; page <= last; page++) {
    if (page === 1 || page === last || Math.abs(page - current) <= 2) {
      pages.push(page)
    } else if (pages[pages.length - 1] !== null) {
      pages.push(null)
    }
  }
  return pages
}

export function Pagination({ page, pageSize, total, onChange }: PaginationProps) {
  const last = Math.ceil(total / pageSize)
  if (last <= 1) return null

  function go(target: number) {
    onChange(target)
    window.scrollTo({ top: 0 })
  }

  return (
    <nav className={styles.pagination} aria-label="Сторінки">
      <button type="button" disabled={page <= 1} onClick={() => go(page - 1)}>
        Назад
      </button>
      {visiblePages(page, last).map((item, index) =>
        item === null ? (
          <span key={`gap-${index}`} className={styles.gap}>
            …
          </span>
        ) : (
          <button
            key={item}
            type="button"
            className={item === page ? styles.current : undefined}
            aria-current={item === page ? 'page' : undefined}
            onClick={() => go(item)}
          >
            {item}
          </button>
        ),
      )}
      <button type="button" disabled={page >= last} onClick={() => go(page + 1)}>
        Далі
      </button>
    </nav>
  )
}
