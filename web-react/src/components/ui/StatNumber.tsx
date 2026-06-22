export default function StatNumber({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ flex: 1 }}>
      <div className="cap" style={{ fontSize: 10.5 }}>{label}</div>
      <div style={{ fontSize: 15, fontWeight: 500, marginTop: 3 }}>{children}</div>
    </div>
  )
}
