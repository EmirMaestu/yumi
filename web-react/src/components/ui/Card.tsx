import { type ReactNode } from 'react'
export default function Card({ children, style }: { children: ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{ border: '1px solid var(--color-mist)', borderRadius: 'var(--radius-card)', padding: 18, ...style }}>
      {children}
    </div>
  )
}
