import { Link } from 'react-router'

import styles from './Tabs.module.css'

interface TabsProps {
  tabs: readonly { id: string; label: string }[]
  activeId: string
  // Link of a tab: `${basePath}?tab=<id>` - the active tab lives in the URL.
  basePath: string
  label: string
}

export function Tabs({ tabs, activeId, basePath, label }: TabsProps) {
  return (
    <nav className={styles.tabs} aria-label={label}>
      {tabs.map((item) => (
        <Link
          key={item.id}
          to={`${basePath}?tab=${item.id}`}
          className={item.id === activeId ? styles.tabActive : styles.tab}
          aria-current={item.id === activeId ? 'page' : undefined}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  )
}
