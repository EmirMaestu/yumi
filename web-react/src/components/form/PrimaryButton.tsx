import { type ButtonHTMLAttributes, type ReactNode } from 'react'

const style: React.CSSProperties = {
  background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none',
  borderRadius: 10, padding: '14px', fontWeight: 500, cursor: 'pointer',
}

// Botón primario con estado de carga (deshabilita + texto "Guardando…").
export default function PrimaryButton({ loading, children, ...rest }: { loading?: boolean; children: ReactNode } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button {...rest} disabled={loading || rest.disabled} style={{ ...style, ...rest.style }}>
      {loading ? 'Guardando…' : children}
    </button>
  )
}
