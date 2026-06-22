export default function AlertPill({ children }: { children: React.ReactNode }) {
  return (
    <span style={{
      background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', fontSize: 10.5,
      fontWeight: 600, padding: '2px 8px', borderRadius: 9999, display: 'inline-block',
    }}>{children}</span>
  )
}
