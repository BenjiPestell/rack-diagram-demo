import { useMemo, useState } from 'react'
import css from './PortAssignView.module.css'
import { useDesignerStore } from '../../store/designerStore'
import { expandRackDevices, expandDesignerConnections } from '../../utils/yaml'
import type { DesignerWiringLayer } from '../../types'

// ─── Types ────────────────────────────────────────────────────────────────────

type PortField = 'from_port' | 'to_port' | 'patch_port_from' | 'patch_port_to'

interface PortSlot {
  port:       number
  peer:       string | null
  peerPort:   number | null
  label:      string | null
  layerName:  string | null
  layerColor: string | null
  ip:         string | null
  // write-back identifiers — null for auto-assigned (no explicit port on connection)
  layerIdx:   number | null
  connIdx:    number | null
  portField:  PortField | null
  // annotation from device.port_notes
  note:       string | null
}

// ─── Port computation ─────────────────────────────────────────────────────────

function computePorts(
  devName:    string,
  totalPorts: number,
  layers:     DesignerWiringLayer[],
  portNotes:  Record<number, string>,
): PortSlot[] {
  const explicit   = new Map<number, PortSlot>()
  const unassigned: Omit<PortSlot, 'port' | 'note'>[] = []

  function record(
    portNum:   number | undefined,
    slot:      Omit<PortSlot, 'port' | 'note'>,
  ) {
    if (portNum != null && portNum >= 1 && portNum <= totalPorts && !explicit.has(portNum)) {
      explicit.set(portNum, { port: portNum, note: null, ...slot })
    } else {
      unassigned.push(slot)
    }
  }

  for (let li = 0; li < layers.length; li++) {
    const layer = layers[li]
    for (let ci = 0; ci < layer.connections.length; ci++) {
      // Only Ethernet connections have assignable ports
      const resolvedType = (layer.connections[ci].cable_type ?? layer.cable_type ?? '').toLowerCase()
      if (resolvedType !== 'ethernet') continue

      // Expand the raw connection: resolves {N}/{N+k} templates and comma-separated `to`.
      // All expanded forms share the same layerIdx/connIdx for write-back.
      const meta = { layerName: layer.name, layerColor: layer.edge_color ?? null, layerIdx: li, connIdx: ci }
      for (const exp of expandDesignerConnections([layer.connections[ci]])) {
        const expFrom = String(exp.from || '')
        const expTo   = String(exp.to   || '')
        if (expFrom === devName) {
          record(exp.from_port, { peer: expTo, peerPort: exp.to_port ?? null,
            label: exp.label ?? null, ip: exp.from_ip ?? null, portField: 'from_port', ...meta })
        }
        if (expTo === devName) {
          record(exp.to_port, { peer: expFrom, peerPort: exp.from_port ?? null,
            label: exp.label ?? null, ip: exp.to_ip ?? null, portField: 'to_port', ...meta })
        }
        if (exp.via_patch_from === devName) {
          record(exp.patch_port_from, { peer: expFrom, peerPort: null,
            label: null, ip: null, portField: 'patch_port_from', ...meta })
        }
        if (exp.via_patch_to === devName) {
          record(exp.patch_port_to, { peer: expTo, peerPort: null,
            label: null, ip: null, portField: 'patch_port_to', ...meta })
        }
      }
    }
  }

  const result: PortSlot[] = []
  let ui = 0
  for (let p = 1; p <= totalPorts; p++) {
    const note = portNotes[p] ?? null
    if (explicit.has(p)) {
      result.push({ ...explicit.get(p)!, note })
    } else if (ui < unassigned.length) {
      result.push({ port: p, ...unassigned[ui++], note })
    } else {
      result.push({ port: p, peer: null, peerPort: null, label: null,
        layerName: null, layerColor: null, ip: null,
        layerIdx: null, connIdx: null, portField: null, note })
    }
  }
  return result
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function PortAssignView() {
  // ── All hooks unconditionally first ──────────────────────────────────────
  const portAssignTarget = useDesignerStore(s => s.portAssignTarget)
  const closePortAssign  = useDesignerStore(s => s.closePortAssign)
  const racks            = useDesignerStore(s => s.racks)
  const wiringLayers     = useDesignerStore(s => s.wiringLayers)
  const updateConnection = useDesignerStore(s => s.updateConnection)
  const updateDevice     = useDesignerStore(s => s.updateDevice)

  const [selectedPort, setSelectedPort] = useState<number | null>(null)
  const [dragSrc,      setDragSrc]      = useState<number | null>(null)
  const [dragOver,     setDragOver]     = useState<number | null>(null)

  const devName = portAssignTarget ?? ''

  // Locate template device (for port_notes write-back)
  const devInfo = useMemo(() => {
    if (!devName) return null
    for (const rack of racks) {
      for (const face of ['front', 'rear'] as const) {
        // Direct match (non-cluster device)
        const direct = rack[face].find(d => d.name === devName)
        if (direct) return { dev: direct, rack, face }
        // Expanded match (cluster member) — find the template
        const expanded = expandRackDevices(rack[face])
        if (expanded.some(d => d.name === devName)) {
          const template = rack[face].find(d =>
            d.name === devName ||
            (d.start != null && expandRackDevices([d]).some(m => m.name === devName)),
          )
          if (template) return { dev: template, rack, face }
        }
      }
    }
    return null
  }, [devName, racks])

  const totalPorts = devInfo?.dev.ports ?? 24
  const portNotes  = useMemo<Record<number, string>>(
    () => devInfo?.dev.port_notes ?? {},
    [devInfo],
  )

  const slots = useMemo(
    () => devName ? computePorts(devName, totalPorts, wiringLayers, portNotes) : [],
    [devName, totalPorts, wiringLayers, portNotes],
  )

  const cols         = totalPorts <= 12 ? 6 : totalPorts <= 24 ? 12 : 16
  const selectedSlot = selectedPort != null ? slots.find(s => s.port === selectedPort) ?? null : null

  // ── Early return now safe (all hooks called above) ────────────────────────
  if (!portAssignTarget) return null

  // ── Write-back helpers ────────────────────────────────────────────────────

  function assignPort(slot: PortSlot, newPort: number | undefined) {
    if (slot.layerIdx == null || slot.connIdx == null || !slot.portField) return
    updateConnection(slot.layerIdx, slot.connIdx, { [slot.portField]: newPort })
  }

  function commitPortNumber(slot: PortSlot, raw: string) {
    const n = parseInt(raw, 10)
    if (!Number.isFinite(n)) return
    const clamped = Math.max(1, Math.min(totalPorts, n))
    if (clamped === slot.port) return
    assignPort(slot, clamped)
    setSelectedPort(clamped)
  }

  function commitNote(portNum: number, text: string) {
    if (!devInfo) return
    const next = { ...(devInfo.dev.port_notes ?? {}) }
    if (text) next[portNum] = text
    else delete next[portNum]
    updateDevice(devInfo.rack.id, devInfo.face, devInfo.dev.name, {
      port_notes: Object.keys(next).length ? next : undefined,
    })
  }

  // ── Drag handlers ─────────────────────────────────────────────────────────

  function handleDrop(dstSlot: PortSlot) {
    setDragSrc(null)
    setDragOver(null)
    if (dragSrc == null || dragSrc === dstSlot.port) return
    const srcSlot = slots.find(s => s.port === dragSrc)
    if (!srcSlot?.peer || srcSlot.layerIdx == null || !srcSlot.portField) return
    // Move src → dst port
    updateConnection(srcSlot.layerIdx, srcSlot.connIdx!, { [srcSlot.portField]: dstSlot.port })
    // If dst is occupied, swap it back to src's old port
    if (dstSlot.peer && dstSlot.layerIdx != null && dstSlot.connIdx != null && dstSlot.portField) {
      updateConnection(dstSlot.layerIdx, dstSlot.connIdx, { [dstSlot.portField]: srcSlot.port })
    }
    setSelectedPort(dstSlot.port)
  }

  // ─────────────────────────────────────────────────────────────────────────

  return (
    <div className={css.overlay} onClick={closePortAssign}>
      <div className={css.panel} onClick={e => e.stopPropagation()}>

        {/* Header */}
        <div className={css.header}>
          <div className={css.headerLeft}>
            <span className={css.devName}>{devName}</span>
            {devInfo && (
              <span className={css.devMeta}>
                {devInfo.rack.name} · {devInfo.face} · {totalPorts} ports
              </span>
            )}
          </div>
          <button className={css.closeBtn} onClick={closePortAssign}>×</button>
        </div>

        <div className={css.body}>

          {/* ── Port grid ──────────────────────────────────────────────────── */}
          <div className={css.gridPane}>
            <div className={css.gridTitle}>
              Port Assignment
              <span className={css.gridHint}>drag to reassign · click to inspect</span>
            </div>
            <div
              className={css.grid}
              style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}
            >
              {slots.map(slot => {
                const isSelected  = selectedPort === slot.port
                const isDragSrc   = dragSrc === slot.port
                const isDragOver  = dragOver === slot.port && dragSrc != null && dragSrc !== slot.port
                return (
                  <div
                    key={slot.port}
                    className={[
                      css.portSlot,
                      slot.peer   ? css.portOccupied  : '',
                      isSelected  ? css.portSelected  : '',
                      isDragSrc   ? css.portDragging  : '',
                      isDragOver  ? css.portDragOver  : '',
                    ].filter(Boolean).join(' ')}
                    style={slot.peer ? {
                      borderColor: slot.layerColor ?? '#888',
                      boxShadow:   `inset 0 2px 0 ${slot.layerColor ?? '#888'}`,
                    } : undefined}
                    draggable={!!slot.peer}
                    onDragStart={slot.peer ? e => {
                      setDragSrc(slot.port)
                      e.dataTransfer.effectAllowed = 'move'
                    } : undefined}
                    onDragOver={e => {
                      e.preventDefault()
                      e.dataTransfer.dropEffect = 'move'
                      setDragOver(slot.port)
                    }}
                    onDragLeave={() => setDragOver(null)}
                    onDragEnd={() => { setDragSrc(null); setDragOver(null) }}
                    onDrop={e => { e.preventDefault(); handleDrop(slot) }}
                    onClick={() => setSelectedPort(isSelected ? null : slot.port)}
                    title={slot.peer
                      ? `Port ${slot.port}: ${slot.peer}`
                      : `Port ${slot.port}: empty`}
                  >
                    <span className={css.portNum} translate="no">{slot.port}</span>
                    {slot.peer && (
                      <span
                        className={css.portDot}
                        style={{ background: slot.layerColor ?? '#888' }}
                      />
                    )}
                    {slot.peer ? (
                      <span className={css.portPeer}>{slot.peer}</span>
                    ) : slot.note ? (
                      <span className={css.portNote}>{slot.note}</span>
                    ) : null}
                  </div>
                )
              })}
            </div>
          </div>

          {/* ── Detail pane ────────────────────────────────────────────────── */}
          <div className={css.detailPane}>
            {!selectedSlot ? (
              <div className={css.detailEmpty}>
                Click a port to inspect or edit.<br />
                Drag occupied ports to reassign.
              </div>
            ) : (
              <>
                <div className={css.detailTitle}>
                  Port {selectedSlot.port}
                  {!selectedSlot.peer && <span className={css.emptyTag}> · empty</span>}
                </div>

                {/* Port number reassignment */}
                {selectedSlot.peer && selectedSlot.connIdx != null && (
                  <div className={css.detailRow}>
                    <span className={css.detailKey}>Port #</span>
                    <div className={css.portNumRow}>
                      <input
                        key={`pn-${selectedSlot.port}`}
                        className={css.portNumInput}
                        type="number"
                        min={1}
                        max={totalPorts}
                        defaultValue={selectedSlot.port}
                        onBlur={e  => commitPortNumber(selectedSlot, e.target.value)}
                        onKeyDown={e => {
                          if (e.key === 'Enter')  e.currentTarget.blur()
                          if (e.key === 'Escape') e.currentTarget.value = String(selectedSlot.port)
                        }}
                      />
                      <button
                        className={css.makeAutoBtn}
                        title="Clear explicit port — connection uses auto-assign order"
                        onClick={() => { assignPort(selectedSlot, undefined); setSelectedPort(null) }}
                      >
                        auto
                      </button>
                    </div>
                  </div>
                )}

                {/* Port note */}
                <div className={css.detailRow}>
                  <span className={css.detailKey}>Note</span>
                  <input
                    key={`note-${selectedSlot.port}`}
                    className={css.noteInput}
                    defaultValue={selectedSlot.note ?? ''}
                    placeholder="annotation…"
                    onBlur={e  => commitNote(selectedSlot.port, e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter')  e.currentTarget.blur()
                      if (e.key === 'Escape') e.currentTarget.value = selectedSlot.note ?? ''
                    }}
                  />
                </div>

                {/* Connection details (read-only) */}
                {selectedSlot.peer && (
                  <>
                    <div className={css.detailDivider} />
                    <div className={css.detailRow}>
                      <span className={css.detailKey}>Peer</span>
                      <span className={css.detailVal}>{selectedSlot.peer}</span>
                    </div>
                    {selectedSlot.peerPort != null && (
                      <div className={css.detailRow}>
                        <span className={css.detailKey}>Peer port</span>
                        <span className={css.detailVal}>{selectedSlot.peerPort}</span>
                      </div>
                    )}
                    <div className={css.detailRow}>
                      <span className={css.detailKey}>Layer</span>
                      <span className={css.detailVal} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                        {selectedSlot.layerColor && (
                          <span style={{
                            width: 8, height: 8, borderRadius: 2,
                            background: selectedSlot.layerColor, flexShrink: 0,
                          }} />
                        )}
                        {selectedSlot.layerName ?? '—'}
                      </span>
                    </div>
                    {selectedSlot.label && (
                      <div className={css.detailRow}>
                        <span className={css.detailKey}>Label</span>
                        <span className={css.detailVal}>{selectedSlot.label}</span>
                      </div>
                    )}
                    {selectedSlot.ip && (
                      <div className={css.detailRow}>
                        <span className={css.detailKey}>IP</span>
                        <span className={css.detailVal}>{selectedSlot.ip}</span>
                      </div>
                    )}
                  </>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
