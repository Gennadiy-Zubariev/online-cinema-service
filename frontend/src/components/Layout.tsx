import { Outlet } from 'react-router'

import { Navbar } from './Navbar'

export function Layout() {
  return (
    <>
      <Navbar />
      <main>
        <Outlet />
      </main>
    </>
  )
}
