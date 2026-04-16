import { useState, useMemo, useRef, forwardRef } from 'react'
import css from './Canvas.module.css'
import { useDesignerStore } from '../../store/designerStore'
import { expandDevices, expandRackDevices, expandDesignerConnections } from '../../utils/yaml'
import type { DesignerDevice, DesignerRack } from '../../types'
import WiringOverlay from './WiringOverlay'

const U_HEIGHT_PX = 18

// ─── helpers ─────────────────────────────────────────────────────────────────

function uNums(totalU: number, uOrder: 'bottom_top' | 'top_bottom'): number[] {
  return uOrder === 'bottom_top'
    ? Array.from({ length: totalU }, (_, i) => totalU - i)
    : Array.from({ length: totalU }, (_, i) => i + 1)
}

function topIdx(startU: number, totalU: number, uOrder: 'bottom_top' | 'top_bottom'): number {
  return uOrder === 'bottom_top' ? totalU - startU : startU - 1
}


// ─── Drag data serialized via dataTransfer ────────────────────────────────────

type DragPayload =
  | { kind: 'palette'; typeName: string }
  | { kind: 'device';  rackId: string; face: 'front' | 'rear'; devName: string; grabRow: number }

const DT_KEY = 'rack-designer/payload'

// ─── Canvas (exported with forwarded ref for WiringOverlay) ──────────────────

const Canvas = forwardRef<HTMLDivElement>((_, _ref) => {
  const racks            = useDesignerStore(s => s.racks)
  const typeEntries      = useDesignerStore(s => s.typeEntries)
  const externalGroups   = useDesignerStore(s => s.externalGroups)
  const selectedDevRef   = useDesignerStore(s => s.selectedDevRef)
  const pickState        = useDesignerStore(s => s.pickState)
  const vizLayerIdx      = useDesignerStore(s => s.vizLayerIdx)
  const wiringLayers     = useDesignerStore(s => s.wiringLayers)
  const addDevice        = useDesignerStore(s => s.addDevice)
  const removeRack       = useDesignerStore(s => s.removeRack)
  const updateRackMeta   = useDesignerStore(s => s.updateRackMeta)
  const moveDevice       = useDesignerStore(s => s.moveDevice)
  const selectDevice     = useDesignerStore(s => s.selectDevice)
  const handleDevicePick = useDesignerStore(s => s.handleDevicePick)

  const canvasRef = useRef<HTMLDivElement>(null)
  const [dropHint, setDropHint] = useState<{ rackId: string; face: 'front' | 'rear'; rowIdx: number } | null>(null)

  const typeColors = useMemo(
    () => Object.fromEntries(typeEntries.map(e => [e.type, e.color])),
    [typeEntries],
  )

  // Wire color and set of device names for the active visualisation layer
  const vizColor = useMemo(() => {
    if (vizLayerIdx == null) return null
    return wiringLayers[vizLayerIdx]?.edge_color ?? '#888888'
  }, [vizLayerIdx, wiringLayers])

  const wiredNames = useMemo<Set<string>>(() => {
    if (vizLayerIdx == null) return new Set()
    const layer = wiringLayers[vizLayerIdx]
    if (!layer) return new Set()
    const names = new Set<string>()
    // Expand template connections so cluster members (e.g. "Encoder 1") are included
    for (const c of expandDesignerConnections(layer.connections)) {
      if (c.from)           names.add(c.from)
      if (c.to)             names.add(c.to as string)
      if (c.via_patch_from) names.add(c.via_patch_from)
      if (c.via_patch_to)   names.add(c.via_patch_to)
    }
    return names
  }, [vizLayerIdx, wiringLayers])

  function getTypeUnits(typeName: string): number {
    return typeEntries.find(e => e.type === typeName)?.units ?? 1
  }

  // ── Drag-over / drop (entire uGrid is drop zone) ──────────────────────────
  function handleGridDragOver(
    e: React.DragEvent<HTMLDivElement>,
    rackId: string,
    face: 'front' | 'rear',
    totalU: number,
  ) {
    if (!e.dataTransfer.types.includes(DT_KEY)) return
    e.preventDefault()
    const rect   = e.currentTarget.getBoundingClientRect()
    const rowIdx = Math.max(0, Math.min(
      Math.floor((e.clientY - rect.top) / U_HEIGHT_PX), totalU - 1,
    ))
    setDropHint({ rackId, face, rowIdx })
  }

  function handleGridDrop(
    e: React.DragEvent<HTMLDivElement>,
    rack: DesignerRack,
    face: 'front' | 'rear',
  ) {
    e.preventDefault()
    setDropHint(null)
    const raw = e.dataTransfer.getData(DT_KEY)
    if (!raw) return
    const payload: DragPayload = JSON.parse(raw)

    const totalU  = rack.total_u ?? 42
    const uOrder  = rack.u_order ?? 'bottom_top'
    const rect    = e.currentTarget.getBoundingClientRect()
    const rowIdx  = Math.max(0, Math.min(
      Math.floor((e.clientY - rect.top) / U_HEIGHT_PX), totalU - 1,
    ))
    const nums    = uNums(totalU, uOrder)
    const targetU = nums[rowIdx]

    if (payload.kind === 'palette') {
      // Create new device from type palette
      const allDevs = [...rack.front, ...rack.rear]
      const count   = allDevs.filter(d => d.type === payload.typeName).length
      const name    = `${payload.typeName} ${count + 1}`
      const units   = getTypeUnits(payload.typeName)
      const dev: DesignerDevice = { name, type: payload.typeName, start_u: targetU, units }
      addDevice(rack.id, face, dev)
      selectDevice({ dev, rackId: rack.id, face, displayName: name })
    } else {
      // Move existing device
      const srcRack = racks.find(r => r.id === payload.rackId)
      if (!srcRack) return
      const srcDev  = srcRack[payload.face].find(d => d.name === payload.devName)
      if (!srcDev)  return
      // Adjust for grab row: if grabbed partway down the device, offset accordingly
      const grabOffset = payload.grabRow
      const newStartU  = uOrder === 'bottom_top'
        ? targetU + grabOffset
        : targetU - grabOffset
      moveDevice(payload.rackId, payload.face, srcDev, rack.id, face, Math.max(1, Math.min(newStartU, totalU)))
    }
  }

  // Drop on zero-U strip → unposition the device
  function handleStripDrop(
    e: React.DragEvent<HTMLDivElement>,
    rack: DesignerRack,
    face: 'front' | 'rear',
  ) {
    e.preventDefault()
    const raw = e.dataTransfer.getData(DT_KEY)
    if (!raw) return
    const payload: DragPayload = JSON.parse(raw)
    if (payload.kind !== 'device') return
    const srcRack = racks.find(r => r.id === payload.rackId)
    if (!srcRack) return
    const srcDev = srcRack[payload.face].find(d => d.name === payload.devName)
    if (!srcDev) return
    moveDevice(payload.rackId, payload.face, srcDev, rack.id, face, undefined)
  }

  // ── Render one face (front or rear) ──────────────────────────────────────
  function renderFace(rack: DesignerRack, face: 'front' | 'rear') {
    const totalU = rack.total_u ?? 42
    const uOrder = rack.u_order ?? 'bottom_top'
    const nums   = uNums(totalU, uOrder)

    // Expand cluster templates into individual members for display.
    // Each member gets its own start_u so it renders at the correct U position.
    const rawDevs      = rack[face]
    const expandedDevs = expandRackDevices(rawDevs)

    // Reverse map: expanded device name → template device in the store.
    // Used so click/drag still operate on the raw template device.
    const expandedToTemplate = new Map<string, DesignerDevice>()
    for (const raw of rawDevs) {
      if (raw.start != null && raw.end != null && raw.name.includes('{N}')) {
        for (const m of expandRackDevices([raw])) {
          expandedToTemplate.set(m.name, raw)
        }
      }
    }

    const positioned   = expandedDevs.filter(d => d.start_u != null && d.units != null)
    const unpositioned = expandedDevs.filter(d => d.start_u == null || d.units == null)

    const isDropTarget = dropHint?.rackId === rack.id && dropHint.face === face

    return (
      <div className={css.faceCol}>
        <div className={`${css.faceLabel} ${face === 'rear' ? css.faceLabelRight : ''}`}>
          {face === 'front' ? '► FRONT' : 'REAR ◄'}
        </div>

        {/* U slot grid — acts as DnD drop zone */}
        <div
          className={css.uGrid}
          style={{ position: 'relative' }}
          onDragOver={e => handleGridDragOver(e, rack.id, face, totalU)}
          onDragLeave={() => setDropHint(null)}
          onDrop={e => handleGridDrop(e, rack, face)}
        >
          {nums.map(u => (
            <div key={u} className={css.uRow}>
              <div className={css.uNum} translate="no">{u}</div>
              <div className={css.uSlot} />
            </div>
          ))}

          {/* Drop highlight */}
          {isDropTarget && (
            <div className={css.dropHighlight} style={{ top: dropHint!.rowIdx * U_HEIGHT_PX }} />
          )}

          {/* Positioned device overlays — each expanded member rendered individually */}
          {positioned.map(dev => {
            const startU      = dev.start_u!
            const tIdx        = topIdx(startU, totalU, uOrder)
            const top         = tIdx * U_HEIGHT_PX
            const height      = (dev.units ?? 1) * U_HEIGHT_PX
            const color       = typeColors[dev.type ?? ''] ?? '#3a3f47'
            // Resolve to template for selection/drag state
            const templateDev = expandedToTemplate.get(dev.name) ?? dev
            const isSelected  = selectedDevRef?.rackId === rack.id
                             && selectedDevRef.face === face
                             && selectedDevRef.dev.name === templateDev.name
            const isWired     = wiredNames.has(dev.name)

            return (
              <div
                key={dev.name}
                data-devname={dev.name}
                className={[
                  css.device,
                  isSelected ? css.deviceSelected : '',
                  pickState  ? css.devicePicking  : '',
                ].join(' ')}
                style={{
                  top, height, background: color,
                  ...(isWired && !isSelected && vizColor
                    ? { outline: `2px solid ${vizColor}`, zIndex: 25 }
                    : {}),
                }}
                draggable={!pickState}
                onDragStart={e => {
                  const rect    = e.currentTarget.getBoundingClientRect()
                  const grabRow = Math.floor((e.clientY - rect.top) / U_HEIGHT_PX)
                  // Drag the template so the whole cluster moves together
                  const payload: DragPayload = {
                    kind: 'device', rackId: rack.id, face,
                    devName: templateDev.name, grabRow,
                  }
                  e.dataTransfer.setData(DT_KEY, JSON.stringify(payload))
                  e.dataTransfer.effectAllowed = 'move'
                }}
                onClick={e => {
                  e.stopPropagation()
                  if (pickState) {
                    handleDevicePick(dev.name)
                  } else {
                    // Select the template device; display the expanded name
                    selectDevice({ dev: templateDev, rackId: rack.id, face, displayName: dev.name })
                  }
                }}
                title={dev.name}
              >
                <span className={css.deviceName}>{dev.name}</span>
              </div>
            )
          })}
        </div>

        {/* Unpositioned strip — also a drop target */}
        <div
          className={css.strip}
          onDragOver={e => { if (e.dataTransfer.types.includes(DT_KEY)) e.preventDefault() }}
          onDrop={e => handleStripDrop(e, rack, face)}
        >
          <div className={css.stripHeader}>
            UNPOSITIONED {unpositioned.length > 0 ? `(${unpositioned.length})` : ''}
          </div>
          {unpositioned.map(dev => {
            const color       = typeColors[dev.type ?? ''] ?? '#3a3f47'
            const templateDev = expandedToTemplate.get(dev.name) ?? dev
            const isSelected  = selectedDevRef?.rackId === rack.id
                             && selectedDevRef.face === face
                             && selectedDevRef.dev.name === templateDev.name
            const isWired     = wiredNames.has(dev.name)
            return (
              <div
                key={dev.name}
                data-devname={dev.name}
                className={[
                  css.stripItem,
                  isSelected ? css.stripItemSelected : '',
                  pickState  ? css.devicePicking     : '',
                ].join(' ')}
                style={isWired && vizColor ? { borderLeft: `3px solid ${vizColor}` } : undefined}
                draggable={!pickState}
                onDragStart={e => {
                  const payload: DragPayload = {
                    kind: 'device', rackId: rack.id, face,
                    devName: templateDev.name, grabRow: 0,
                  }
                  e.dataTransfer.setData(DT_KEY, JSON.stringify(payload))
                  e.dataTransfer.effectAllowed = 'move'
                }}
                onClick={e => {
                  e.stopPropagation()
                  if (pickState) {
                    handleDevicePick(dev.name)
                  } else {
                    selectDevice({ dev: templateDev, rackId: rack.id, face, displayName: dev.name })
                  }
                }}
              >
                <span className={css.stripDot} style={{ background: color }} />
                {dev.name}
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  // ── External group widgets ────────────────────────────────────────────────
  function renderExtWidgets() {
    if (externalGroups.length === 0) return null
    return (
      <div className={css.extColumn}>
        {externalGroups.map((group, gi) => {
          const expanded = expandDevices(group.devices)
          return (
            <div key={gi} className={css.extWidget}>
              <div className={css.extWidgetHeader}>
                <span>{group.name}</span>
                <span className={css.extBadge}>{group.distance_from_racks}m</span>
                <span className={css.extTag}>EXT</span>
              </div>
              <div className={css.extWidgetBody}>
                {expanded.map(dev => {
                  const color     = typeColors[(group.devices.find(d => d.name === dev.name || d.name.includes('{N}'))?.type) ?? ''] ?? '#484f58'
                  const isWired   = wiredNames.has(dev.name)
                  return (
                    <div
                      key={dev.name}
                      data-devname={dev.name}
                      className={[css.extDevRow, pickState ? css.devicePicking : ''].join(' ')}
                      style={isWired && vizColor ? { borderLeft: `3px solid ${vizColor}` } : undefined}
                      onClick={e => {
                        e.stopPropagation()
                        if (pickState) handleDevicePick(dev.name)
                      }}
                    >
                      <span className={css.extDevDot} style={{ background: color }} />
                      <span>{dev.name}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <div
      ref={canvasRef}
      className={`${css.canvas} ${pickState ? css.pickingMode : ''}`}
      onClick={() => { if (!pickState) selectDevice(null) }}
    >
      {racks.length === 0 && !externalGroups.length && (
        <div className={css.empty}>
          Click <strong>+ Add Rack</strong> to get started,<br />
          then drag a device type from the left panel onto a U slot.
        </div>
      )}

      {racks.map(rack => (
        <div key={rack.id} className={css.rackCol}>
          <div className={css.rackHeader}>
            <input
              className={css.rackNameInput}
              value={rack.name}
              onChange={e => updateRackMeta(rack.id, { name: e.target.value })}
              onClick={e => e.stopPropagation()}
              title="Rack name"
            />
            <select
              className={css.rackSelect}
              value={rack.total_u}
              onChange={e => updateRackMeta(rack.id, { total_u: +e.target.value })}
              title="Total U"
            >
              {[12, 18, 24, 32, 42, 48].map(u => (
                <option key={u} value={u}>{u}U</option>
              ))}
            </select>
            <select
              className={css.rackSelect}
              value={rack.u_order}
              onChange={e => updateRackMeta(rack.id, {
                u_order: e.target.value as 'bottom_top' | 'top_bottom',
              })}
              title="U numbering"
            >
              <option value="bottom_top">B→T</option>
              <option value="top_bottom">T→B</option>
            </select>
            <button
              className={css.removeRackBtn}
              onClick={e => { e.stopPropagation(); removeRack(rack.id) }}
              title="Remove rack"
            >×</button>
          </div>
          <div className={css.rackBody}>
            {renderFace(rack, 'front')}
            {renderFace(rack, 'rear')}
          </div>
        </div>
      ))}

      {renderExtWidgets()}

      {/* SVG wiring overlay — rendered last so wires paint above all device blocks */}
      <WiringOverlay canvasRef={canvasRef} />
    </div>
  )
})

Canvas.displayName = 'Canvas'
export default Canvas
