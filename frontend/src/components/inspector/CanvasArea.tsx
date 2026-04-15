import css from './CanvasArea.module.css'
import type { RawConfig, DeviceInfo, DeviceMap } from '../../types'
import { expandRackDevices } from '../../utils/yaml'

const U_HEIGHT_PX = 14

interface Props {
  config: RawConfig
  deviceMap: DeviceMap
  typeColors: Record<string, string>
  selectedDev: string | null
  onSelect: (name: string) => void
}

export default function CanvasArea({ config, deviceMap, typeColors, selectedDev, onSelect }: Props) {
  return (
    <div className={css.canvas}>
      {(config.racks || []).map((rackCfg) => {
        const rackId   = rackCfg.rack.id
        const rackName = rackCfg.rack.name || rackId
        const totalU   = rackCfg.rack.total_u ?? 42
        const uOrder   = rackCfg.rack.u_order ?? 'bottom_top'
        const uNums    = uOrder === 'bottom_top'
          ? Array.from({ length: totalU }, (_, i) => totalU - i)
          : Array.from({ length: totalU }, (_, i) => i + 1)

        const unpositioned: DeviceInfo[] = []

        const renderFace = (face: 'front' | 'rear') => {
          const raw = rackCfg[face] ?? []
          const devs = expandRackDevices(raw)
          const positioned = devs.filter(d => d.start_u != null && d.units != null)
          const unpos = devs.filter(d => d.start_u == null || d.units == null)
          unpos.forEach(d => {
            const info = deviceMap[d.name]
            if (info) unpositioned.push(info)
          })

          // Build slot map
          const slotMap: Record<number, DeviceInfo> = {}
          for (const d of positioned) {
            const info = deviceMap[d.name]
            if (!info) continue
            slotMap[d.start_u!] = info
          }

          return (
            <div className={css.faceCol}>
              <div className={`${css.faceLabel} ${face === 'rear' ? css.faceLabelRight : ''}`}>
                {face === 'front' ? '► FRONT' : 'REAR ◄'}
              </div>
              <div className={css.uGrid} style={{ position: 'relative' }}>
                {uNums.map(u => (
                  <div key={u} className={css.uRow}>
                    <div className={css.uNum} translate="no">{u}</div>
                    <div className={css.uSlot} />
                  </div>
                ))}
                {/* Absolute device overlays */}
                {positioned.map(d => {
                  const info = deviceMap[d.name]
                  if (!info) return null
                  const startU = d.start_u!
                  const units  = d.units!
                  const color  = typeColors[info.type ?? ''] ?? '#3a3f47'

                  let topIdx: number
                  if (uOrder === 'bottom_top') {
                    topIdx = totalU - startU
                  } else {
                    topIdx = startU - 1
                  }

                  const top    = topIdx * U_HEIGHT_PX
                  const height = units * U_HEIGHT_PX

                  return (
                    <div
                      key={d.name}
                      className={`${css.device} ${selectedDev === d.name ? css.deviceSelected : ''}`}
                      style={{ top, height, background: color, color: '#fff' }}
                      onClick={() => onSelect(d.name)}
                      title={d.name}
                    >
                      {d.name}
                    </div>
                  )
                })}
              </div>
            </div>
          )
        }

        return (
          <div key={rackId} className={css.rackCol}>
            <div className={css.rackLabel}>{rackName}</div>
            <div className={css.rackBody}>
              {renderFace('front')}
              {renderFace('rear')}
            </div>

            {/* Unpositioned strip */}
            {unpositioned.length > 0 && (
              <div className={css.strip}>
                <div className={css.stripHeader}>UNPOSITIONED</div>
                {unpositioned.map(dev => (
                  <div
                    key={dev.name}
                    className={`${css.stripItem} ${selectedDev === dev.name ? css.stripItemSelected : ''}`}
                    onClick={() => onSelect(dev.name)}
                  >
                    <div
                      className={css.stripDot}
                      style={{ background: typeColors[dev.type ?? ''] ?? '#3a3f47' }}
                    />
                    {dev.name}
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
