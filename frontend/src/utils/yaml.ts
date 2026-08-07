import jsYaml from 'js-yaml'
import type { RawConfig, RawConnection, RawDevice, DesignerRack, DesignerWiringLayer, DesignerExternalGroup, DesignerConnection, TypeEntry } from '../types'

export function parseConfig(yamlText: string): RawConfig {
  const parsed = jsYaml.load(yamlText)
  if (!parsed || typeof parsed !== 'object') throw new Error('Invalid YAML')
  return parsed as unknown as RawConfig
}

// ─── Cluster expansion ───────────────────────────────────────────────────────

export function expandName(template: string, n: number): string {
  return template.replace(/\{N\}/g, String(n))
}

/** Generic expansion — for external devices (no start_u offset needed). */
export function expandDevices<T extends { name: string; start?: number; end?: number }>(
  devices: T[]
): T[] {
  const out: T[] = []
  for (const dev of devices) {
    if (dev.start != null && dev.end != null && dev.name.includes('{N}')) {
      for (let n = dev.start; n <= dev.end; n++) {
        out.push({ ...dev, name: expandName(dev.name, n), start: undefined, end: undefined })
      }
    } else {
      out.push(dev)
    }
  }
  return out
}

/**
 * Rack-device expansion. Like expandDevices, but also offsets start_u for each
 * cluster member so they don't all land on the same U position.
 * Mirrors the Python cable_length.py logic: step = units + spacing.
 */
export function expandRackDevices(devices: RawDevice[]): RawDevice[] {
  const out: RawDevice[] = []
  for (const dev of devices) {
    const { name, start, end, units = 1, spacing = 0, start_u } = dev
    if (start != null && end != null && name.includes('{N}')) {
      const step = units + spacing
      for (let i = 0, n = start; n <= end; n++, i++) {
        out.push({
          ...dev,
          name: expandName(name, n),
          start: undefined,
          end: undefined,
          start_u: start_u != null ? start_u - i * step : undefined,
        })
      }
    } else {
      out.push(dev)
    }
  }
  return out
}

// Expand {N}, {N+k}, {N-k} in a string — used by both designer and raw connection expansion
function expandNExpr(s: string, n: number): string {
  return s.replace(/\{N([+-]\d+)?\}/g, (_, offset) =>
    String(n + (offset ? parseInt(offset, 10) : 0)),
  )
}

// Normalise a connection's `to` field to an array of target name strings.
// Accepts: single string, YAML array, or comma-separated list ("A,B" or "A, B").
function toArray(to: string | string[] | undefined): string[] {
  if (!to) return []
  if (Array.isArray(to)) return to.map(s => s.trim()).filter(Boolean)
  // Split on comma with optional surrounding whitespace ("A,B", "A, B", "A ,B" all work)
  return to.split(/\s*,\s*/).map(s => s.trim()).filter(Boolean)
}

/** N-pattern regex — matches {N}, {N+3}, {N-1}, etc. */
const N_RE = /\{N([+-]\d+)?\}/

/**
 * Expand template connections into individual DesignerConnection objects.
 *
 * Handles:
 *   - {N}, {N+k}, {N-k} in from / to / via_patch_from / via_patch_to
 *   - Multi-target to (YAML array or comma-separated string)
 *
 * Each returned connection has to: string (never an array).
 * Used by WiringOverlay and Canvas wiredNames computation.
 */
export function expandDesignerConnections(connections: DesignerConnection[]): DesignerConnection[] {
  const out: DesignerConnection[] = []
  for (const c of connections) {
    const fromStr = String(c.from || '')
    const targets = toArray(c.to as string | string[] | undefined)

    // Does any field contain an {N…} expression?
    const hasN =
      N_RE.test(fromStr) ||
      targets.some(t => N_RE.test(t)) ||
      (c.via_patch_from ? N_RE.test(c.via_patch_from) : false) ||
      (c.via_patch_to   ? N_RE.test(c.via_patch_to)   : false) ||
      (c.from_ip        ? N_RE.test(c.from_ip)         : false) ||
      (c.to_ip          ? N_RE.test(c.to_ip)           : false)

    if (hasN && c.start != null && c.end != null) {
      for (let n = c.start; n <= c.end; n++) {
        const exp = (s: string) => expandNExpr(s, n)
        for (const t of targets) {
          out.push({
            ...c,
            from:           exp(fromStr),
            to:             exp(t),
            via_patch_from: c.via_patch_from ? exp(c.via_patch_from) : undefined,
            via_patch_to:   c.via_patch_to   ? exp(c.via_patch_to)   : undefined,
            from_ip:        c.from_ip        ? exp(c.from_ip)        : undefined,
            to_ip:          c.to_ip          ? exp(c.to_ip)          : undefined,
          })
        }
      }
    } else {
      // No N-expansion — still fan out multi-target to
      for (const t of targets) {
        out.push({ ...c, to: t })
      }
    }
  }
  return out
}

export function expandConnections(connections: RawConnection[], layerCableType?: string): RawConnection[] {
  const out: RawConnection[] = []
  for (const conn of connections) {
    const fromStr = String(conn.from || '')
    const toRaw   = conn.to
    // Support comma-separated string in addition to YAML array
    const toArr: string[] = Array.isArray(toRaw)
      ? toRaw.map(String)
      : toRaw ? toArray(String(toRaw)) : []
    const connAny = conn as unknown as Record<string, unknown>
    const start = connAny['start'] as number | undefined
    const end   = connAny['end']   as number | undefined

    // Detect any {N…} expression in from, any target, via_patch, or IP fields
    const hasN =
      N_RE.test(fromStr) ||
      toArr.some(t => N_RE.test(t)) ||
      (conn.via_patch_from ? N_RE.test(conn.via_patch_from) : false) ||
      (conn.via_patch_to   ? N_RE.test(conn.via_patch_to)   : false) ||
      (conn.from_ip        ? N_RE.test(conn.from_ip)        : false) ||
      (conn.to_ip          ? N_RE.test(conn.to_ip)          : false)

    if (hasN && start != null && end != null) {
      for (let n = start; n <= end; n++) {
        const exp = (s: string) => expandNExpr(s, n)
        for (const t of toArr) {
          out.push({
            ...conn,
            from:           exp(fromStr),
            to:             exp(t),
            via_patch_from: conn.via_patch_from ? exp(conn.via_patch_from) : conn.via_patch_from,
            via_patch_to:   conn.via_patch_to   ? exp(conn.via_patch_to)   : conn.via_patch_to,
            from_ip:        conn.from_ip        ? exp(conn.from_ip)        : conn.from_ip,
            to_ip:          conn.to_ip          ? exp(conn.to_ip)          : conn.to_ip,
            cable_type:     conn.cable_type || layerCableType,
          })
        }
      }
    } else {
      for (const t of toArr) {
        out.push({ ...conn, to: t, cable_type: conn.cable_type || layerCableType })
      }
    }
  }
  return out
}

// ─── YAML serialisation (designer state → YAML string) ───────────────────────

interface SerialiseInput {
  racks: DesignerRack[]
  wiringLayers: DesignerWiringLayer[]
  externalGroups: DesignerExternalGroup[]
  typeEntries: TypeEntry[]
  cableTypes: string[]
  interRackDistance: number
  cableSlackLength: number
  frontToBackLength: number
  railExtensionLength: number
  standardUHeight: number
  projectTitle: string
  showTypeKey: boolean
}

function indent(s: string, n: number) {
  const pad = ' '.repeat(n)
  return s.split('\n').map(l => (l.trim() ? pad + l : l)).join('\n')
}

function yamlStr(s: string): string {
  // Quote if contains special chars or starts with special chars
  if (/[:{}\[\],&*#?|<>=!%@`]/.test(s) || /^\s|\s$/.test(s) || s === '') {
    return `"${s.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`
  }
  return s
}

export function serializeToYaml(input: SerialiseInput): string {
  const lines: string[] = []

  // Global params
  lines.push(`inter_rack_distance: ${input.interRackDistance}`)
  lines.push(`cable_slack_length: ${input.cableSlackLength}`)
  lines.push(`front_to_back_length: ${input.frontToBackLength}`)
  lines.push(`rail_extension_length: ${input.railExtensionLength}`)
  lines.push(`standard_u_height: ${input.standardUHeight}`)
  lines.push('')

  // Project config — the pipeline reads these when building the combined diagram
  lines.push(`show_type_key: ${input.showTypeKey}`)
  if (input.projectTitle.trim()) {
    lines.push(`project_title: ${yamlStr(input.projectTitle)}`)
  }
  lines.push('')

  // Cable types
  if (input.cableTypes.length) {
    lines.push('cable_types:')
    for (const ct of input.cableTypes) lines.push(`  - ${yamlStr(ct)}`)
    lines.push('')
  }

  // Type colors
  if (input.typeEntries.length) {
    lines.push('type_colors:')
    for (const e of input.typeEntries) {
      lines.push(`  ${yamlStr(e.type)}:`)
      lines.push(`    color: "${e.color}"`)
      if (e.units && e.units !== 1) lines.push(`    units: ${e.units}`)
      if (e.ported) lines.push(`    ported: true`)
    }
    lines.push('')
  }

  // Racks
  lines.push('racks:')
  for (const rack of input.racks) {
    lines.push(`  - rack:`)
    lines.push(`      id: ${rack.id}`)
    lines.push(`      name: ${yamlStr(rack.name)}`)
    lines.push(`      total_u: ${rack.total_u}`)
    if (rack.u_order !== 'bottom_top') lines.push(`      u_order: ${rack.u_order}`)

    for (const face of ['front', 'rear'] as const) {
      const devs = rack[face]
      if (!devs.length) continue
      lines.push(`    ${face}:`)
      for (const dev of devs) {
        lines.push(`      - name: ${yamlStr(dev.name)}`)
        if (dev.type)    lines.push(`        type: ${yamlStr(dev.type)}`)
        if (dev.start_u != null) lines.push(`        start_u: ${dev.start_u}`)
        if (dev.units != null)   lines.push(`        units: ${dev.units}`)
        if (dev.start != null)   lines.push(`        start: ${dev.start}`)
        if (dev.end != null)     lines.push(`        end: ${dev.end}`)
        if (dev.spacing)         lines.push(`        spacing: ${dev.spacing}`)
        if (dev.cable_exit && dev.cable_exit !== 'rear') lines.push(`        cable_exit: ${dev.cable_exit}`)
        if (dev.on_rails)        lines.push(`        on_rails: true`)
        if (dev.ports)           lines.push(`        ports: ${dev.ports}`)
        if (dev.port_notes && Object.keys(dev.port_notes).length) {
          lines.push(`        port_notes:`)
          for (const [p, note] of Object.entries(dev.port_notes))
            lines.push(`          ${p}: ${yamlStr(String(note))}`)
        }
      }
    }
  }
  lines.push('')

  // External devices
  if (input.externalGroups.length) {
    lines.push('external_devices:')
    for (const g of input.externalGroups) {
      lines.push(`  - name: ${yamlStr(g.name)}`)
      if (g.distance_from_racks) lines.push(`    distance_from_racks: ${g.distance_from_racks}`)
      if (g.devices.length) {
        lines.push(`    devices:`)
        for (const d of g.devices) {
          lines.push(`      - name: ${yamlStr(d.name)}`)
          if (d.type)          lines.push(`        type: ${yamlStr(d.type)}`)
          if (d.start != null) lines.push(`        start: ${d.start}`)
          if (d.end   != null) lines.push(`        end: ${d.end}`)
        }
      }
    }
    lines.push('')
  }

  // Wiring layers
  if (input.wiringLayers.length) {
    lines.push('wiring_layers:')
    for (const layer of input.wiringLayers) {
      lines.push(`  - name: ${yamlStr(layer.name)}`)
      if (layer.edge_color) lines.push(`    edge_color: "${layer.edge_color}"`)
      if (layer.cable_type) lines.push(`    cable_type: ${yamlStr(layer.cable_type)}`)
      if (layer.connections.length) {
        lines.push(`    connections:`)
        for (const c of layer.connections) {
          lines.push(`      - from: ${yamlStr(c.from)}`)
          if (Array.isArray(c.to)) {
            lines.push(`        to:`)
            for (const t of c.to) lines.push(`          - ${yamlStr(t)}`)
          } else {
            lines.push(`        to: ${yamlStr(c.to)}`)
          }
          if (c.cable_type)            lines.push(`        cable_type: ${yamlStr(c.cable_type)}`)
          if (c.edge_color)            lines.push(`        edge_color: "${c.edge_color}"`)
          if (c.label)                 lines.push(`        label: ${yamlStr(c.label)}`)
          if (c.start != null)         lines.push(`        start: ${c.start}`)
          if (c.end   != null)         lines.push(`        end: ${c.end}`)
          if (c.via_patch_from)        lines.push(`        via_patch_from: ${yamlStr(c.via_patch_from)}`)
          if (c.via_patch_to)          lines.push(`        via_patch_to: ${yamlStr(c.via_patch_to)}`)
          if (c.patch_port_from != null) lines.push(`        patch_port_from: ${c.patch_port_from}`)
          if (c.patch_port_to   != null) lines.push(`        patch_port_to: ${c.patch_port_to}`)
          if (c.from_port != null)     lines.push(`        from_port: ${c.from_port}`)
          if (c.to_port   != null)     lines.push(`        to_port: ${c.to_port}`)
          if (c.from_ip)               lines.push(`        from_ip: ${yamlStr(c.from_ip)}`)
          if (c.to_ip)                 lines.push(`        to_ip: ${yamlStr(c.to_ip)}`)
        }
      }
    }
  }

  return lines.join('\n')
}

// Suppress unused warning on indent — kept for potential future use
void indent
