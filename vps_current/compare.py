"""
Comparacion periodo-vs-periodo. Modulo PURO: recibe filas ya agregadas
(por moneda) y nunca suma ARS+USD: el delta se calcula por moneda.
"""


def period_delta(rows_a, rows_b):
    """rows_* = [{'currency':str,'total':float}]. Devuelve {cur:{a,b,delta,pct}}."""
    a = {r["currency"]: float(r["total"] or 0) for r in rows_a}
    b = {r["currency"]: float(r["total"] or 0) for r in rows_b}
    out = {}
    for cur in sorted(set(a) | set(b)):
        va, vb = a.get(cur, 0.0), b.get(cur, 0.0)
        delta = va - vb
        pct = ((delta / vb) * 100) if vb else None
        out[cur] = {"a": va, "b": vb, "delta": delta, "pct": pct}
    return out


def format_comparison(label_a, label_b, delta_map, tipo_str):
    lines = [f"📊 {tipo_str.capitalize()}: {label_a} vs {label_b}\n"]
    for cur, d in delta_map.items():
        arrow = "📈" if d["delta"] > 0 else ("📉" if d["delta"] < 0 else "➖")
        sign = "+" if d["delta"] > 0 else ""
        pct = f" ({sign}{d['pct']:.1f}%)" if d["pct"] is not None else ""
        lines.append(
            f"{arrow} {cur}: {d['a']:,.0f} vs {d['b']:,.0f} → {sign}{d['delta']:,.0f}{pct}")
    return "\n".join(lines)
