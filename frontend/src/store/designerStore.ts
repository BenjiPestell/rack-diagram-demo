import { create } from 'zustand'
import { parseConfig, serializeToYaml, expandName } from '../utils/yaml'
import { SAMPLE_DATA } from '../utils/sampleData'
import type {
  DesignerRack, DesignerDevice, DesignerWiringLayer, DesignerConnection,
  DesignerExternalGroup, DesignerExternalDevice, TypeEntry,
  SelectedDevRef, PickState, RunFiles,
} from '../types'

// ─── History ─────────────────────────────────────────────────────────────────

/** The data slice that participates in undo/redo (excludes ephemeral UI state). */
type HistorySlice = Pick<DesignerStore,
  'racks' | 'wiringLayers' | 'externalGroups' | 'typeEntries' | 'cableTypes' |
  'interRackDistance' | 'cableSlackLength' | 'frontToBackLength' |
  'railExtensionLength' | 'standardUHeight'
>

const MAX_HISTORY = 50

function snapshot(s: DesignerStore): HistorySlice {
  return {
    racks:               s.racks,
    wiringLayers:        s.wiringLayers,
    externalGroups:      s.externalGroups,
    typeEntries:         s.typeEntries,
    cableTypes:          s.cableTypes,
    interRackDistance:   s.interRackDistance,
    cableSlackLength:    s.cableSlackLength,
    frontToBackLength:   s.frontToBackLength,
    railExtensionLength: s.railExtensionLength,
    standardUHeight:     s.standardUHeight,
  }
}

/** Wraps a partial state update with a history push and future clear. */
function withHistory<T extends object>(s: DesignerStore, changes: T) {
  return {
    ...changes,
    past:   [...s.past.slice(-(MAX_HISTORY - 1)), snapshot(s)],
    future: [] as HistorySlice[],
  }
}

// ─── Rename helpers ───────────────────────────────────────────────────────────

/**
 * Build a map of oldName → newName covering both the template name and every
 * expanded member name (for cluster devices with start/end/{N}).
 */
function buildRenameMap(
  oldName: string,
  newName: string,
  dev: { start?: number; end?: number },
): Map<string, string> {
  const map = new Map<string, string>()
  map.set(oldName, newName)
  if (dev.start != null && dev.end != null && oldName.includes('{N}')) {
    for (let n = dev.start; n <= dev.end; n++) {
      const oldExp = expandName(oldName, n)
      const newExp = expandName(newName, n)
      if (oldExp !== newExp) map.set(oldExp, newExp)
    }
  }
  return map
}

/** Rewrite all connection name references using the supplied rename map. */
function rewriteConnections(
  layers: DesignerWiringLayer[],
  nameMap: Map<string, string>,
): DesignerWiringLayer[] {
  if (nameMap.size === 0) return layers
  const r = (s: string) => nameMap.get(s) ?? s
  return layers.map(layer => ({
    ...layer,
    connections: layer.connections.map(conn => ({
      ...conn,
      from:           r(conn.from),
      to:             Array.isArray(conn.to) ? conn.to.map(r) : r(conn.to as string),
      via_patch_from: conn.via_patch_from ? r(conn.via_patch_from) : conn.via_patch_from,
      via_patch_to:   conn.via_patch_to   ? r(conn.via_patch_to)   : conn.via_patch_to,
    })),
  }))
}

// ─── Default type palette ────────────────────────────────────────────────────

const DEFAULT_TYPES: TypeEntry[] = [
  { type: 'Switch',        color: '#1f6feb', units: 1 },
  { type: 'Patch panel',   color: '#388bfd', units: 1, ported: true },
  { type: 'Server',        color: '#2ea043', units: 2 },
  { type: 'PDU',           color: '#d29922', units: 1 },
  { type: 'UPS',           color: '#6e40c9', units: 2 },
  { type: 'KVM',           color: '#bf4b8a', units: 1 },
  { type: 'Media',         color: '#1b7c83', units: 1 },
  { type: 'Encoder',       color: '#c0392b', units: 1 },
  { type: 'Decoder',       color: '#2980b9', units: 1 },
  { type: 'Controller',    color: '#8e44ad', units: 1 },
]

function nextRackName(racks: DesignerRack[]): { id: string; name: string } {
  const n = racks.length + 1
  return { id: `rack${n}`, name: `Rack ${n}` }
}

// ─── State + actions interface ───────────────────────────────────────────────

export interface DesignerStore {
  // Data
  racks: DesignerRack[]
  wiringLayers: DesignerWiringLayer[]
  externalGroups: DesignerExternalGroup[]
  typeEntries: TypeEntry[]
  cableTypes: string[]

  // Cable config
  interRackDistance: number
  cableSlackLength: number
  frontToBackLength: number
  railExtensionLength: number
  standardUHeight: number

  // UI state
  selectedDevRef: SelectedDevRef | null
  pickState: PickState | null
  activeLayerIdx: number | null
  vizLayerIdx: number | null          // which layer to draw on canvas
  activeTab: 'properties' | 'wiring' | 'external' | 'yaml'
  portAssignTarget: string | null     // device name for port assign overlay

  // Undo / redo history
  past:   HistorySlice[]
  future: HistorySlice[]

  // Run pipeline state
  isRunning: boolean
  showRunPanel: boolean
  runLog: string[]
  runFiles: RunFiles | null

  // ── Rack actions ────────────────────────────────────────────────────────
  addRack: () => void
  removeRack: (id: string) => void
  updateRackMeta: (id: string, changes: Partial<Pick<DesignerRack, 'name' | 'total_u' | 'u_order'>>) => void

  // ── Device actions ──────────────────────────────────────────────────────
  addDevice: (rackId: string, face: 'front' | 'rear', dev: DesignerDevice) => void
  removeDevice: (rackId: string, face: 'front' | 'rear', devName: string) => void
  updateDevice: (rackId: string, face: 'front' | 'rear', devName: string, changes: Partial<DesignerDevice>) => void
  moveDevice: (
    fromRackId: string, fromFace: 'front' | 'rear', dev: DesignerDevice,
    toRackId: string,   toFace:   'front' | 'rear', newStartU?: number,
  ) => void

  // ── Selection ───────────────────────────────────────────────────────────
  selectDevice: (ref: SelectedDevRef | null) => void

  // ── Wiring ──────────────────────────────────────────────────────────────
  addWiringLayer: () => void
  removeWiringLayer: (idx: number) => void
  updateLayerMeta: (idx: number, changes: Partial<Pick<DesignerWiringLayer, 'name' | 'edge_color' | 'cable_type'>>) => void
  addConnection: (layerIdx: number) => void
  removeConnection: (layerIdx: number, connIdx: number) => void
  updateConnection: (layerIdx: number, connIdx: number, changes: Partial<DesignerConnection>) => void
  setActiveLayer: (idx: number | null) => void
  setVizLayer: (idx: number | null) => void

  // ── Pick mode ───────────────────────────────────────────────────────────
  enterPickMode: (layerIdx: number, connIdx: number, field: string) => void
  exitPickMode: () => void
  handleDevicePick: (devName: string) => void

  // ── Type entries ────────────────────────────────────────────────────────
  addTypeEntry: (entry: TypeEntry) => void
  removeTypeEntry: (type: string) => void
  updateTypeEntry: (type: string, changes: Partial<TypeEntry>) => void

  // ── Cable types ─────────────────────────────────────────────────────────
  addCableType: (ct: string) => void
  removeCableType: (ct: string) => void

  // ── External groups ─────────────────────────────────────────────────────
  addExternalGroup: () => void
  removeExternalGroup: (idx: number) => void
  updateGroupMeta: (idx: number, changes: Partial<Pick<DesignerExternalGroup, 'name' | 'distance_from_racks'>>) => void
  addExternalDevice: (groupIdx: number, dev: DesignerExternalDevice) => void
  removeExternalDevice: (groupIdx: number, devName: string) => void
  updateExternalDevice: (groupIdx: number, devName: string, changes: Partial<DesignerExternalDevice>) => void

  // ── YAML I/O ────────────────────────────────────────────────────────────
  generateYaml: () => string
  loadFromYaml: (yamlText: string) => void

  // ── Cable config ────────────────────────────────────────────────────────
  setCableConfig: (changes: Partial<Pick<DesignerStore,
    'interRackDistance' | 'cableSlackLength' | 'frontToBackLength' | 'railExtensionLength' | 'standardUHeight'
  >>) => void

  // ── Tab ─────────────────────────────────────────────────────────────────
  setActiveTab: (tab: DesignerStore['activeTab']) => void

  // ── Port assignment ──────────────────────────────────────────────────────
  openPortAssign: (devName: string) => void
  closePortAssign: () => void

  // ── Run pipeline ─────────────────────────────────────────────────────────
  startRun: () => Promise<void>
  toggleRunPanel: () => void

  // ── History ──────────────────────────────────────────────────────────────
  undo: () => void
  redo: () => void

  // ── Workspace ────────────────────────────────────────────────────────────
  clearAll: () => void
  loadSampleData: () => void
}

// ─── Store implementation ────────────────────────────────────────────────────

export const useDesignerStore = create<DesignerStore>((set, get) => ({
  racks:            [],
  wiringLayers:     [],
  externalGroups:   [],
  typeEntries:      DEFAULT_TYPES,
  cableTypes:       ['Ethernet', 'Fibre', 'HDMI', 'SDI', 'XLR', 'USB'],
  interRackDistance:   2.5,
  cableSlackLength:    0.2,
  frontToBackLength:   0.5,
  railExtensionLength: 0.5,
  standardUHeight:     0.045,
  past:             [],
  future:           [],
  selectedDevRef:   null,
  pickState:        null,
  activeLayerIdx:   null,
  vizLayerIdx:      null,
  activeTab:        'properties',
  portAssignTarget: null,
  isRunning:        false,
  showRunPanel:     false,
  runLog:           [],
  runFiles:         null,

  // ── Rack ──────────────────────────────────────────────────────────────────
  addRack: () => set(s => {
    const { id, name } = nextRackName(s.racks)
    return withHistory(s, { racks: [...s.racks, { id, name, total_u: 42, u_order: 'bottom_top', front: [], rear: [] }] })
  }),

  removeRack: (id) => set(s =>
    withHistory(s, { racks: s.racks.filter(r => r.id !== id) }),
  ),

  updateRackMeta: (id, changes) => set(s =>
    withHistory(s, { racks: s.racks.map(r => r.id === id ? { ...r, ...changes } : r) }),
  ),

  // ── Device ────────────────────────────────────────────────────────────────
  addDevice: (rackId, face, dev) => set(s =>
    withHistory(s, { racks: s.racks.map(r => r.id !== rackId ? r : { ...r, [face]: [...r[face], dev] }) }),
  ),

  removeDevice: (rackId, face, devName) => set(s =>
    withHistory(s, {
      racks: s.racks.map(r => r.id !== rackId ? r : {
        ...r, [face]: r[face].filter(d => d.name !== devName),
      }),
      selectedDevRef: s.selectedDevRef?.dev.name === devName ? null : s.selectedDevRef,
    }),
  ),

  updateDevice: (rackId, face, devName, changes) => set(s => {
    const newName   = changes.name
    const isRename  = newName !== undefined && newName !== devName
    const srcDev    = s.racks.find(r => r.id === rackId)?.[face].find(d => d.name === devName)
    const nameMap   = isRename && srcDev
      ? buildRenameMap(devName, newName, srcDev)
      : new Map<string, string>()

    // If portAssignTarget references an old name, follow the rename
    const pat = s.portAssignTarget
    const newPat = pat ? (nameMap.get(pat) ?? pat) : pat

    return withHistory(s, {
      racks: s.racks.map(r => r.id !== rackId ? r : {
        ...r, [face]: r[face].map(d => d.name !== devName ? d : { ...d, ...changes }),
      }),
      wiringLayers: rewriteConnections(s.wiringLayers, nameMap),
      portAssignTarget: newPat,
      selectedDevRef: s.selectedDevRef?.dev.name === devName
        ? { ...s.selectedDevRef,
            dev:         { ...s.selectedDevRef.dev, ...changes },
            displayName: isRename
              ? (nameMap.get(s.selectedDevRef.displayName) ?? s.selectedDevRef.displayName)
              : s.selectedDevRef.displayName,
          }
        : s.selectedDevRef,
    })
  }),

  moveDevice: (fromRackId, fromFace, dev, toRackId, toFace, newStartU) => set(s => {
    const moved = { ...dev, start_u: newStartU }
    return withHistory(s, {
      racks: s.racks.map(r => {
        if (r.id === fromRackId && r.id === toRackId && fromFace === toFace) {
          return { ...r, [fromFace]: r[fromFace].map(d => d.name === dev.name ? moved : d) }
        }
        if (r.id === fromRackId) return { ...r, [fromFace]: r[fromFace].filter(d => d.name !== dev.name) }
        if (r.id === toRackId)   return { ...r, [toFace]: [...r[toFace], moved] }
        return r
      }),
      selectedDevRef: s.selectedDevRef?.dev.name === dev.name
        ? { ...s.selectedDevRef, rackId: toRackId, face: toFace, dev: moved }
        : s.selectedDevRef,
    })
  }),

  // ── Selection ─────────────────────────────────────────────────────────────
  selectDevice: (ref) => set({ selectedDevRef: ref, activeTab: ref ? 'properties' : get().activeTab }),

  // ── Wiring ────────────────────────────────────────────────────────────────
  addWiringLayer: () => set(s => {
    const n = s.wiringLayers.length + 1
    const colors = ['#e74c3c','#3498db','#2ecc71','#f39c12','#9b59b6','#1abc9c']
    return withHistory(s, {
      wiringLayers: [...s.wiringLayers, {
        name: `Layer ${n}`,
        edge_color: colors[(n - 1) % colors.length],
        cable_type: '',
        connections: [],
      }],
      activeLayerIdx: s.wiringLayers.length,
    })
  }),

  removeWiringLayer: (idx) => set(s =>
    withHistory(s, {
      wiringLayers:   s.wiringLayers.filter((_, i) => i !== idx),
      activeLayerIdx: s.activeLayerIdx === idx ? null : s.activeLayerIdx,
      vizLayerIdx:    s.vizLayerIdx    === idx ? null : s.vizLayerIdx,
    }),
  ),

  updateLayerMeta: (idx, changes) => set(s =>
    withHistory(s, { wiringLayers: s.wiringLayers.map((l, i) => i !== idx ? l : { ...l, ...changes }) }),
  ),

  addConnection: (layerIdx) => set(s =>
    withHistory(s, {
      wiringLayers: s.wiringLayers.map((l, i) => i !== layerIdx ? l : {
        ...l, connections: [...l.connections, { from: '', to: '' }],
      }),
    }),
  ),

  removeConnection: (layerIdx, connIdx) => set(s =>
    withHistory(s, {
      wiringLayers: s.wiringLayers.map((l, i) => i !== layerIdx ? l : {
        ...l, connections: l.connections.filter((_, ci) => ci !== connIdx),
      }),
    }),
  ),

  updateConnection: (layerIdx, connIdx, changes) => set(s =>
    withHistory(s, {
      wiringLayers: s.wiringLayers.map((l, i) => i !== layerIdx ? l : {
        ...l, connections: l.connections.map((c, ci) => ci !== connIdx ? c : { ...c, ...changes }),
      }),
    }),
  ),

  setActiveLayer: (idx) => set({ activeLayerIdx: idx }),
  setVizLayer:    (idx) => set(s => ({ vizLayerIdx: s.vizLayerIdx === idx ? null : idx })),

  // ── Pick mode ─────────────────────────────────────────────────────────────
  enterPickMode: (layerIdx, connIdx, field) => set({ pickState: { layerIdx, connIdx, field } }),
  exitPickMode:  () => set({ pickState: null }),

  handleDevicePick: (devName) => {
    const { pickState, wiringLayers } = get()
    if (!pickState) return
    const { layerIdx, connIdx, field } = pickState
    if (!wiringLayers[layerIdx]?.connections[connIdx]) return
    get().updateConnection(layerIdx, connIdx, { [field]: devName })
    get().exitPickMode()
  },

  // ── Type entries ──────────────────────────────────────────────────────────
  addTypeEntry:    (entry)         => set(s => withHistory(s, { typeEntries: [...s.typeEntries, entry] })),
  removeTypeEntry: (type)          => set(s => withHistory(s, { typeEntries: s.typeEntries.filter(e => e.type !== type) })),
  updateTypeEntry: (type, changes) => set(s =>
    withHistory(s, { typeEntries: s.typeEntries.map(e => e.type !== type ? e : { ...e, ...changes }) }),
  ),

  // ── Cable types ───────────────────────────────────────────────────────────
  addCableType:    (ct) => set(s => withHistory(s, { cableTypes: s.cableTypes.includes(ct) ? s.cableTypes : [...s.cableTypes, ct] })),
  removeCableType: (ct) => set(s => withHistory(s, { cableTypes: s.cableTypes.filter(c => c !== ct) })),

  // ── External groups ───────────────────────────────────────────────────────
  addExternalGroup: () => set(s =>
    withHistory(s, {
      externalGroups: [...s.externalGroups, {
        name: `External ${s.externalGroups.length + 1}`,
        distance_from_racks: 10,
        devices: [],
      }],
    }),
  ),
  removeExternalGroup: (idx) => set(s =>
    withHistory(s, { externalGroups: s.externalGroups.filter((_, i) => i !== idx) }),
  ),
  updateGroupMeta: (idx, changes) => set(s =>
    withHistory(s, { externalGroups: s.externalGroups.map((g, i) => i !== idx ? g : { ...g, ...changes }) }),
  ),
  addExternalDevice: (groupIdx, dev) => set(s =>
    withHistory(s, {
      externalGroups: s.externalGroups.map((g, i) => i !== groupIdx ? g : { ...g, devices: [...g.devices, dev] }),
    }),
  ),
  removeExternalDevice: (groupIdx, devName) => set(s =>
    withHistory(s, {
      externalGroups: s.externalGroups.map((g, i) => i !== groupIdx ? g : {
        ...g, devices: g.devices.filter(d => d.name !== devName),
      }),
    }),
  ),
  updateExternalDevice: (groupIdx, devName, changes) => set(s => {
    const newName  = changes.name
    const isRename = newName !== undefined && newName !== devName
    const srcDev   = s.externalGroups[groupIdx]?.devices.find(d => d.name === devName)
    const nameMap  = isRename && srcDev
      ? buildRenameMap(devName, newName, srcDev)
      : new Map<string, string>()

    return withHistory(s, {
      externalGroups: s.externalGroups.map((g, i) => i !== groupIdx ? g : {
        ...g, devices: g.devices.map(d => d.name !== devName ? d : { ...d, ...changes }),
      }),
      wiringLayers: rewriteConnections(s.wiringLayers, nameMap),
    })
  }),

  // ── YAML I/O ──────────────────────────────────────────────────────────────
  generateYaml: () => {
    const s = get()
    return serializeToYaml({
      racks: s.racks,
      wiringLayers: s.wiringLayers,
      externalGroups: s.externalGroups,
      typeEntries: s.typeEntries,
      cableTypes: s.cableTypes,
      interRackDistance:   s.interRackDistance,
      cableSlackLength:    s.cableSlackLength,
      frontToBackLength:   s.frontToBackLength,
      railExtensionLength: s.railExtensionLength,
      standardUHeight:     s.standardUHeight,
    })
  },

  loadFromYaml: (yamlText) => {
    try {
      const r = parseConfig(yamlText) as unknown as Record<string, unknown>

      const typeEntries: TypeEntry[] = []
      const tc = r['type_colors'] as Record<string, unknown> | undefined
      if (tc) {
        for (const [type, val] of Object.entries(tc)) {
          if (val && typeof val === 'object') {
            const v = val as Record<string, unknown>
            typeEntries.push({
              type,
              color:  String(v['color']  ?? '#888'),
              units:  Number(v['units']  ?? 1),
              ported: Boolean(v['ported']),
            })
          } else {
            typeEntries.push({ type, color: String(val ?? '#888') })
          }
        }
      }

      const rawRacks = Array.isArray(r['racks']) ? r['racks'] as Record<string, unknown>[] : []
      const racks: DesignerRack[] = rawRacks.map((rc: Record<string, unknown>) => {
        const rackMeta = rc['rack'] as Record<string, unknown>
        const parseDevs = (face: unknown): DesignerDevice[] =>
          Array.isArray(face) ? face.map((d: Record<string, unknown>) => ({
            name:       String(d['name'] ?? ''),
            type:       d['type']      != null ? String(d['type'])              : undefined,
            start_u:    d['start_u']   != null ? Number(d['start_u'])           : undefined,
            units:      d['units']     != null ? Number(d['units'])             : undefined,
            start:      d['start']     != null ? Number(d['start'])             : undefined,
            end:        d['end']       != null ? Number(d['end'])               : undefined,
            spacing:    d['spacing']   != null ? Number(d['spacing'])           : undefined,
            on_rails:   d['on_rails']  ? true : undefined,
            cable_exit: d['cable_exit'] as 'front' | 'rear' | undefined,
            ports:      d['ports']     != null ? Number(d['ports'])             : undefined,
            port_notes: d['port_notes'] as Record<number, string> | undefined,
          })) : []
        return {
          id:      String(rackMeta['id'] ?? 'rack'),
          name:    String(rackMeta['name'] ?? rackMeta['id'] ?? 'Rack'),
          total_u: Number(rackMeta['total_u'] ?? 42),
          u_order: (rackMeta['u_order'] as 'bottom_top' | 'top_bottom') ?? 'bottom_top',
          front:   parseDevs(rc['front']),
          rear:    parseDevs(rc['rear']),
        }
      })

      const rawLayers = Array.isArray(r['wiring_layers']) ? r['wiring_layers'] as Record<string, unknown>[] : []
      const wiringLayers: DesignerWiringLayer[] = rawLayers.map((l: Record<string, unknown>) => ({
        name:        String(l['name'] ?? ''),
        edge_color:  l['edge_color'] != null ? String(l['edge_color']) : undefined,
        cable_type:  l['cable_type'] != null ? String(l['cable_type']) : undefined,
        connections: Array.isArray(l['connections'])
          ? l['connections'].map((c: Record<string, unknown>): DesignerConnection => ({
              from:           String(c['from'] ?? ''),
              to:             Array.isArray(c['to']) ? (c['to'] as unknown[]).map(String).join(', ') : String(c['to'] ?? ''),
              cable_type:     c['cable_type']     != null ? String(c['cable_type'])     : undefined,
              edge_color:     c['edge_color']     != null ? String(c['edge_color'])     : undefined,
              label:          c['label']          != null ? String(c['label'])          : undefined,
              via_patch_from: c['via_patch_from'] != null ? String(c['via_patch_from']) : undefined,
              via_patch_to:   c['via_patch_to']   != null ? String(c['via_patch_to'])   : undefined,
              patch_port_from: c['patch_port_from'] != null ? Number(c['patch_port_from']) : undefined,
              patch_port_to:   c['patch_port_to']   != null ? Number(c['patch_port_to'])   : undefined,
              from_port:       c['from_port']       != null ? Number(c['from_port'])       : undefined,
              to_port:         c['to_port']         != null ? Number(c['to_port'])         : undefined,
              from_ip:         c['from_ip']         != null ? String(c['from_ip'])         : undefined,
              to_ip:           c['to_ip']           != null ? String(c['to_ip'])           : undefined,
              start:           c['start']           != null ? Number(c['start'])           : undefined,
              end:             c['end']             != null ? Number(c['end'])             : undefined,
            }))
          : [],
      }))

      const rawExternal = Array.isArray(r['external_devices']) ? r['external_devices'] as Record<string, unknown>[] : []
      const externalGroups: DesignerExternalGroup[] = rawExternal.map((g: Record<string, unknown>) => ({
        name:                String(g['name'] ?? ''),
        distance_from_racks: Number(g['distance_from_racks'] ?? 0),
        devices:             Array.isArray(g['devices'])
          ? g['devices'].map((d: Record<string, unknown>): DesignerExternalDevice => ({
              name:  String(d['name'] ?? ''),
              type:  d['type'] != null ? String(d['type']) : undefined,
              start: d['start'] != null ? Number(d['start']) : undefined,
              end:   d['end']   != null ? Number(d['end'])   : undefined,
            }))
          : [],
      }))

      const cableTypes = Array.isArray(r['cable_types']) ? (r['cable_types'] as unknown[]).map(String) : get().cableTypes

      const s = get()
      set({
        racks, wiringLayers, externalGroups, cableTypes,
        typeEntries: typeEntries.length ? typeEntries : s.typeEntries,
        interRackDistance:   Number(r['inter_rack_distance']   ?? s.interRackDistance),
        cableSlackLength:    Number(r['cable_slack_length']    ?? s.cableSlackLength),
        frontToBackLength:   Number(r['front_to_back_length']  ?? s.frontToBackLength),
        railExtensionLength: Number(r['rail_extension_length'] ?? s.railExtensionLength),
        standardUHeight:     Number(r['standard_u_height']     ?? s.standardUHeight),
        selectedDevRef: null,
        activeLayerIdx: wiringLayers.length ? 0 : null,
        vizLayerIdx: null,
        past:   [...s.past.slice(-(MAX_HISTORY - 1)), snapshot(s)],
        future: [],
      })
    } catch (e) {
      console.error('Failed to load YAML:', e)
    }
  },

  // ── Cable config ──────────────────────────────────────────────────────────
  setCableConfig: (changes) => set(s => withHistory(s, changes)),

  // ── Tab ───────────────────────────────────────────────────────────────────
  setActiveTab: (tab) => set({ activeTab: tab }),

  // ── Port assignment ───────────────────────────────────────────────────────
  openPortAssign:  (devName) => set({ portAssignTarget: devName }),
  closePortAssign: ()        => set({ portAssignTarget: null }),

  // ── Run pipeline ──────────────────────────────────────────────────────────
  startRun: async () => {
    if (get().isRunning) return
    set({ isRunning: true, showRunPanel: true, runLog: ['Saving YAML to server...'], runFiles: null })
    try {
      const yaml = get().generateYaml()
      const saveResp = await fetch('/yaml', {
        method: 'POST',
        headers: { 'Content-Type': 'text/plain' },
        body: yaml,
      })
      if (!saveResp.ok) {
        set(s => ({ runLog: [...s.runLog, `Error: save failed (HTTP ${saveResp.status})`], isRunning: false }))
        return
      }
      set(s => ({ runLog: [...s.runLog, 'Starting pipeline...'] }))
      const runResp = await fetch('/run', { method: 'POST' })
      if (!runResp.ok) {
        set(s => ({ runLog: [...s.runLog, `Error: run failed (HTTP ${runResp.status})`], isRunning: false }))
        return
      }

      const poll = async () => {
        try {
          const res  = await fetch('/status')
          const data = await res.json() as { running: boolean; log: string[]; files: RunFiles | null }
          set({ runLog: data.log ?? [] })
          if (data.running) {
            setTimeout(poll, 500)
          } else {
            set({ isRunning: false, runFiles: data.files })
          }
        } catch (e) {
          set(s => ({ runLog: [...s.runLog, `Poll error: ${e}`], isRunning: false }))
        }
      }
      setTimeout(poll, 400)
    } catch (e) {
      set(s => ({ runLog: [...s.runLog, `Error: ${e}`], isRunning: false }))
    }
  },

  toggleRunPanel: () => set(s => ({ showRunPanel: !s.showRunPanel })),

  // ── History ───────────────────────────────────────────────────────────────
  undo: () => set(s => {
    if (!s.past.length) return {}
    const prev = s.past[s.past.length - 1]
    return {
      ...prev,
      past:         s.past.slice(0, -1),
      future:       [snapshot(s), ...s.future.slice(0, MAX_HISTORY - 1)],
      selectedDevRef: null,
    }
  }),

  redo: () => set(s => {
    if (!s.future.length) return {}
    const next = s.future[0]
    return {
      ...next,
      past:         [...s.past.slice(-(MAX_HISTORY - 1)), snapshot(s)],
      future:       s.future.slice(1),
      selectedDevRef: null,
    }
  }),

  // ── Workspace ─────────────────────────────────────────────────────────────
  clearAll: () => set(s => ({
    racks: [], wiringLayers: [], externalGroups: [],
    selectedDevRef: null, activeLayerIdx: null, vizLayerIdx: null,
    pickState: null, portAssignTarget: null,
    past:   [...s.past.slice(-(MAX_HISTORY - 1)), snapshot(s)],
    future: [],
  })),

  loadSampleData: () => {
    get().loadFromYaml(SAMPLE_DATA)
  },
}))
