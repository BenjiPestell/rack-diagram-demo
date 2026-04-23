import { useRef, useMemo } from 'react'
import css from './BottomSheet.module.css'
import type { DeviceInfo, ConnIndex, CableConfig, CableSegment, RawConfig } from '../../types'
import { calcPatchedCableLength } from '../../utils/cableLength'
import { expandConnections } from '../../utils/yaml'

// ─── Port schedule computation ────────────────────────────────────────────────

interface PortSlot {
  port:       number
  peer:       string | null
  layerColor: string | null
  patchSrc:   string | null
  patchDst:   string | null
  note:       string | null
}

function computePortSlots(
  devName:    string,
  totalPorts: number,
  portNotes:  Record<number, string>,
  config:     RawConfig,
): PortSlot[] {
  const explicit   = new Map<number, Omit<PortSlot, 'port' | 'note'>>()
  const unassigned: Omit<PortSlot, 'port' | 'note'>[] = []

  function record(portNum: number | undefined, slot: Omit<PortSlot, 'port' | 'note'>) {
    if (portNum != null && portNum >= 1 && !explicit.has(portNum)) {
      explicit.set(portNum, slot)
    } else {
      unassigned.push(slot)
    }
  }

  for (const layer of config.wiring_layers ?? []) {
    const layerColor = layer.edge_color ?? '#888'
    for (const rawConn of layer.connections ?? []) {
      const cable = ((rawConn as unknown as Record<string,unknown>)['cable_type'] as string ?? layer.cable_type ?? '').toLowerCase()
      if (cable && cable !== 'ethernet') continue

      const rawAny    = rawConn as unknown as Record<string, unknown>
      const isCluster = rawAny['start'] != null && rawAny['end'] != null
      const connColor = (rawAny['edge_color'] as string | undefined) ?? layerColor

      // expandConnections handles {N} template expansion
      const expanded = expandConnections([rawConn])
      let idx = 0
      for (const exp of expanded) {
        const off    = isCluster ? idx : 0
        const expFrom = String(exp.from || '')
        const expTo   = String(exp.to   || '')

        const effFromPort      = exp.from_port       != null ? exp.from_port       + off : undefined
        const effToPort        = exp.to_port         != null ? exp.to_port         + off : undefined
        const effPatchPortFrom = exp.patch_port_from != null ? exp.patch_port_from + off : undefined
        const effPatchPortTo   = exp.patch_port_to   != null ? exp.patch_port_to   + off : undefined

        if (expFrom === devName)
          record(effFromPort, { peer: expTo,   layerColor: connColor, patchSrc: null,    patchDst: null })
        if (expTo === devName)
          record(effToPort,   { peer: expFrom, layerColor: connColor, patchSrc: null,    patchDst: null })
        if (exp.via_patch_from === devName)
          record(effPatchPortFrom, { peer: expFrom, layerColor: connColor, patchSrc: expFrom, patchDst: expTo })
        if (exp.via_patch_to === devName)
          record(effPatchPortTo,   { peer: expTo,   layerColor: connColor, patchSrc: expFrom, patchDst: expTo })

        idx++
      }
    }
  }

  const maxPort = Math.max(
    totalPorts,
    explicit.size > 0 ? Math.max(...explicit.keys()) : 0,
    unassigned.length,
  )
  const result: PortSlot[] = []
  let ui = 0
  for (let p = 1; p <= maxPort; p++) {
    const note = portNotes[p] ?? null
    if (explicit.has(p)) {
      result.push({ port: p, note, ...explicit.get(p)! })
    } else if (ui < unassigned.length) {
      result.push({ port: p, note, ...unassigned[ui++] })
    } else {
      result.push({ port: p, peer: null, layerColor: null, patchSrc: null, patchDst: null, note })
    }
  }
  return result
}

interface Props {
  dev: DeviceInfo | null
  connIndex: ConnIndex
  deviceMap: Record<string, DeviceInfo>
  cfg: CableConfig
  config: RawConfig | null
  onClose: () => void
}

function fmtM(v: number) { return `${v.toFixed(3)}m` }

function BreakdownLine({ seg }: { seg: CableSegment }) {
  const b = seg.breakdown
  const parts: string[] = []
  if (b.vertical)    parts.push(`vert ${fmtM(b.vertical)}`)
  if (b.verticalA)   parts.push(`vertA ${fmtM(b.verticalA)}`)
  if (b.verticalB)   parts.push(`vertB ${fmtM(b.verticalB)}`)
  if (b.frontToBack) parts.push(`f2b ${fmtM(b.frontToBack)}`)
  if (b.horizontal)  parts.push(`horiz ${fmtM(b.horizontal)}`)
  if (b.groupDist)   parts.push(`ext ${fmtM(b.groupDist)}`)
  if (b.rails)       parts.push(`rails ${fmtM(b.rails)}`)
  if (b.slack)       parts.push(`slack ${fmtM(b.slack)}`)
  return <>{parts.join('  ·  ')}</>
}

export default function BottomSheet({ dev, connIndex, deviceMap, cfg, config, onClose }: Props) {
  const isOpen = dev != null
  const sheetRef = useRef<HTMLDivElement>(null)

  // Swipe-to-close
  const dragStart = useRef<number | null>(null)
  function onTouchStart(e: React.TouchEvent) {
    dragStart.current = e.touches[0].clientY
  }
  function onTouchMove(e: React.TouchEvent) {
    if (dragStart.current == null || !sheetRef.current) return
    const dy = e.touches[0].clientY - dragStart.current
    if (dy > 0) sheetRef.current.style.transform = `translateY(${dy}px)`
  }
  function onTouchEnd(e: React.TouchEvent) {
    if (!sheetRef.current || dragStart.current == null) return
    const dy = e.changedTouches[0].clientY - dragStart.current
    sheetRef.current.style.transform = ''
    if (dy > 80) onClose()
    dragStart.current = null
  }

  // Port schedule — computed unconditionally (Rules of Hooks)
  const portSlots = useMemo(() => {
    if (!dev || !config) return []
    const total = dev.ports ?? 0
    const notes = dev.port_notes ?? {}
    return computePortSlots(dev.name, total, notes, config)
  }, [dev?.name, dev?.ports, dev?.port_notes, config]) // eslint-disable-line react-hooks/exhaustive-deps

  const portCols = portSlots.length <= 12 ? 6 : portSlots.length <= 24 ? 12 : 16

  if (!dev) {
    return (
      <>
        <div className={css.backdrop} />
        <div className={css.sheet} />
      </>
    )
  }

  const conns = connIndex[dev.name] || []

  // Group by layer
  const byLayer = new Map<string, typeof conns>()
  for (const c of conns) {
    if (!byLayer.has(c.layer)) byLayer.set(c.layer, [])
    byLayer.get(c.layer)!.push(c)
  }

  // Footer stats
  const allLengths: number[] = []
  for (const c of conns) {
    const r = calcPatchedCableLength(c, dev.name, deviceMap, cfg)
    if (r.total != null) allLengths.push(r.total)
  }
  const totalCable = allLengths.reduce((s, v) => s + v, 0)
  const shortest   = allLengths.length ? Math.min(...allLengths) : null
  const longest    = allLengths.length ? Math.max(...allLengths) : null

  const metaBadges = [
    dev.type,
    `${dev.rackName} · ${dev.face} · ${dev.located ? `U${dev.start_u}` : 'unpositioned'}`,
  ].filter(Boolean) as string[]

  return (
    <>
      <div
        className={`${css.backdrop} ${isOpen ? css.backdropOpen : ''}`}
        onClick={onClose}
      />

      <div
        ref={sheetRef}
        className={`${css.sheet} ${isOpen ? css.sheetOpen : ''}`}
      >
        {/* Drag handle */}
        <div
          className={css.handle}
          onTouchStart={onTouchStart}
          onTouchMove={onTouchMove}
          onTouchEnd={onTouchEnd}
        >
          <div className={css.handleBar} />
        </div>

        {/* Header */}
        <div className={css.header}>
          <div className={css.devName}>{dev.name}</div>
          <div className={css.meta}>
            {metaBadges.map((b, i) => <span key={i} className={css.badge}>{b}</span>)}
          </div>
        </div>

        {/* Port grid */}
        {portSlots.some(s => s.peer !== null) && (
          <div className={css.portSection}>
            <div className={css.portSectionTitle}>PORT ASSIGNMENT</div>
            <div className={css.portGridWrap}>
              <div
                className={css.portGrid}
                style={{ gridTemplateColumns: `repeat(${portCols}, 1fr)` }}
              >
                {portSlots.map(slot => (
                  <div
                    key={slot.port}
                    className={`${css.portCell} ${slot.peer ? css.portCellOccupied : ''}`}
                    style={slot.peer ? {
                      borderColor: slot.layerColor ?? '#888',
                      boxShadow:   `inset 0 2px 0 ${slot.layerColor ?? '#888'}`,
                    } : undefined}
                  >
                    <span className={css.portCellNum}>{slot.port}</span>
                    {slot.peer && (
                      <>
                        <span
                          className={css.portCellDot}
                          style={{ background: slot.layerColor ?? '#888' }}
                        />
                        <span className={css.portCellText}>
                          {slot.patchSrc != null
                            ? `${slot.patchSrc} → ${slot.patchDst}`
                            : slot.peer}
                        </span>
                      </>
                    )}
                    {slot.note && (
                      <span className={css.portCellNote}>{slot.note}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Connections */}
        <div className={css.scroll}>
          {conns.length === 0 && (
            <div style={{ padding: '16px', color: '#484f58', fontSize: 12 }}>No connections</div>
          )}

          {Array.from(byLayer.entries()).map(([layerName, layerConns]) => (
            <div key={layerName}>
              <div className={css.sectionHeader}>{layerName}</div>

              {layerConns.map((c, ci) => {
                const result = calcPatchedCableLength(c, dev.name, deviceMap, cfg)
                const segs   = c.isPatchLeg
                  ? result.segments.filter(s => s.from === dev.name || s.to === dev.name)
                  : result.segments
                const total  = result.total
                const isPatched = result.isPatched

                // Full route string
                let routeParts: string[] | null = null
                if (isPatched && c.patchFrom || c.patchTo) {
                  if (c.isPatchLeg && c.peerFrom) {
                    const chain = [c.peerFrom, c.patchFrom, c.patchTo, c.peer].filter(Boolean) as string[]
                    routeParts = chain
                  } else if (c.direction === '→') {
                    const chain = [dev.name, c.patchFrom, c.patchTo, c.peer].filter(Boolean) as string[]
                    routeParts = chain
                  } else {
                    const chain = [c.peer, c.patchFrom, c.patchTo, dev.name].filter(Boolean) as string[]
                    routeParts = chain
                  }
                }

                const peerLabel = c.isPatchLeg
                  ? `${c.peerFrom} ↔ ${c.peer}`
                  : c.peer

                return (
                  <div key={ci} className={`${css.card} ${isPatched ? css.cardPatched : ''}`}>
                    {/* Primary row */}
                    <div className={css.cardPrimary}>
                      <div className={css.dot} style={{ background: c.layerColor }} />
                      <span className={css.peer}>{peerLabel}</span>
                      {c.isPatchLeg && <span className={css.ppBadge}>[PP]</span>}
                      <span className={total == null ? css.lengthNull : css.length}>
                        {total == null ? '—' : `${total.toFixed(1)}m`}
                      </span>
                    </div>

                    {c.cableType && <div className={css.cableType}>{c.cableType}</div>}

                    {/* Route hint */}
                    {routeParts && (
                      <div className={css.patchRoute}>{routeParts.join(' → ')}</div>
                    )}

                    {/* Per-segment breakdown */}
                    {segs.length === 1 ? (
                      <div className={css.breakdown}>
                        <BreakdownLine seg={segs[0]} />
                      </div>
                    ) : (
                      segs.map((seg, si) => (
                        <div key={si}>
                          <div className={css.segRow}>
                            <span className={css.segLabel}>{si + 1}/{segs.length}</span>
                            <span className={css.segNames}>{seg.from} → {seg.to}</span>
                            <span className={css.segLen}>
                              {seg.length == null ? '?' : `${seg.length.toFixed(1)}m`}
                            </span>
                          </div>
                          <div className={`${css.breakdown} ${css.breakdownIndent}`}>
                            <BreakdownLine seg={seg} />
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )
              })}
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className={css.footer}>
          <div className={css.stat}>
            <span className={css.statLabel}>Connections</span>
            <span className={css.statValue}>{conns.length}</span>
          </div>
          <div className={css.stat}>
            <span className={css.statLabel}>Total cable</span>
            <span className={css.statValue}>{totalCable.toFixed(1)}m</span>
          </div>
          <div className={css.stat}>
            <span className={css.statLabel}>Shortest</span>
            <span className={css.statValue}>{shortest == null ? '—' : `${shortest.toFixed(1)}m`}</span>
          </div>
          <div className={css.stat}>
            <span className={css.statLabel}>Longest</span>
            <span className={css.statValue}>{longest == null ? '—' : `${longest.toFixed(1)}m`}</span>
          </div>
        </div>
      </div>
    </>
  )
}
