# Rack Diagram Generator with Wiring Layers (WIP)

Enhanced rack diagram generator that produces both physical rack layouts and logical wiring diagrams.

## Features

- **Single or Multiple Racks**: Define one or more racks in the same configuration
- **Rack Layout Diagrams**: Visual representation of physical device placement
  - Individual rack diagrams
  - Multi-rack overview showing all racks side-by-side
- **Wiring Layer Diagrams**: Network/connection topology diagrams showing:
  - Data networks (ethernet, fibre channel, etc.)
  - Management networks (IPMI, BMC, etc.)
  - Power distribution
  - Cross-rack connections
  - Any custom connection topology
- **Rack Grouping**: Devices automatically grouped by rack in wiring diagrams with readable rack names

## Usage

1. Define your racks and devices in `rack.yaml`
2. Run the generator:
   ```bash
   python rack_with_wiring.py
   ```
3. Convert DOT files to images:
   ```bash
   # Individual racks
   dot -Tpng rack_rack1_front.dot -o rack1_front.png
   dot -Tpng rack_rack2_rear.dot -o rack2_rear.png
   
   # Multi-rack overview
   dot -Tpng rack_layout_all.dot -o rack_layout_all.png
   
   # Wiring diagrams
   dot -Tpng wiring_visual_subnet_ethernet.dot -o wiring_visual_subnet.png
   dot -Tpng wiring_management_network.dot -o wiring_management.png
   ```

Or use SVG format for scalable vector graphics:
```bash
dot -Tsvg rack_rack1_front.dot -o rack1_front.svg
```

## YAML Structure

### Rack Configuration

```yaml
racks:
  - rack:
      id: rack1_front          # Required: unique identifier
      name: Rack 1 Front       # Display name
      total_u: 40
      
      # Optional layout tuning
      table_width: 300
      device_width: 260
      u_col_width: 28
      
      # Optional font tuning
      device_font_size: 14
      unit_font_size: 16
      title_font_size: 20
      auto_scale_font: true    # Scales font for larger devices
    
    devices:
      - name: Server A
        start_u: 10            # Top U position
        units: 5               # Height in rack units
        color: "#ced3db"       # Optional background color
      # ... more devices
  
  # Add more racks as needed
  - rack:
      id: rack2_rear
      name: Rack 2 Rear
      total_u: 40
    
    devices:
      - name: Storage Array
        start_u: 10
        units: 8
        color: "#FFE5B4"
```

**Note:** For a single rack, just include one item in the `racks:` array.

### Wiring Layers

Define one or more wiring layers to show different connection topologies:

```yaml
wiring_layers:
  - name: Visual Subnet (Ethernet)
    
    # Optional styling for entire layer
    node_color: "#E8F4F8"      # Default node fill color
    node_shape: "box"           # box, circle, ellipse, etc.
    node_style: "rounded,filled"
    edge_color: "#2E86AB"       # Default edge color
    edge_style: "solid"         # solid, dashed, dotted
    edge_width: "2.5"           # Line width
    font_size: 11
    
    # Connections between devices
    connections:
      - from: Server A
        to: Server B
        label: "1Gb/s"          # Optional connection label
        
      # Override styling per connection
      - from: Server B
        to: Server C
        label: "10Gb/s"
        color: "#FF6B35"        # Custom color for this connection
        width: "3.5"            # Custom width
        style: "dashed"         # Custom style
```

## Wiring Layer Options

### Global Layer Styling

- `name`: Layer name (required)
- `show_rack_labels`: Show rack groupings in multi-rack setups (default: true)
- `node_color`: Default fill color for nodes (hex color)
- `node_shape`: Node shape (`box`, `circle`, `ellipse`, `diamond`, etc.)
- `node_style`: Node style (`rounded,filled`, `filled`, `solid`, etc.)
- `edge_color`: Default edge color (hex color)
- `edge_style`: Edge style (`solid`, `dashed`, `dotted`, `bold`)
- `edge_width`: Edge thickness (number as string)
- `font_size`: Font size for labels

### Connection Options

- `from`: Source device name (required)
- `to`: Destination device name (required)
- `label`: Connection label (port, speed, cable type, etc.)
- `color`: Override edge color for this connection
- `style`: Override edge style for this connection
- `width`: Override edge width for this connection

## Example Wiring Layers

### Data Network
```yaml
- name: Visual Subnet (Ethernet)
  edge_color: "#2E86AB"
  connections:
    - from: PC1
      to: PC2
      label: "1Gb/s"
```

### Management Network
```yaml
- name: Management Network
  edge_color: "#F57C00"
  edge_style: "dashed"
  connections:
    - from: Switch
      to: Server1
      label: "IPMI"
```

### Power Distribution
```yaml
- name: Power Distribution
  edge_color: "#C62828"
  edge_width: "3.0"
  connections:
    - from: PDU-A
      to: Server1
      label: "240V"
```

## Output Files

- `rack_<rack_id>.dot` / `.png`: Individual rack layouts (one per rack)
- `rack_layout_all.dot` / `.png`: All racks shown side-by-side (multi-rack only)
- `wiring_<layer_name>.dot` / `.png`: One file per wiring layer

## Tips

1. **Color Coding**: Use consistent colors across layers to identify device types
2. **Connection Labels**: Add bandwidth, port numbers, or cable IDs for documentation
3. **Multiple Layers**: Create separate layers for different concerns (data, management, power)
4. **External Devices**: Reference devices not in the rack (switches, PDUs) by name in connections
5. **Custom Styling**: Override colors/styles per connection to highlight critical paths
6. **Multi-Rack Setup**: Use unique rack IDs and enable `show_rack_labels` in wiring layers
7. **Cross-Rack Links**: Highlight uplinks between racks with different colors/widths
8. **Rack Grouping**: Wiring diagrams automatically group devices by rack with dashed borders

## Requirements

- Python 3.6+
- PyYAML: `pip install pyyaml`
- Graphviz (for rendering): `apt-get install graphviz` or `brew install graphviz`