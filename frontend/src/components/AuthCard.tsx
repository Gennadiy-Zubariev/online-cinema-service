import type { ReactNode } from 'react'

import styles from './AuthCard.module.css'

// Centered card for login, registration and password pages.
export function AuthCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className={styles.wrap}>
      <section className={styles.card}>
        <h1 className={styles.title}>{title}</h1>
        {children}
      </section>
    </div>
  )
}
