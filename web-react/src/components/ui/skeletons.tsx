// Per-view skeleton loaders using the .nf-skel shimmer class

function Skel({ h, w = '100%', style }: { h: number; w?: number | string; style?: React.CSSProperties }) {
  return <span aria-hidden className="nf-skel" style={{ height: h, width: w, display: 'block', ...style }} />
}

export function InicioSkeleton() {
  return (
    <div style={{ padding: '8px 4px 24px' }}>
      {/* Hero */}
      <section style={{ padding: '8px 18px 6px', display: 'grid', gap: 10 }}>
        <Skel h={11} w="38%" />
        <Skel h={54} w="60%" />
        <Skel h={13} w="44%" />
        <Skel h={18} w={18} style={{ borderRadius: '50%' }} />
      </section>
      {/* Stats row */}
      <section style={{ display: 'flex', gap: 6, padding: '16px 18px 6px' }}>
        <Skel h={44} style={{ flex: 1 }} />
        <Skel h={44} style={{ flex: 1 }} />
        <Skel h={44} style={{ flex: 1 }} />
      </section>
      {/* Card block */}
      <div style={{ padding: '12px 18px 0' }}>
        <Skel h={140} style={{ borderRadius: 14 }} />
      </div>
      {/* Category bars */}
      <section style={{ padding: '20px 18px 8px', display: 'grid', gap: 10 }}>
        {[82, 64, 71, 55].map((w, i) => (
          <Skel key={i} h={18} w={`${w}%`} />
        ))}
      </section>
    </div>
  )
}

export function MovimientosSkeleton() {
  return (
    <div style={{ padding: '14px 18px 24px' }}>
      {/* Header */}
      <Skel h={14} w="30%" style={{ marginBottom: 16 }} />
      {/* Filter pills */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <Skel h={36} w={90} style={{ borderRadius: 10 }} />
        <Skel h={36} w={110} style={{ borderRadius: 10 }} />
        <Skel h={36} w={120} style={{ borderRadius: 10 }} />
      </div>
      {/* List rows */}
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '12px 0', borderBottom: '1px solid var(--color-mist)' }}>
          <div style={{ flex: 1, display: 'grid', gap: 6 }}>
            <Skel h={14} w="50%" />
            <Skel h={11} w="70%" />
          </div>
          <Skel h={15} w={68} style={{ alignSelf: 'center', borderRadius: 6 }} />
        </div>
      ))}
    </div>
  )
}

export function CuentasSkeleton() {
  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 12 }}>
      <Skel h={14} w="28%" />
      {[0, 1, 2, 3].map((i) => (
        <div key={i} style={{ borderRadius: 14, padding: 16, border: '1px solid var(--color-mist)', display: 'grid', gap: 10 }}>
          <Skel h={15} w="40%" />
          <Skel h={28} w="55%" />
        </div>
      ))}
    </div>
  )
}

export function CategoriasSkeleton() {
  return (
    <div style={{ padding: '14px 18px 24px' }}>
      {/* Header */}
      <Skel h={14} w="30%" style={{ marginBottom: 16 }} />
      {/* Category rows */}
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--color-mist)' }}>
          <Skel h={14} w="45%" />
          <Skel h={15} w={56} style={{ borderRadius: 6 }} />
        </div>
      ))}
    </div>
  )
}

export function TarjetasSkeleton() {
  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 14 }}>
      <Skel h={12} w="35%" />
      {[0, 1].map((i) => (
        <div key={i} style={{ borderRadius: 14, padding: 16, border: '1px solid var(--color-mist)', display: 'grid', gap: 12 }}>
          <Skel h={16} w="45%" />
          <Skel h={10} w="30%" />
          <Skel h={30} w="52%" />
          <Skel h={150} style={{ borderRadius: 10 }} />
        </div>
      ))}
    </div>
  )
}

export function TarjetaDetalleSkeleton() {
  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 16 }}>
      {/* Header */}
      <div style={{ display: 'grid', gap: 8 }}>
        <Skel h={13} w="15%" />
        <Skel h={22} w="50%" />
      </div>
      {/* Summary card */}
      <div style={{ borderRadius: 14, padding: 16, border: '1px solid var(--color-mist)', display: 'grid', gap: 12 }}>
        <Skel h={11} w="25%" />
        <Skel h={34} w="55%" />
        <div style={{ height: 1, background: 'var(--color-mist)' }} />
        <Skel h={120} style={{ borderRadius: 10 }} />
      </div>
      {/* Cuota rows */}
      {[0, 1].map((i) => (
        <div key={i} style={{ borderRadius: 14, padding: 14, border: '1px solid var(--color-mist)', display: 'grid', gap: 8 }}>
          <Skel h={14} w="60%" />
          <Skel h={11} w="40%" />
        </div>
      ))}
    </div>
  )
}
