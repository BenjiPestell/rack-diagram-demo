# Rack Visualisation System

A Python-based system for generating professional rack layout diagrams and network wiring diagrams from YAML configuration files using Graphviz.

## Overview

This system generates two types of diagrams:

1. **Rack Layout Diagrams** - Horizontal Visualisation of all racks showing front and rear panels with devices
2. **Wiring Diagrams** - Radial network topology diagrams showing device interconnections grouped by rack

## Configuration

### Basic Structure

```yaml
type_colors:
  pc: "#E8F4F8"
  pdu: "#AAAAAA"
  switch: "#B8D6D6"

racks:
  - rack:
      id: rack1
      name: Rack 1
      total_u: 42
    
    front:
      - name: Device Name
        start_u: 42
        units: 3
        type: pdu
    
    rear:
      - name: Switch
        start_u: 42
        units: 1
        type: switch

wiring_layers:
  - name: Visual Subnet Ethernet
    edge_color: "#7B1FA2"
    edge_width: "2.5"
    connections:
      - from: Switch
        to: PC
      - from: Switch
        to: Server
```

### Rack Configuration

**Top-level fields:**
- `type_colors` (optional) - Map of device types to hex colors
- `racks` (required) - List of rack definitions

**Rack object:**
- `id` - Unique identifier (e.g., "rack1", "rack2_rear")
- `name` - Display name (e.g., "Rack 1", "Rack 2 Rear")
- `total_u` - Total rack units (typically 42)
- `table_width` (optional) - SVG table width, default 240
- `device_width` (optional) - Device cell width, default 200
- `u_col_width` (optional) - Unit number column width, default 28
- `device_font_size` (optional) - Device name font size, default 13.5
- `unit_font_size` (optional) - Unit count font size, default 15
- `title_font_size` (optional) - Rack title font size, default 16
- `auto_scale_font` (optional) - Scale font for large devices, default true

**Device object:**
- `name` - Device name
- `start_u` - Starting unit (from top, e.g., 42)
- `units` - Number of rack units occupied
- `type` - Device type (used for color lookup in type_colors)
- `color` (optional) - Explicit hex color (overrides type color)

### Wiring Layer Configuration

**Layer fields:**
- `name` - Network name/title (e.g., "Visual Subnet Ethernet")
- `edge_color` (optional) - Connection line color, default "#333333"
- `edge_style` (optional) - Connection style (solid, dashed, dotted), default "solid"
- `edge_width` (optional) - Connection line width, default "2.0"
- `font_size` (optional) - Label font size, default 12
- `connections` (required) - List of connections

**Connection object:**
- `from` - Source device name
- `to` - Destination device name
- `label` (optional) - Connection label (e.g., port number)
- `color` (optional) - Per-connection color override
- `style` (optional) - Per-connection style override
- `width` (optional) - Per-connection width override

## Usage

### Generate Diagrams

```bash
python generate.py
```

This reads `checkers.yaml` and generates:
- `rack_layout.dot` - Horizontal rack layout diagram
- `{network_name}.dot` - One wiring diagram per network layer

### Render Diagrams

**Rack Layout (dot format):**
```bash
dot -Tpng rack_layout.dot -o rack_layout.png
```

**Wiring Diagrams (neato format for radial layout):**
```bash
neato -Tpng visual_subnet_ethernet.dot -o visual_subnet_ethernet.png
```

Use `dot` if you prefer hierarchical layout, but `neato` produces better radial/circular arrangements for wiring diagrams.

## Device Type Colors

Default type colors can be overridden in the YAML:

```yaml
type_colors:
  pc: "#E8F4F8"              # Light blue
  pdu: "#AAAAAA"             # Gray
  switch: "#B8D6D6"          # Teal
  shelf: "#ced3db"           # Light gray
  realtime: "#FFE8D8"        # Peach
  cable management: "#C4C4C4" # Medium gray
  customer: "#ffd9d6"        # Light pink
```

Devices can also have explicit colors that override type colors:

```yaml
- name: Special Device
  start_u: 10
  units: 2
  type: pc
  color: "#FF0000"  # Red, overrides type color
```

## Font

All diagrams use **Sinkin Sans 400 Regular** font throughout for consistency.

## Example YAML Structure

```yaml
type_colors:
  pc: "#E8F4F8"
  pdu: "#AAAAAA"
  switch: "#B8D6D6"

racks:
  - rack:
      id: rack1
      name: Rack 1
      total_u: 42
    
    front:
      - name: UPS
        start_u: 42
        units: 3
        type: pdu
      
      - name: Operator PC
        start_u: 27
        units: 4
        type: pc
      
      - name: Graphics Switch
        start_u: 3
        units: 1
        type: switch
    
    rear:
      - name: PDU A
        start_u: 42
        units: 1
        type: pdu
      
      - name: Network Switch
        start_u: 41
        units: 1
        type: switch

  - rack:
      id: rack2
      name: Rack 2
      total_u: 42
    
    front:
      - name: IG 1
        start_u: 20
        units: 4
        type: pc
    
    rear:
      - name: PDU B
        start_u: 42
        units: 1
        type: pdu

wiring_layers:
  - name: Graphics Network
    edge_color: "#7B1FA2"
    edge_width: "2.5"
    connections:
      - from: Graphics Switch 1
        to: Graphics Switch 2
      
      - from: Graphics Switch 1
        to: Operator PC
      
      - from: Graphics Switch 2
        to: IG 1
```

## Output Files

### rack_layout.dot
Graphviz diagram showing all racks horizontally with front and rear panels visible.

### {network_name}.dot
Graphviz diagram showing network topology for a specific wiring layer.

Each wiring diagram includes:
- Rack clusters containing devices
- Central hubs (devices with >1 connection) with thicker borders
- Peripheral devices connected to central hubs
- Inter-rack connections
- Connection counts on central nodes

## Requirements

- Python 3.6+
- PyYAML
- Graphviz (for rendering .dot files)

## Installation

```bash
pip install pyyaml
```

And install Graphviz:
- **macOS**: `brew install graphviz`
- **Linux**: `apt-get install graphviz`
- **Windows**: Download from https://graphviz.org/download/

## Notes

- Device names must be unique within a configuration
- Unit numbering starts at the top (U42 for 42U racks)
- Rack pairs are automatically spaced for visual clarity
- Central nodes in wiring diagrams are determined by connection count (>1 connection)
- Missing device properties are handled gracefully with warnings
- Colors use standard hex notation (#RRGGBB)

## Troubleshooting

**Issue: Device doesn't appear in layout**
- Check that `start_u` and `units` are correctly defined
- Verify no duplicate device names exist
- Check that the device name matches exactly in wiring connections

**Issue: Wiring diagram shows empty clusters**
- Verify device names in connections match exactly with device definitions
- Ensure devices are in `front` or `rear` lists

**Issue: Poor radial layout in wiring diagram**
- Use `neato` instead of `dot` for rendering
- Increase `sep` value in graph attributes if nodes overlap

## License

This project is open source.
