// ─── Raw YAML shapes (as parsed from js-yaml) ───────────────────────────────

export interface RawDevice {
  name: string
  type?: string
  start_u?: number
  units?: number
  start?: number
  end?: number
  spacing?: number
  ports?: number
  port_notes?: Record<number, string>
  on_rails?: boolean
  cable_exit?: 'front' | 'rear'
  is_pattern?: boolean
}

export interface RawRack {
  id: string
  name?: string
  total_u?: number
  u_order?: 'bottom_top' | 'top_bottom'
}

export interface RawRackConfig {
  rack: RawRack
  front?: RawDevice[]
  rear?: RawDevice[]
}

export interface RawConnection {
  from: string
  to: string | string[]
  cable_type?: string
  edge_color?: string
  via_patch_from?: string
  via_patch_to?: string
  patch_port_from?: number
  patch_port_to?: number
  from_port?: number
  to_port?: number
}

export interface RawWiringLayer {
  name: string
  cable_type?: string
  edge_color?: string
  connections: RawConnection[]
}

export interface RawExternalDevice {
  name: string
  start?: number
  end?: number
}

export interface RawExternalGroup {
  name: string
  distance_from_racks?: number
  devices: RawExternalDevice[]
}

export interface RawConfig {
  racks: RawRackConfig[]
  wiring_layers?: RawWiringLayer[]
  external_devices?: RawExternalGroup[]
  cable_slack_length?: number
  standard_u_height?: number
  front_to_back_length?: number
  inter_rack_distance?: number
  rail_extension_length?: number
}

// ─── Expanded / processed types (after cluster expansion) ────────────────────

export interface DeviceInfo {
  name: string
  type?: string
  rackId: string
  rackName: string
  rackIdx: number
  face: 'front' | 'rear' | 'external'
  start_u?: number
  units: number
  located: boolean
  ports?: number
  port_notes?: Record<number, string>
  onRails: boolean
  cableExit: 'front' | 'rear'
  isPatchPanel: boolean
  totalU: number
  uOrder: 'bottom_top' | 'top_bottom'
  // external only
  distanceFromRacks?: number
  groupName?: string
}

export interface ConnectionEntry {
  peer: string
  layer: string
  cableType: string
  layerColor: string
  direction: '→' | '←' | '↔'
  patchFrom: string | null
  patchTo: string | null
  // patch-leg entries (PP selected)
  isPatchLeg?: boolean
  peerFrom?: string
  segFrom?: string
  segTo?: string
}

export type DeviceMap = Record<string, DeviceInfo>
export type ConnIndex = Record<string, ConnectionEntry[]>
export type ColorMap = Record<string, string>

// ─── Cable length ────────────────────────────────────────────────────────────

export interface CableBreakdown {
  vertical?: number
  verticalA?: number
  verticalB?: number
  frontToBack?: number
  horizontal?: number
  groupDist?: number
  rails?: number
  slack: number
}

export interface CableSegment {
  from: string
  to: string
  length: number | null
  breakdown: CableBreakdown
  note?: string
}

export interface CableResult {
  segments: CableSegment[]
  total: number | null
  isPatched: boolean
}

export interface CableConfig {
  interRack: number
  frontToBack: number
  slack: number
  uHeight: number
  railExt: number
}

// ─── Designer state types ────────────────────────────────────────────────────

export interface DesignerDevice {
  name: string
  type?: string
  start_u?: number
  units?: number
  start?: number
  end?: number
  spacing?: number
  ports?: number
  port_notes?: Record<number, string>
  on_rails?: boolean
  cable_exit?: 'front' | 'rear'
  is_pattern?: boolean
}

export interface DesignerRack {
  id: string
  name: string
  total_u: number
  u_order: 'bottom_top' | 'top_bottom'
  front: DesignerDevice[]
  rear: DesignerDevice[]
}

export interface DesignerConnection {
  from: string
  to: string | string[]   // single name, comma-separated list, or YAML array
  cable_type?: string
  edge_color?: string        // per-connection color override
  label?: string             // display label on wiring diagram
  via_patch_from?: string
  via_patch_to?: string
  patch_port_from?: number
  patch_port_to?: number
  from_port?: number
  to_port?: number
  from_ip?: string
  to_ip?: string
  start?: number             // cluster N expansion start
  end?: number               // cluster N expansion end
}

export interface DesignerWiringLayer {
  name: string
  cable_type?: string
  edge_color?: string
  connections: DesignerConnection[]
}

export interface DesignerExternalDevice {
  name: string
  type?: string              // device type (for color lookup)
  start?: number
  end?: number
}

export interface RunFiles {
  output: string[]
  pngs: {
    rack: string[]
    wiring: string[]
    ports: string[]
  }
}

export interface DesignerExternalGroup {
  name: string
  distance_from_racks: number
  devices: DesignerExternalDevice[]
}

export interface TypeEntry {
  type: string
  color: string
  units?: number
  ported?: boolean
}

export interface SelectedDevRef {
  dev: DesignerDevice
  rackId: string
  face: 'front' | 'rear'
  displayName: string
}

export interface PickState {
  layerIdx: number
  connIdx: number
  field: string
}
