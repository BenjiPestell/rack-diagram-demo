import css from './RightPanel.module.css'
import { useDesignerStore } from '../../store/designerStore'
import PropertiesTab from './tabs/PropertiesTab'
import WiringTab from './tabs/WiringTab'
import ExternalTab from './tabs/ExternalTab'
import YAMLTab from './tabs/YAMLTab'

const TABS = [
  { id: 'properties', label: 'Properties' },
  { id: 'wiring',     label: 'Wiring' },
  { id: 'external',   label: 'External' },
  { id: 'yaml',       label: 'YAML' },
] as const

export default function RightPanel() {
  const activeTab    = useDesignerStore(s => s.activeTab)
  const setActiveTab = useDesignerStore(s => s.setActiveTab)

  return (
    <div className={css.panel}>
      <div className={css.tabs}>
        {TABS.map(t => (
          <button
            key={t.id}
            className={`${css.tab} ${activeTab === t.id ? css.tabActive : ''}`}
            onClick={() => setActiveTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className={css.content}>
        {activeTab === 'properties' && <PropertiesTab />}
        {activeTab === 'wiring'     && <WiringTab />}
        {activeTab === 'external'   && <ExternalTab />}
        {activeTab === 'yaml'       && <YAMLTab />}
      </div>
    </div>
  )
}
