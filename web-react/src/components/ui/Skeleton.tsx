export default function Skeleton({ h = 16, w = '100%' }: { h?: number; w?: number | string }) {
  return <div aria-hidden style={{ height: h, width: w, background: 'var(--color-mist)', opacity: 0.5, borderRadius: 6 }} />
}
