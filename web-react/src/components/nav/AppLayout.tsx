import { type ReactNode, useEffect, useState } from 'react'
import { Outlet } from 'react-router-dom'
import TopBar from './TopBar'
import BottomNav from './BottomNav'
import Sidebar from './Sidebar'
import MenuDrawer from './MenuDrawer'
import QuickAddSheet from '../QuickAddSheet'

export default function AppLayout({ children }: { children?: ReactNode }) {
  const [isDesktop, setIsDesktop] = useState(() => window.innerWidth >= 1024)
  const [menuOpen, setMenuOpen] = useState(false)
  const [addOpen, setAddOpen] = useState(false)

  useEffect(() => {
    const mq = window.matchMedia('(min-width: 1024px)')
    const fn = () => setIsDesktop(mq.matches)
    mq.addEventListener('change', fn)
    return () => mq.removeEventListener('change', fn)
  }, [])

  if (isDesktop) {
    return (
      <div style={{ display: 'flex', maxWidth: 1100, margin: '0 auto', minHeight: '100vh' }}>
        <Sidebar onAdd={() => setAddOpen(true)} />
        <main style={{ flex: 1, padding: 24 }}>{children ?? <Outlet />}</main>
        <QuickAddSheet open={addOpen} onClose={() => setAddOpen(false)} />
      </div>
    )
  }
  return (
    <div style={{ maxWidth: 480, margin: '0 auto', minHeight: '100vh' }}>
      <div style={{ position: 'sticky', top: 0, zIndex: 30, background: 'var(--color-linen)' }}>
        <TopBar onMenu={() => setMenuOpen(true)} />
      </div>
      <main style={{ paddingBottom: 96 }}>{children ?? <Outlet />}</main>
      <BottomNav onAdd={() => setAddOpen(true)} />
      <MenuDrawer open={menuOpen} onClose={() => setMenuOpen(false)} />
      <QuickAddSheet open={addOpen} onClose={() => setAddOpen(false)} />
    </div>
  )
}
