export interface NavItem { to: string; label: string; icon: string }

// Barra inferior (mobile): 3 tabs + el FAB "+" (al medio) + el botón "Más" (abre hoja).
export const BOTTOM_NAV: NavItem[] = [
  { to: '/', label: 'Inicio', icon: 'ti-sparkles' },
  { to: '/finanzas', label: 'Finanzas', icon: 'ti-coin' },
  { to: '/agenda', label: 'Agenda', icon: 'ti-calendar' },
]

// Grilla de la hoja "Más" (Yo va aparte, en el encabezado de la hoja).
export const MORE_LINKS: NavItem[] = [
  { to: '/tareas', label: 'Tareas', icon: 'ti-checkbox' },
  { to: '/listas', label: 'Listas', icon: 'ti-shopping-cart' },
  { to: '/habitos', label: 'Hábitos', icon: 'ti-flame' },
  { to: '/notas', label: 'Notas', icon: 'ti-note' },
]

// Rieles de acceso (chips) que exponen las sub-secciones DENTRO de cada hub,
// de forma visible (reemplazan al drawer lateral como vía de descubrimiento).
export const HOY_RAIL: NavItem[] = [
  { to: '/agenda', label: 'Agenda', icon: 'ti-calendar' },
  { to: '/tareas', label: 'Tareas', icon: 'ti-checkbox' },
  { to: '/listas', label: 'Listas', icon: 'ti-shopping-cart' },
  { to: '/habitos', label: 'Hábitos', icon: 'ti-flame' },
  { to: '/notas', label: 'Notas', icon: 'ti-note' },
]

export const FINANZAS_RAIL: NavItem[] = [
  { to: '/movimientos', label: 'Movimientos', icon: 'ti-arrows-left-right' },
  { to: '/tarjetas', label: 'Tarjetas', icon: 'ti-credit-card' },
  { to: '/cuentas', label: 'Cuentas', icon: 'ti-wallet' },
  { to: '/categorias', label: 'Categorías', icon: 'ti-tags' },
  { to: '/recurrentes', label: 'Recurrentes', icon: 'ti-repeat' },
]

export interface NavGroup { title?: string; items: NavItem[] }

// Sidebar (desktop): misma taxonomía que la barra mobile (Asistente / Finanzas / Yo).
export const SIDEBAR_GROUPS: NavGroup[] = [
  {
    title: 'Asistente',
    items: [
      { to: '/', label: 'Inicio', icon: 'ti-sparkles' },
      ...HOY_RAIL,
    ],
  },
  {
    title: 'Finanzas',
    items: [
      { to: '/finanzas', label: 'Resumen', icon: 'ti-coin' },
      ...FINANZAS_RAIL,
    ],
  },
  {
    items: [
      { to: '/yo', label: 'Yo', icon: 'ti-user' },
    ],
  },
]
