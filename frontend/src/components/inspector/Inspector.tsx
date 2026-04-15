import { useState, useEffect, useCallback } from 'react'
import css from './Inspector.module.css'
import Topbar from './Topbar'
import ConfigDrawer from './ConfigDrawer'
import CanvasArea from './CanvasArea'
import BottomSheet from './BottomSheet'
import type { RawConfig, DeviceMap, ConnIndex, CableConfig } from '../../types'
import { parseConfig } from '../../utils/yaml'
import { buildDeviceMap, buildConnectionIndex } from '../../utils/deviceMap'

const DEFAULT_CFG: CableConfig = {
  interRack:   2.5,
  frontToBack: 0.5,
  slack:       0.2,
  uHeight:     0.045,
  railExt:     0.5,
}

const DEFAULT_TYPE_COLORS: Record<string, string> = {
  'Switch':        '#1f6feb',
  'Patch panel':   '#388bfd',
  'Server':        '#2ea043',
  'PDU':           '#d29922',
  'UPS':           '#8b949e',
}

export default function Inspector() {
  const [,            setYamlText]    = useState<string>('')
  const [config,      setConfig]      = useState<RawConfig | null>(null)
  const [error,       setError]       = useState<string | null>(null)
  const [connected,   setConnected]   = useState(false)
  const [showConfig,  setShowConfig]  = useState(false)
  const [cableCfg,    setCableCfg]    = useState<CableConfig>(DEFAULT_CFG)
  const [selectedDev, setSelectedDev] = useState<string | null>(null)
  const [deviceMap,   setDeviceMap]   = useState<DeviceMap>({})
  const [connIndex,   setConnIndex]   = useState<ConnIndex>({})
  const [typeColors,  setTypeColors]  = useState<Record<string, string>>(DEFAULT_TYPE_COLORS)

  const load = useCallback(async () => {
    try {
      const resp = await fetch('/yaml')
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const text = await resp.text()
      setYamlText(text)
      setConnected(true)

      const parsed = parseConfig(text)
      setConfig(parsed)
      setError(null)

      setCableCfg(prev => ({
        interRack:   parsed.inter_rack_distance   ?? prev.interRack,
        frontToBack: parsed.front_to_back_length  ?? prev.frontToBack,
        slack:       parsed.cable_slack_length     ?? prev.slack,
        uHeight:     parsed.standard_u_height      ?? prev.uHeight,
        railExt:     parsed.rail_extension_length  ?? prev.railExt,
      }))

      const dm = buildDeviceMap(parsed)
      setDeviceMap(dm)
      setTypeColors({ ...DEFAULT_TYPE_COLORS })
      setConnIndex(buildConnectionIndex(parsed, DEFAULT_TYPE_COLORS))
    } catch (e) {
      setConnected(false)
      setError(String(e))
    }
  }, [])

  useEffect(() => { load() }, [load])

  function handleSelect(name: string) {
    setSelectedDev(prev => prev === name ? null : name)
  }

  const selectedDevInfo = selectedDev ? deviceMap[selectedDev] : null

  return (
    <div className={css.root}>
      <Topbar
        connected={connected}
        onReload={load}
        onToggleConfig={() => setShowConfig(v => !v)}
      />

      {showConfig && (
        <ConfigDrawer config={cableCfg} onChange={setCableCfg} />
      )}

      {error && (
        <div style={{ padding: '8px 14px', background: '#3d1a1a', color: '#f85149', fontSize: 12 }}>
          {error}
        </div>
      )}

      <div className={css.main}>
        {config && (
          <CanvasArea
            config={config}
            deviceMap={deviceMap}
            typeColors={typeColors}
            selectedDev={selectedDev}
            onSelect={handleSelect}
          />
        )}
      </div>

      <BottomSheet
        dev={selectedDevInfo}
        connIndex={connIndex}
        deviceMap={deviceMap}
        cfg={cableCfg}
        onClose={() => setSelectedDev(null)}
      />
    </div>
  )
}
