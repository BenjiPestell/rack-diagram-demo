import { useMemo, useState } from 'react'
import css from './PortAssignView.module.css'
import { useDesignerStore } from '../../store/designerStore'
import { expandRackDevices } from '../../utils/yaml'
import type { DesignerWiringLayer } from '../../types'

// ─── Port assignment computation ─────────────────────────────────────────────

interface PortSlot {
  port: number
  peer: string | null
  peerPort: number | null
  label: string | null
  layerName: string | null
  layerColor: string | null
  ip: string | null
}

function computePorts(devName: string, totalPorts: number, layers: DesignerWiringLayer[]): PortSlot[] {
  const explicit = new Map<number, PortSlot>()
  const unassigned: Omit<PortSlot, 'port'>[] = []

  function record(portNum: number | undefined, slot: Omit<PortSlot, 'port'>) {
    if (portNum != null && portNum >= 1 && portNum <= totalPorts) {
      explicit.set(portNum, { port: portNum, ...slot })
    } else {
      unassigned.push(slot)
    }
  }

  for (const layer of layers) {
    for (const c of layer.connections) {
      const meta = {
        layerName:  layer.name,
        layerColor: layer.edge_color ?? null,
      }
      if (c.from === devName) {
        record(c.from_port, { peer: String(c.to), peerPort: c.to_port ?? null,
          label: c.label ?? null, ip: c.from_ip ?? null, ...meta })
      }
      if (c.to === devName) {
        record(c.to_port, { peer: c.from, peerPort: c.from_port ?? null,
          label: c.label ?? null, ip: c.to_ip ?? null, ...meta })
      }
      if (c.via_patch_from === devName) {
        record(c.patch_port_from, { peer: c.from, peerPort: null,
          label: null, ip: null, ...meta })
      }
      if (c.via_patch_to === devName) {
        record(c.patch_port_to, { peer: String(c.to), peerPort: null,
          label: null, ip: null, ...meta })
      }
    }
  }

  // Fill remaining slots with unassigned connections
  const result: PortSlot[] = []
  let ui = 0
  for (let p = 1; p <= totalPorts; p++) {
    if (explicit.has(p)) {
      result.push(explicit.get(p)!)
    } else if (ui < unassigned.length) {
      result.push({ port: p, ...unassigned[ui++] })
    } else {
      result.push({ port: p, peer: null, peerPort: null, label: null, layerName: null, layerColor: null, ip: null })
    }
  }
  return result
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function PortAssignView() {
  const portAssignTarget = useDesignerStore(s => s.portAssignTarget)
  const closePortAssign  = useDesignerStore(s => s.closePortAssign)
  const racks            = useDesignerStore(s => s.racks)
  const wiringLayers     = useDesignerStore(s => s.wiringLayers)

  const [selectedPort, setSelectedPort] = useState<number | null>(null)

  const devName = portAssignTarget
  if (!devName) return null

  // Find device info
  const devInfo = useMemo(() => {
    for (const rack of racks) {
      for (const face of ['front', 'rear'] as const) {
        const expanded = expandRackDevices(rack[face])
        const found    = expanded.find(d => d.name === devName)
        if (found) return { dev: found, rack, face }
      }
    }
    return null
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [devName, racks])

  const totalPorts = devInfo?.dev.ports ?? 24
  const slots = useMemo(
    () => computePorts(devName, totalPorts, wiringLayers),
    [devName, totalPorts, wiringLayers],
  )

  const cols = totalPorts <= 12 ? 6 : totalPorts <= 24 ? 12 : 16
  const selectedSlot = selectedPort != null ? slots.find(s => s.port === selectedPort) : null

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
          {/* Port grid */}
          <div className={css.gridPane}>
            <div className={css.gridTitle}>Port Assignment</div>
            <div className={css.grid} style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
              {slots.map(slot => (
                <div
                  key={slot.port}
                  className={[
                    css.portSlot,
                    slot.peer ? css.portOccupied : '',
                    selectedPort === slot.port ? css.portSelected : '',
                  ].join(' ')}
                  style={slot.peer ? {
                    borderColor: slot.layerColor ?? '#888',
                    boxShadow: `inset 0 2px 0 ${slot.layerColor ?? '#888'}`,
                  } : undefined}
                  onClick={() => setSelectedPort(slot.port === selectedPort ? null : slot.port)}
                  title={slot.peer ? `Port ${slot.port}: ${slot.peer}` : `Port ${slot.port}: empty`}
                >
                  <span className={css.portNum} translate="no">{slot.port}</span>
                  {slot.peer && (
                    <span
                      className={css.portDot}
                      style={{ background: slot.layerColor ?? '#888' }}
                    />
                  )}
                  {slot.peer && (
                    <span className={css.portPeer}>{slot.peer}</span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Detail panel */}
          <div className={css.detailPane}>
            {!selectedSlot ? (
              <div className={css.detailEmpty}>Click a port to see details.</div>
            ) : (
              <>
                <div className={css.detailTitle}>Port {selectedSlot.port}</div>
                <div className={css.detailRow}>
                  <span className={css.detailKey}>Peer</span>
                  <span className={css.detailVal}>{selectedSlot.peer ?? '—'}</span>
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
                      <span style={{ width: 8, height: 8, borderRadius: 2, background: selectedSlot.layerColor, flexShrink: 0 }} />
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
          </div>
        </div>
      </div>
    </div>
  )
}
