import styles from './Poster.module.css'

// Vertical 2:3 poster; without an uploaded image - the title on a dark plate.
export function Poster({ url, title }: { url: string | null | undefined; title: string }) {
  if (url) {
    return <img className={styles.poster} src={url} alt={`Постер: ${title}`} loading="lazy" />
  }
  return (
    <div className={`${styles.poster} ${styles.placeholder}`} aria-label={`Без постера: ${title}`}>
      <span>{title}</span>
    </div>
  )
}
