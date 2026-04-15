import type { DeviceInfo, CableSegment, CableResult, CableConfig, CableBreakdown } from '../types'

// ─── Geometry helpers ────────────────────────────────────────────────────────

function uDistToRackBottom(dev: DeviceInfo): number {
  if (!dev.located || dev.start_u == null) return 0
  if (dev.uOrder === 'top_bottom') {
    const physBottom = dev.start_u + dev.units - 1
    return Math.max(0, dev.totalU - physBottom)
  }
  const physBottom = dev.start_u - dev.units + 1
  return Math.max(0, physBottom - 1)
}

function intraRackUDelta(a: DeviceInfo, b: DeviceInfo): number {
  if (!a.located || !b.located || a.start_u == null || b.start_u == null) return 0
  let botA: number, botB: number
  if (a.uOrder === 'top_bottom') {
    botA = a.start_u + a.units - 1
    botB = b.start_u + b.units - 1
  } else {
    botA = a.start_u - a.units + 1
    botB = b.start_u - b.units + 1
  }
  return Math.abs(botA - botB)
}

export function steppedSlack(rawTotal: number, slackMax: number): number {
  if (rawTotal < 1.0) return 0
  if (rawTotal < 3.0) return slackMax * 0.25
  if (rawTotal < 10.0) return slackMax * 0.5
  return slackMax
}

export function roundCableLength(length: number): number {
  if (length <= 1.0) return Math.ceil(length * 5) / 5
  return Math.ceil(length * 2) / 2
}

// ─── Per-segment calculator ──────────────────────────────────────────────────

export function calcCableLength(
  devA: DeviceInfo,
  devB: DeviceInfo,
  cfg: CableConfig
): { length: number | null; breakdown: CableBreakdown; note?: string } {
  const aExt = devA.face === 'external'
  const bExt = devB.face === 'external'

  if (aExt && bExt) return { length: null, breakdown: { slack: 0 }, note: 'ext↔ext' }

  // Patch panels adopt the peer's cable exit
  let exitA = devA.cableExit
  let exitB = devB.cableExit
  if (devA.isPatchPanel && !devB.isPatchPanel) exitA = exitB
  if (devB.isPatchPanel && !devA.isPatchPanel) exitB = exitA

  let vertical = 0, verticalA = 0, verticalB = 0, horizontal = 0,
      frontToBack = 0, groupDist = 0, railExt = 0

  if (aExt || bExt) {
    const rackDev = aExt ? devB : devA
    const extDev  = aExt ? devA : devB
    const rackExit = aExt ? exitB : exitA
    if (!rackDev.located) return { length: null, breakdown: { slack: 0 }, note: 'unpositioned' }
    groupDist = extDev.distanceFromRacks ?? 10
    verticalA = uDistToRackBottom(rackDev) * cfg.uHeight
    if (rackExit === 'front') frontToBack = cfg.frontToBack
    if (rackDev.onRails) railExt += cfg.railExt
    const raw = verticalA + frontToBack + groupDist + railExt
    const slack = steppedSlack(raw, cfg.slack)
    return {
      length: roundCableLength(raw + slack),
      breakdown: { verticalA, frontToBack: frontToBack || undefined, groupDist, rails: railExt || undefined, slack },
      note: 'ext',
    }
  }

  if (!devA.located || !devB.located) return { length: null, breakdown: { slack: 0 }, note: 'unpositioned' }

  const breakdown: CableBreakdown = { slack: 0 }

  if (devA.rackId === devB.rackId) {
    // INTRA-RACK
    if (exitA === exitB) {
      vertical = intraRackUDelta(devA, devB) * cfg.uHeight
      breakdown.vertical = vertical
    } else {
      vertical = intraRackUDelta(devA, devB) * cfg.uHeight
      breakdown.vertical = vertical
      frontToBack = cfg.frontToBack
      breakdown.frontToBack = frontToBack
    }
  } else {
    // INTER-RACK
    verticalA = uDistToRackBottom(devA) * cfg.uHeight
    verticalB = uDistToRackBottom(devB) * cfg.uHeight
    breakdown.verticalA = verticalA
    breakdown.verticalB = verticalB
    const rackDelta = Math.abs(devA.rackIdx - devB.rackIdx)
    horizontal = rackDelta * cfg.interRack
    breakdown.horizontal = horizontal
    if (exitA === 'front') frontToBack += cfg.frontToBack
    if (exitB === 'front') frontToBack += cfg.frontToBack
    if (frontToBack > 0) breakdown.frontToBack = frontToBack
  }

  if (devA.onRails) railExt += cfg.railExt
  if (devB.onRails) railExt += cfg.railExt
  if (railExt > 0) breakdown.rails = railExt

  const raw = vertical + verticalA + verticalB + frontToBack + horizontal + groupDist + railExt
  const slack = steppedSlack(raw, cfg.slack)
  breakdown.slack = slack
  return { length: roundCableLength(raw + slack), breakdown }
}

// ─── Patch-aware multi-segment calculator ────────────────────────────────────

export function calcPatchedCableLength(
  conn: {
    peer: string
    patchFrom: string | null
    patchTo: string | null
    direction: '→' | '←' | '↔'
    isPatchLeg?: boolean
    peerFrom?: string
  },
  thisName: string,
  deviceMap: Record<string, DeviceInfo>,
  cfg: CableConfig
): CableResult {
  const { patchFrom, patchTo } = conn

  if (!patchFrom && !patchTo) {
    const devA = deviceMap[thisName]
    const devB = deviceMap[conn.peer]
    if (!devA || !devB) return { segments: [], total: null, isPatched: false }
    const { length, breakdown, note } = calcCableLength(devA, devB, cfg)
    return {
      segments: [{ from: thisName, to: conn.peer, length, breakdown, note }],
      total: length,
      isPatched: false,
    }
  }

  let orderedNames: string[]
  if (conn.isPatchLeg && conn.peerFrom != null) {
    orderedNames = patchFrom && patchTo
      ? [conn.peerFrom, patchFrom, patchTo, conn.peer]
      : patchFrom
        ? [conn.peerFrom, patchFrom, conn.peer]
        : [conn.peerFrom, patchTo!, conn.peer]
  } else if (conn.direction === '→') {
    orderedNames = patchFrom && patchTo
      ? [thisName, patchFrom, patchTo, conn.peer]
      : patchFrom
        ? [thisName, patchFrom, conn.peer]
        : [thisName, patchTo!, conn.peer]
  } else {
    orderedNames = patchFrom && patchTo
      ? [conn.peer, patchFrom, patchTo, thisName]
      : patchFrom
        ? [conn.peer, patchFrom, thisName]
        : [conn.peer, patchTo!, thisName]
  }

  const segments: CableSegment[] = []
  let total = 0
  let anyNull = false

  for (let i = 0; i < orderedNames.length - 1; i++) {
    const aName = orderedNames[i]
    const bName = orderedNames[i + 1]
    const devA = deviceMap[aName]
    const devB = deviceMap[bName]
    if (!devA || !devB) { anyNull = true; continue }
    const { length, breakdown, note } = calcCableLength(devA, devB, cfg)
    segments.push({ from: aName, to: bName, length, breakdown, note })
    if (length == null) anyNull = true
    else total += length
  }

  return { segments, total: anyNull ? null : total, isPatched: true }
}

// ─── Port schedule ───────────────────────────────────────────────────────────

export interface PortUsage {
  explicit: number | null
  sideA: string
  sideAPort: number | null
  sideB: string | null
  sideBPort: number | null
  layerColor: string
  layerName: string
}

export interface PortScheduleResult {
  schedule: Record<number, PortUsage>
  totalPorts: number
}

export function computePortSchedule(
  devName: string,
  totalPorts: number,
  connIndex: Record<string, import('../types').ConnectionEntry[]>,
  _colorMap: Record<string, string>
): PortScheduleResult {
  const usages: PortUsage[] = []
  const allConns = connIndex[devName] || []

  for (const conn of allConns) {
    if (conn.isPatchLeg) continue
    const layerColor = conn.layerColor
    const layerName  = conn.layer

    if (conn.direction === '→') {
      usages.push({
        explicit: null,
        sideA: conn.peer, sideAPort: null,
        sideB: null, sideBPort: null,
        layerColor, layerName,
      })
    } else if (conn.direction === '←') {
      usages.push({
        explicit: null,
        sideA: conn.peer, sideAPort: null,
        sideB: null, sideBPort: null,
        layerColor, layerName,
      })
    }
  }

  // Auto-assign: manual-first, then fill gaps
  const schedule: Record<number, PortUsage> = {}
  const manuallyAssigned = new Set<number>()

  for (const u of usages) {
    if (u.explicit != null && u.explicit >= 1 && u.explicit <= totalPorts) {
      schedule[u.explicit] = u
      manuallyAssigned.add(u.explicit)
    }
  }

  let nextPort = 1
  for (const u of usages) {
    if (u.explicit != null) continue
    while (nextPort <= totalPorts && manuallyAssigned.has(nextPort)) nextPort++
    if (nextPort <= totalPorts) {
      schedule[nextPort] = u
      nextPort++
    }
  }

  return { schedule, totalPorts }
}
