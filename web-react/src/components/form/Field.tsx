import { type ReactNode } from 'react'

// Campo de formulario: label opcional arriba, error abajo con el token único.
export default function Field({ label, error, children }: { label?: string; error?: string; children: ReactNode }) {
  return (
    <label style={{ display: 'grid', gap: 4, fontSize: 13, color: 'var(--color-sage)' }}>
      {label}
      {children}
      {error && <span style={{ fontSize: 12, color: 'var(--color-error)', marginTop: 2 }}>{error}</span>}
    </label>
  )
}
