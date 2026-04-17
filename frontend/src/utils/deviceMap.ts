import type {
  RawConfig, DeviceMap, ConnIndex, ColorMap,
  RawRackConfig, RawExternalGroup,
} from '../types'
import { expandRackDevices, expandDevices, expandConnections } from './yaml'

export function buildDeviceMap(config: RawConfig): DeviceMap {
  const map: DeviceMap = {}

  ;(config.racks || []).forEach((rackCfg: RawRackConfig, ri: number) => {
    const rackId   = rackCfg.rack.id
    const rackName = rackCfg.rack.name || rackId
    const totalU   = rackCfg.rack.total_u ?? 42
    const uOrder   = rackCfg.rack.u_order ?? 'bottom_top'

    for (const face of ['front', 'rear'] as const) {
      const raw = rackCfg[face] ?? []
      const expanded = expandRackDevices(raw)
      for (const dev of expanded) {
        map[dev.name] = {
          name: dev.name,
          type: dev.type,
          rackId, rackName, rackIdx: ri,
          face,
          start_u: dev.start_u,
          units: dev.units ?? 1,
          located: dev.start_u != null && dev.units != null,
          ports: dev.ports,
          port_notes: dev.port_notes,
          onRails: !!dev.on_rails,
          cableExit: dev.cable_exit ?? 'rear',
          isPatchPanel: (dev.type ?? '').toLowerCase().includes('patch panel'),
          totalU, uOrder,
        }
      }
    }
  })

  ;(config.external_devices || []).forEach((group: RawExternalGroup) => {
    const dist = group.distance_from_racks ?? 0
    const groupName = group.name || 'External'
    const expanded = expandDevices(group.devices)
    for (const dev of expanded) {
      map[dev.name] = {
        name: dev.name,
        type: dev.type,
        rackId: 'external',
        rackName: groupName,
        rackIdx: -1,
        face: 'external',
        units: 1,
        located: false,
        onRails: false,
        cableExit: 'rear',
        isPatchPanel: false,
        totalU: 42,
        uOrder: 'bottom_top',
        distanceFromRacks: dist,
        groupName,
      }
    }
  })

  return map
}

export function buildTypeColorMap(
  typeEntries: { type: string; color: string }[]
): ColorMap {
  const map: ColorMap = {}
  for (const e of typeEntries) map[e.type] = e.color
  return map
}

export function buildConnectionIndex(config: RawConfig, colorMap: ColorMap): ConnIndex {
  const index: ConnIndex = {}

  function ensure(name: string) {
    if (!index[name]) index[name] = []
  }

  for (const layer of config.wiring_layers ?? []) {
    const layerName  = layer.name
    const cableType  = layer.cable_type ?? ''
    const layerColor = layer.edge_color ?? colorMap[cableType] ?? '#888'
    const conns      = expandConnections(layer.connections ?? [], cableType)

    for (const c of conns) {
      const fromName = String(c.from || '')
      const toArr    = Array.isArray(c.to) ? c.to.map(String) : c.to ? [String(c.to)] : []
      const patchFrom = c.via_patch_from ?? null
      const patchTo   = c.via_patch_to   ?? null
      const connCableType  = c.cable_type  || cableType
      const connLayerColor = c.edge_color  || layerColor

      for (const toName of toArr) {
        ensure(fromName)
        ensure(toName)
        index[fromName].push({
          peer: toName, layer: layerName, cableType: connCableType,
          layerColor: connLayerColor, direction: '→', patchFrom, patchTo,
        })
        index[toName].push({
          peer: fromName, layer: layerName, cableType: connCableType,
          layerColor: connLayerColor, direction: '←', patchFrom, patchTo,
        })

        if (patchFrom || patchTo) {
          const chain = patchFrom && patchTo
            ? [fromName, patchFrom, patchTo, toName]
            : patchFrom
              ? [fromName, patchFrom, toName]
              : [fromName, patchTo!, toName]

          for (let ci = 1; ci < chain.length - 1; ci++) {
            const ppName   = chain[ci]
            const prevName = chain[ci - 1]
            const nextName = chain[ci + 1]
            ensure(ppName)
            index[ppName].push({
              peer: toName, peerFrom: fromName,
              segFrom: prevName, segTo: nextName,
              layer: layerName, cableType: connCableType, layerColor: connLayerColor,
              direction: '↔', patchFrom, patchTo,
              isPatchLeg: true,
            })
          }
        }
      }
    }
  }

  return index
}
