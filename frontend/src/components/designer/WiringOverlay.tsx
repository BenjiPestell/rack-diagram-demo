import { useEffect, useLayoutEffect, useState } from 'react'
import type { RefObject } from 'react'
import { useDesignerStore } from '../../store/designerStore'
import { expandDesignerConnections } from '../../utils/yaml'
import type { DesignerConnection } from '../../types'

interface Props {
  canvasRef: RefObject<HTMLDivElement | null>
}

interface Point { x: number; y: number }

interface PathInfo {
  key:     string
  d:       string
  color:   string
  isDash:  boolean        // patch inter-panel leg → dashed
  label:   string | null  // shown inline near curve start
  tooltip: string         // shown in cursor-following div on hover
  labelX:  number
  labelY:  number
}

// ─── Coordinate helpers ───────────────────────────────────────────────────────

// getBoundingClientRect-based lookup: gives content-relative coordinates that
// correctly account for the canvas's padding, scroll position, and flex layout.
function deviceOffsetInCanvas(canvasEl: HTMLDivElement | null, devName: string): Point | null {
  if (!canvasEl) return null
  try {
    const el = canvasEl.querySelector(
      `[data-devname="${CSS.escape(devName)}"]`,
    ) as HTMLElement | null
    if (!el) return null
    const cr = canvasEl.getBoundingClientRect()
    const dr = el.getBoundingClientRect()
    return {
      x: dr.left - cr.left + canvasEl.scrollLeft + dr.width  / 2,
      y: dr.top  - cr.top  + canvasEl.scrollTop  + dr.height / 2,
    }
  } catch {
    return null
  }
}

// ─── Quadratic Bezier with perpendicular deflection (matches legacy HTML) ─────

interface QuadInfo { d: string; cx: number; cy: number }

function makeQuad(p1: Point, p2: Point): QuadInfo {
  const dx   = p2.x - p1.x
  const dy   = p2.y - p1.y
  const dist = Math.sqrt(dx * dx + dy * dy)
  if (dist < 1) {
    const mx = (p1.x + p2.x) / 2
    const my = (p1.y + p2.y) / 2
    return { d: `M${p1.x},${p1.y} L${p2.x},${p2.y}`, cx: mx, cy: my }
  }
  // Perpendicular offset to the left of the direction of travel
  const curve = Math.min(dist * 0.35, 120)
  const px = -dy / dist * curve
  const py =  dx / dist * curve
  const cx = (p1.x + p2.x) / 2 + px
  const cy = (p1.y + p2.y) / 2 + py
  return { d: `M${p1.x},${p1.y} Q${cx},${cy} ${p2.x},${p2.y}`, cx, cy }
}

// Point at parameter t along a quadratic Bezier (t=0.25 ≈ ¼ from start)
function quadPoint(p1: Point, cp: Point, p2: Point, t = 0.25): Point {
  const mt = 1 - t
  return {
    x: mt * mt * p1.x + 2 * mt * t * cp.x + t * t * p2.x,
    y: mt * mt * p1.y + 2 * mt * t * cp.y + t * t * p2.y,
  }
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function WiringOverlay({ canvasRef }: Props) {
  const vizLayerIdx  = useDesignerStore(s => s.vizLayerIdx)
  const wiringLayers = useDesignerStore(s => s.wiringLayers)
  const racks        = useDesignerStore(s => s.racks)        // dependency for re-layout
  const extGroups    = useDesignerStore(s => s.externalGroups)

  const [svgSize,    setSvgSize]    = useState({ w: 0, h: 0 })
  const [paths,      setPaths]      = useState<PathInfo[]>([])
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null)
  const [cursor,     setCursor]     = useState({ x: 0, y: 0 })
  // tick increments whenever the canvas scrolls, forcing path recomputation
  const [scrollTick, setScrollTick] = useState(0)

  // Resize SVG to match canvas scroll dimensions; also track scroll for coordinate recompute
  useLayoutEffect(() => {
    const el = canvasRef.current
    if (!el) return
    const updateSize   = () => setSvgSize({ w: el.scrollWidth, h: el.scrollHeight })
    const updateScroll = () => setScrollTick(t => t + 1)
    updateSize()
    const obs = new ResizeObserver(updateSize)
    obs.observe(el)
    el.addEventListener('scroll', updateSize)
    el.addEventListener('scroll', updateScroll)
    return () => {
      obs.disconnect()
      el.removeEventListener('scroll', updateSize)
      el.removeEventListener('scroll', updateScroll)
    }
  }, [canvasRef])

  // ResizeObserver tracks layout-box changes, not scrollWidth/scrollHeight growth.
  // When racks/external groups are added the canvas scrolls wider/taller — re-read here.
  useEffect(() => {
    const el = canvasRef.current
    if (!el) return
    setSvgSize({ w: el.scrollWidth, h: el.scrollHeight })
  }, [canvasRef, racks, extGroups])

  // Recompute wire paths whenever layer data or canvas layout changes
  useEffect(() => {
    const el = canvasRef.current
    if (!el || vizLayerIdx == null) { setPaths([]); return }

    const layer = wiringLayers[vizLayerIdx]
    if (!layer) { setPaths([]); return }

    const layerColor = layer.edge_color ?? '#888888'
    const layerCable = layer.cable_type  ?? ''
    // Expand template connections (e.g. "Encoder {N}", start/end) into individual entries
    // so each expanded device name matches its data-devname DOM attribute.
    const connections: DesignerConnection[] = expandDesignerConnections(layer.connections ?? [])
    const newPaths: PathInfo[] = []

    function addPath(
      from:     string,
      to:       string,
      color:    string,
      label:    string | null,
      isDash:   boolean,
      tipText?: string,
    ) {
      const p1 = deviceOffsetInCanvas(el, from)
      const p2 = deviceOffsetInCanvas(el, to)
      if (!p1 || !p2) return

      const { d, cx, cy } = makeQuad(p1, p2)
      const cp  = { x: cx, y: cy }
      const lp  = quadPoint(p1, cp, p2, 0.25)
      const tip = tipText ?? `${from}  →  ${to}`

      newPaths.push({
        key:     `${newPaths.length}-${from}-${to}`,
        d, color, isDash, label,
        tooltip: label ? `${tip}  ·  ${label}` : tip,
        labelX:  lp.x,
        labelY:  lp.y - 6,
      })
    }

    for (const conn of connections) {
      const from  = String(conn.from || '')
      const to    = String(conn.to   || '')
      if (!from || !to) continue

      const color = conn.edge_color ?? layerColor
      const label = conn.label ?? conn.cable_type ?? layerCable ?? null

      const pf = conn.via_patch_from  // patch panel near source
      const pt = conn.via_patch_to    // patch panel near destination

      if (pf || pt) {
        // 3-leg patch routing:
        //   from → patchFrom  (solid, no label)
        //   patchFrom → patchTo  (dashed, inter-panel trunk)
        //   patchTo → to  (solid, label)
        if (pf) addPath(from, pf,   color, null,  false, `${from} → ${pf}`)
        if (pf && pt) addPath(pf, pt, color, null, true,  `${pf} → ${pt}  (patch)`)
        addPath(pt ?? pf ?? from, to, color, label, false,
          `${pt ?? pf ?? from} → ${to}`)
      } else {
        addPath(from, to, color, label, false)
      }
    }

    setPaths(newPaths)
    setHoveredIdx(null)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vizLayerIdx, wiringLayers, scrollTick, racks, extGroups])

  if (vizLayerIdx == null || paths.length === 0) return null

  return (
    <>
      <svg
        style={{
          position:      'absolute',
          top:           0,
          left:          0,
          pointerEvents: 'none',
          zIndex:        50,
          overflow:      'visible',
        }}
        width={svgSize.w}
        height={svgSize.h}
      >
        <defs>
          {/* Single shared marker — fill inherits the referencing path's stroke color */}
          <marker
            id="wiring-arrow"
            markerWidth="6"
            markerHeight="6"
            refX="5"
            refY="3"
            orient="auto"
          >
            <path d="M0,0 L0,6 L6,3 z" fill="context-stroke" />
          </marker>
        </defs>

        {paths.map((p, i) => {
          const hovered = hoveredIdx === i

          return (
            <g key={p.key}>
              {/* ── Outer glow ring (wide, semi-transparent, no filter) ── */}
              <path
                d={p.d}
                fill="none"
                stroke={p.color}
                strokeWidth={hovered ? 11 : 7}
                strokeOpacity={hovered ? 0.28 : 0.18}
                strokeDasharray={p.isDash ? '6,4' : undefined}
                style={{ pointerEvents: 'none' }}
              />
              {/* ── Inner glow ring (medium) ── */}
              <path
                d={p.d}
                fill="none"
                stroke={p.color}
                strokeWidth={hovered ? 5 : 3.5}
                strokeOpacity={hovered ? 0.55 : 0.38}
                strokeDasharray={p.isDash ? '6,4' : undefined}
                style={{ pointerEvents: 'none' }}
              />
              {/* ── Crisp core wire ── */}
              <path
                d={p.d}
                fill="none"
                stroke={p.color}
                strokeWidth={hovered ? 2.5 : 1.5}
                strokeOpacity={hovered ? 1.0 : 0.95}
                strokeDasharray={p.isDash ? '6,4' : undefined}
                markerEnd={p.isDash ? undefined : 'url(#wiring-arrow)'}
                style={{ pointerEvents: 'none', transition: 'stroke-width 0.12s, stroke-opacity 0.12s' }}
              />

              {/* ── Transparent hit area (14px wide) ── */}
              <path
                d={p.d}
                fill="none"
                stroke="transparent"
                strokeWidth={14}
                style={{ pointerEvents: 'stroke', cursor: 'crosshair' }}
                onMouseEnter={() => setHoveredIdx(i)}
                onMouseMove={e => setCursor({ x: e.clientX, y: e.clientY })}
                onMouseLeave={() => setHoveredIdx(null)}
              />

              {/* ── Inline label at ¼ along curve ── */}
              {p.label && (
                <text
                  x={p.labelX}
                  y={p.labelY}
                  textAnchor="middle"
                  fontSize={9}
                  fill={p.color}
                  fillOpacity={hovered ? 1.0 : 0.9}
                  style={{ pointerEvents: 'none', fontFamily: 'Share Tech Mono, monospace' }}
                >
                  {p.label}
                </text>
              )}
            </g>
          )
        })}
      </svg>

      {/* ── Cursor-following tooltip (fixed, outside SVG) ── */}
      {hoveredIdx != null && paths[hoveredIdx] && (
        <div
          style={{
            position:      'fixed',
            left:          cursor.x + 14,
            top:           cursor.y - 8,
            background:    'var(--surface3)',
            border:        `1px solid ${paths[hoveredIdx].color}`,
            color:         'var(--text)',
            fontFamily:    'var(--mono)',
            fontSize:      11,
            padding:       '4px 8px',
            borderRadius:  3,
            pointerEvents: 'none',
            zIndex:        9999,
            whiteSpace:    'nowrap',
            letterSpacing: '0.5px',
          }}
        >
          {paths[hoveredIdx].tooltip}
        </div>
      )}
    </>
  )
}
