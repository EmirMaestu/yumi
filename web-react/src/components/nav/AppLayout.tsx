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
      <div style={{ display: 'flex', maxWidth: 1100, margin: '0 auto', minHeight: '100%' }}>
        <Sidebar onAdd={() => setAddOpen(true)} />
        <main style={{ flex: 1, padding: 24 }}>{children ?? <Outlet />}</main>
        {addOpen && <QuickAddSheet onClose={() => setAddOpen(false)} />}
      </div>
    )
  }
  return (
    <div style={{ minHeight: '100%', display: 'flex', flexDirection: 'column', maxWidth: 480, margin: '0 auto' }}>
      <TopBar onMenu={() => setMenuOpen(true)} />
      <main style={{ flex: 1 }}>{children ?? <Outlet />}</main>
      <BottomNav onAdd={() => setAddOpen(true)} />
      <MenuDrawer open={menuOpen} onClose={() => setMenuOpen(false)} />
      {addOpen && <QuickAddSheet onClose={() => setAddOpen(false)} />}
    </div>
  )
}
