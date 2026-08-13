import type { QuickType } from '../components/QuickAddSheet'

// Catálogo de atajos del home ("TUS ATAJOS"). El usuario elige cuáles y en qué orden
// (hasta 6) desde el editor; se persiste en localStorage. Cada atajo abre una ruta o
// la hoja "Agregar" en un tipo.
export interface ShortcutDef {
  id: string
  label: string
  sub: string
  icon: string
  action: { type: 'route'; to: string } | { type: 'add'; addType: QuickType }
  shareable?: boolean   // se puede compartir con la pareja (muestra scope "Con <pareja>")
}

export const SHORTCUT_CATALOG: ShortcutDef[] = [
  { id: 'super', label: 'Sumar al súper', sub: 'Lista compartida', icon: 'ti-shopping-cart', action: { type: 'route', to: '/listas' }, shareable: true },
  { id: 'recordar', label: 'Recordame algo', sub: 'Nuevo recordatorio', icon: 'ti-bell', action: { type: 'add', addType: 'recordatorio' }, shareable: true },
  { id: 'evento', label: 'Nuevo evento', sub: 'Agenda', icon: 'ti-calendar', action: { type: 'add', addType: 'evento' }, shareable: true },
  { id: 'nota', label: 'Anotar', sub: 'Nueva nota', icon: 'ti-note', action: { type: 'add', addType: 'nota' } },
  { id: 'tarea', label: 'Nueva tarea', sub: 'Pendiente', icon: 'ti-checkbox', action: { type: 'add', addType: 'tarea' }, shareable: true },
  { id: 'movimientos', label: 'Ver movimientos', sub: 'Finanzas', icon: 'ti-arrows-left-right', action: { type: 'route', to: '/movimientos' } },
  { id: 'tarjeta-pago', label: 'Registrar pago de tarjeta', sub: 'Tarjetas', icon: 'ti-credit-card', action: { type: 'route', to: '/tarjetas' } },
  { id: 'habito', label: 'Marcar hábito', sub: 'Hábitos', icon: 'ti-flame', action: { type: 'route', to: '/habitos' } },
]

export const MAX_SHORTCUTS = 6
const KEY = 'yumi_shortcuts'
const DEFAULT_IDS = ['super', 'recordar', 'evento', 'nota']

export function shortcutById(id: string): ShortcutDef | undefined {
  return SHORTCUT_CATALOG.find((s) => s.id === id)
}

export function getShortcutIds(): string[] {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || 'null')
    if (Array.isArray(v) && v.length) return v.filter((id) => SHORTCUT_CATALOG.some((s) => s.id === id))
  } catch { /* ignore */ }
  return DEFAULT_IDS
}

export function setShortcutIds(ids: string[]): void {
  try { localStorage.setItem(KEY, JSON.stringify(ids.slice(0, MAX_SHORTCUTS))) } catch { /* ignore */ }
}
