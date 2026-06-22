export default function TickMark({ width = 50 }: { width?: number }) {
  return <div style={{ width, height: 2, background: 'var(--color-voltage)' }} />
}
