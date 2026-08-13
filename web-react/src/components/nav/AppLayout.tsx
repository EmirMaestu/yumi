import { type ReactNode, useEffect, useState } from 'react'
import { Outlet } from 'react-router-dom'
import TopBar from './TopBar'
import BottomNav from './BottomNav'
import Sidebar from './Sidebar'
import MoreSheet from './MoreSheet'
import QuickAddSheet, { type QuickType } from '../QuickAddSheet'
import KeypadExpenseSheet from '../KeypadExpenseSheet'

// Contexto para que las pantallas (ej. las acciones rápidas del Inicio) abran
// la hoja "Agregar" en el tipo que quieran, o el teclado de gasto rápido (1c).
export interface LayoutCtx { openAdd: (t?: QuickType) => void; openExpense: () => void }

export default function AppLayout({ children }: { children?: ReactNode }) {
  const [isDesktop, setIsDesktop] = useState(() => window.innerWidth >= 1024)
  const [addOpen, setAddOpen] = useState(false)
  const [addType, setAddType] = useState<QuickType>('gasto')
  const [keypadOpen, setKeypadOpen] = useState(false)
  const [moreOpen, setMoreOpen] = useState(false)
  const openAdd = (t: QuickType = 'gasto') => { setAddType(t); setAddOpen(true) }
  const openExpense = () => setKeypadOpen(true)
  const ctx: LayoutCtx = { openAdd, openExpense }
  const keypad = (
    <KeypadExpenseSheet open={keypadOpen} onClose={() => setKeypadOpen(false)}
      onChangeType={() => { setKeypadOpen(false); openAdd('gasto') }} />
  )

  useEffect(() => {
    const mq = window.matchMedia('(min-width: 1024px)')
    const fn = () => setIsDesktop(mq.matches)
    mq.addEventListener('change', fn)
    return () => mq.removeEventListener('change', fn)
  }, [])

  if (isDesktop) {
    return (
      <div style={{ display: 'flex', maxWidth: 1100, margin: '0 auto', minHeight: '100vh' }}>
        <Sidebar onAdd={() => openAdd()} />
        <main style={{ flex: 1, padding: 24 }}>{children ?? <Outlet context={ctx} />}</main>
        <QuickAddSheet open={addOpen} initialType={addType} onClose={() => setAddOpen(false)} />
        {keypad}
      </div>
    )
  }
  return (
    <div style={{ maxWidth: 480, margin: '0 auto', minHeight: '100vh' }}>
      <div style={{ position: 'sticky', top: 0, zIndex: 30, background: 'var(--color-linen)' }}>
        <TopBar />
      </div>
      <main style={{ paddingBottom: 96 }}>{children ?? <Outlet context={ctx} />}</main>
      <BottomNav onAdd={() => openAdd()} onMore={() => setMoreOpen(true)} />
      <MoreSheet open={moreOpen} onClose={() => setMoreOpen(false)} />
      <QuickAddSheet open={addOpen} initialType={addType} onClose={() => setAddOpen(false)} />
      {keypad}
    </div>
  )
}
