// Preferencia de tema: claro / oscuro / seguir el sistema. Persistida en localStorage.
// Aplica html[data-theme="light"|"dark"] (los overrides viven en styles/theme.css).
export type ThemePref = 'system' | 'light' | 'dark'
const KEY = 'yumi.theme'

export function getThemePref(): ThemePref {
  const v = localStorage.getItem(KEY)
  return v === 'light' || v === 'dark' || v === 'system' ? v : 'system'
}

function effective(p: ThemePref): 'light' | 'dark' {
  if (p === 'system') return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  return p
}

export function applyTheme() {
  document.documentElement.setAttribute('data-theme', effective(getThemePref()))
}

export function setThemePref(p: ThemePref) {
  localStorage.setItem(KEY, p)
  applyTheme()
}

export function initTheme() {
  applyTheme()
  // Si está en "sistema", seguir los cambios del SO en vivo.
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (getThemePref() === 'system') applyTheme()
  })
}
