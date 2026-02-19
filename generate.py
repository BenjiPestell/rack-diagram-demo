import yaml
import os
import csv
import json
from collections import defaultdict

# -------------------------------------------------
# Load config
# -------------------------------------------------
def load_config():
    with open("system.yaml") as f:
        return yaml.safe_load(f)
        
# -------------------------------------------------
# Build device map
# -------------------------------------------------
def build_device_map(racks_config):
    """
    Build a map of device name -> {rack_id, device_info}
    """
    all_devices = {}
    for rack_config in racks_config:
        rack_id = rack_config["rack"].get("id", "rack")
        
        for side in ['front', 'rear']:
            if side in rack_config:
                for dev in rack_config[side]:
                    dev_copy = dev.copy()
                    dev_copy["rack_id"] = rack_id
                    dev_copy["side"] = side
                    all_devices[dev["name"]] = dev_copy
    
    return all_devices

# -------------------------------------------------
# Get device color based on type or explicit color
# -------------------------------------------------
def get_device_color(device, type_colors):
    """
    Determine device color with priority:
    1. Explicit 'color' attribute in device
    2. Color based on device 'type' from type_colors mapping
    3. Default white if neither specified
    """
    if "color" in device:
        return device["color"]
    
    if "type" in device:
        device_type = device["type"]
        if device_type in type_colors:
            return type_colors[device_type]
    
    return "#FFFFFF"

# -------------------------------------------------
# Validation / occupancy
# -------------------------------------------------
def build_occupancy(devices, total_u):
    """
    Build map: U number -> device
    """
    slots = {}
    for dev in devices:
        name = dev["name"]
        try:
            start = dev["start_u"]
            units = dev["units"]
            
            if units < 1:
                raise ValueError(f"{name} has invalid unit size")
            
            for u in range(start, start - units, -1):
                if u < 1:
                    raise ValueError(f"{name} exceeds bottom of rack")
                if u in slots:
                    raise ValueError(f"U{u} conflict between {slots[u]['name']} and {name}")
                slots[u] = dev
        except:
            print(f"Skipping layout for device '{name}'. Missing properties.")
    
    return slots

# -------------------------------------------------
# DOT Generator - Multi-Rack Layout (Front + Rear Horizontal)
# -------------------------------------------------
def generate_rack_layout_dot(racks_config, type_colors):
    """
    Generate a single diagram showing all racks horizontally:
    Rack 1 Front | Rack 1 Rear | Spacer | Rack 2 Front | Rack 2 Rear | Spacer | ...
    """
    lines = []
    
    # Graph header
    lines.append("digraph rack_layout {")
    lines.append("")
    lines.append("  graph [")
    lines.append("    rankdir=TB,")
    lines.append("    nodesep=0.3,")
    lines.append("    ranksep=0,")
    lines.append("    bgcolor=\"white\"")
    lines.append("  ];")
    lines.append("")
    lines.append("  node [")
    lines.append("    shape=plain,")
    lines.append("    fontname=\"Sinkin Sans 400 Regular\"")
    lines.append("  ];")
    lines.append("")
    
    # Generate each rack (front and rear)
    for rack_config in racks_config:
        rack = rack_config["rack"]
        rack_id = rack.get("id", "rack")
        
        total_u = rack["total_u"]
        table_width = rack.get("table_width", 240)
        device_width = rack.get("device_width", 200)
        u_col_width = rack.get("u_col_width", 28)
        base_device_font = rack.get("device_font_size", 13.5)
        unit_font = rack.get("unit_font_size", 15)
        title_font = rack.get("title_font_size", 16)
        auto_scale = rack.get("auto_scale_font", True)
        
        # Process both front and rear
        for side in ['front', 'rear']:
            if side not in rack_config:
                continue
            
            devices = rack_config[side]
            side_node_id = f"{rack_id}_{side}"
            slots = build_occupancy(devices, total_u)
            
            # Rack node
            lines.append(f"  {side_node_id} [")
            lines.append("    label=<")
            lines.append("")
            
            # Table start
            lines.append("<TABLE")
            lines.append("  BORDER=\"2\"")
            lines.append("  CELLBORDER=\"1\"")
            lines.append("  CELLSPACING=\"0\"")
            lines.append("  CELLPADDING=\"4\"")
            lines.append(f"  WIDTH=\"{table_width}\"")
            lines.append(">")
            lines.append("")
            
            # Title row
            side_label = side.capitalize()
            lines.append("<TR>")
            lines.append(
                f"<TD COLSPAN=\"3\" BGCOLOR=\"#5af282\">"
                f"<FONT POINT-SIZE=\"{title_font}\" FACE=\"Sinkin Sans 400 Regular\">"
                f"<B>{rack['name']} {side_label}</B>"
                f"</FONT></TD>"
            )
            lines.append("</TR>")
            
            processed = set()
            
            # Rack rows (top to bottom)
            for u in range(total_u, 0, -1):
                if u in processed:
                    continue
                
                dev = slots.get(u)
                
                # Empty slot
                if not dev:
                    lines.append("<TR>")
                    lines.append(
                        f"<TD WIDTH=\"{u_col_width}\"><FONT FACE=\"Sinkin Sans 400 Regular\">{u}</FONT></TD>"
                    )
                    lines.append("<TD COLSPAN=\"2\"></TD>")
                    lines.append("</TR>")
                    continue
                
                # Device slot
                name = dev["name"]
                units = dev["units"]
                color = get_device_color(dev, type_colors)
                
                # Auto-scale font for big devices
                if auto_scale:
                    device_font = min(base_device_font + units, 20)
                else:
                    device_font = base_device_font
                
                # First row
                lines.append("<TR>")
                lines.append(
                    f"<TD WIDTH=\"{u_col_width}\"><FONT FACE=\"Sinkin Sans 400 Regular\">{u}</FONT></TD>"
                )
                
                # Build device cell content
                device_content = f"<FONT POINT-SIZE=\"{device_font}\" FACE=\"Sinkin Sans 400 Regular\"><B>{name}</B></FONT>"
                
                # Only add units label if device is not 1U
                if units > 1:
                    device_content += f"<BR/><FONT POINT-SIZE=\"{unit_font}\" FACE=\"Sinkin Sans 400 Regular\">{units}U</FONT>"
                
                lines.append(
                    f"<TD COLSPAN=\"2\" "
                    f"ROWSPAN=\"{units}\" "
                    f"BGCOLOR=\"{color}\" "
                    f"WIDTH=\"{device_width}\">"
                    f"{device_content}"
                    f"</TD>"
                )
                lines.append("</TR>")
                
                # Mark occupied rows
                for i in range(units):
                    processed.add(u - i)
                
                # Remaining rows for rowspan
                for i in range(1, units):
                    lines.append("<TR>")
                    lines.append(
                        f"<TD WIDTH=\"{u_col_width}\"><FONT FACE=\"Sinkin Sans 400 Regular\">{u - i}</FONT></TD>"
                    )
                    lines.append("</TR>")
            
            # Table end
            lines.append("")
            lines.append("</TABLE>")
            lines.append("")
            lines.append(">")
            lines.append("  ];")
            lines.append("")
    
    # Create spacing nodes between rack pairs
    lines.append("  // Spacing between rack pairs")
    for i in range(len(racks_config) - 1):
        spacer_id = f"spacer_{i}"
        lines.append(f"  {spacer_id} [shape=point, style=invis, width=1.6, height=0, fixedsize=true];")
    lines.append("")
    
    # Create horizontal ranking: 1F, 1R, spacer, 2F, 2R, spacer, 3F, 3R, ...
    lines.append("  // Horizontal layout with spacing")
    rank_nodes = []
    for i in range(len(racks_config)):
        rack_id = racks_config[i]["rack"].get("id", "rack")
        rank_nodes.append(f"\"{rack_id}_front\"")
        rank_nodes.append(f"\"{rack_id}_rear\"")
        
        # Add spacer after each rack pair except the last
        if i < len(racks_config) - 1:
            rank_nodes.append(f"spacer_{i}")
    
    lines.append(f"  {{ rank=same; {'; '.join(rank_nodes)}; }}")
    lines.append("")
    
    # Create invisible edges to enforce spacing between pairs
    lines.append("  // Invisible edges to enforce spacing")
    for i in range(len(racks_config) - 1):
        current_rear = f"{racks_config[i]['rack'].get('id', 'rack')}_rear"
        spacer = f"spacer_{i}"
        next_front = f"{racks_config[i+1]['rack'].get('id', 'rack')}_front"
        
        lines.append(f"  {current_rear} -> {spacer} [style=invis, minlen=1];")
        lines.append(f"  {spacer} -> {next_front} [style=invis, minlen=1];")
    
    lines.append("")
    lines.append("}")
    
    return "\n".join(lines)

# -------------------------------------------------
# Generate Wiring Diagram with Radial Layout
# -------------------------------------------------
def generate_wiring_diagram(layer, all_devices, type_colors):
    """
    Generate a radial wiring diagram grouped by rack.
    
    Structure:
    - Connections are organized by rack
    - Each rack has central hubs (devices with >1 connection) with peripheral devices in a circle
    - Inter-rack connections shown as edges between central nodes
    
    Central nodes are any device with more than 1 connection.
    """
    layer_name = layer["name"]
    connections = layer.get("connections", [])
    
    # Styling
    edge_color = layer.get("edge_color", "#333333")
    edge_style = layer.get("edge_style", "solid")
    edge_width = layer.get("edge_width", "2.0")
    font_size = layer.get("font_size", 12)
    
    lines = []
    
    # Graph header
    lines.append(f"graph \"{layer_name}\" {{")
    lines.append("")
    lines.append("  graph [")
    lines.append("    bgcolor=\"white\",")
    lines.append(f"    label=\"{layer_name}\",")
    lines.append(f"    labelloc=t,")
    lines.append(f"    fontsize={font_size + 4},")
    lines.append("    fontname=\"Sinkin Sans 400 Regular\",")
    lines.append("    overlap=false,")
    lines.append("    sep=0.5")
    lines.append("  ];")
    lines.append("")
    
    lines.append("  node [")
    lines.append("    shape=box,")
    lines.append("    style=\"rounded,filled\",")
    lines.append(f"    fontsize={font_size},")
    lines.append("    fontname=\"Sinkin Sans 400 Regular\",")
    lines.append("    margin=0.2")
    lines.append("  ];")
    lines.append("")
    
    lines.append("  edge [")
    lines.append(f"    color=\"{edge_color}\",")
    lines.append(f"    style={edge_style},")
    lines.append(f"    penwidth={edge_width}")
    lines.append("  ];")
    lines.append("")
    
    # Collect devices and connections per rack
    rack_devices = defaultdict(set)
    rack_connection_count = defaultdict(lambda: defaultdict(int))  # Count connections per device per rack
    inter_rack_connections = []
    
    for conn in connections:
        from_dev = conn["from"]
        to_dev = conn["to"]
        
        # Get device info
        from_info = all_devices.get(from_dev)
        to_info = all_devices.get(to_dev)
        
        if from_info and to_info:
            from_rack = from_info.get("rack_id")
            to_rack = to_info.get("rack_id")
            
            # Track which devices belong to which rack
            rack_devices[from_rack].add(from_dev)
            rack_devices[to_rack].add(to_dev)
            
            # Count connections
            if from_rack == to_rack:
                rack_connection_count[from_rack][from_dev] += 1
                rack_connection_count[from_rack][to_dev] += 1
            else:
                # Inter-rack connection
                inter_rack_connections.append((from_dev, to_dev, from_rack, to_rack))
                rack_connection_count[from_rack][from_dev] += 1
                rack_connection_count[to_rack][to_dev] += 1
    
    # Find central nodes per rack (any device with >1 connection)
    rack_central = defaultdict(list)
    for rack_id in rack_devices:
        for dev_name, conn_count in rack_connection_count[rack_id].items():
            if conn_count > 1:
                rack_central[rack_id].append(dev_name)
    
    # Create nodes grouped by rack
    lines.append("  // Devices grouped by rack")
    lines.append("")
    
    for rack_id in sorted(rack_devices.keys()):
        devices = rack_devices[rack_id]
        
        lines.append(f"  subgraph cluster_{rack_id} {{")
        rack_label = rack_id.replace('rack', '').replace('_front', '').replace('_rear', '').strip('_')
        lines.append(f"    label=\"Rack {rack_label}\";")
        lines.append("    style=filled;")
        lines.append("    color=\"#F5F5F5\";")
        lines.append("    fontname=\"Sinkin Sans 400 Regular\";")
        lines.append("")
        
        # Central nodes - larger, prominent
        central_nodes = rack_central.get(rack_id, [])
        for dev_name in sorted(central_nodes):
            node_id = dev_name.replace(" ", "_").replace("/", "_")
            dev_info = all_devices.get(dev_name)
            color = get_device_color(dev_info, type_colors)
            connection_count = rack_connection_count[rack_id][dev_name]
            
            lines.append(f"    \"{node_id}\" [")
            lines.append(f"      label=\"{dev_name}\\n({connection_count} conn)\",")
            lines.append(f"      fillcolor=\"{color}\",")
            lines.append("      penwidth=2.5")
            lines.append("    ];")
        
        # Peripheral nodes
        peripheral = devices - set(central_nodes)
        for dev_name in sorted(peripheral):
            node_id = dev_name.replace(" ", "_").replace("/", "_")
            dev_info = all_devices.get(dev_name)
            color = get_device_color(dev_info, type_colors)
            
            lines.append(f"    \"{node_id}\" [")
            lines.append(f"      label=\"{dev_name}\",")
            lines.append(f"      fillcolor=\"{color}\"")
            lines.append("    ];")
        
        lines.append("  }")
        lines.append("")
    
    # Create connections
    lines.append("  // Connections")
    for conn in connections:
        from_dev = conn["from"]
        to_dev = conn["to"]
        from_id = from_dev.replace(" ", "_").replace("/", "_")
        to_id = to_dev.replace(" ", "_").replace("/", "_")
        
        label = conn.get("label", "")
        conn_color = conn.get("color", edge_color)
        conn_style = conn.get("style", edge_style)
        conn_width = conn.get("width", edge_width)
        
        edge_attrs = [
            f"color=\"{conn_color}\"",
            f"style={conn_style}",
            f"penwidth={conn_width}"
        ]
        
        if label:
            edge_attrs.append(f"label=\"{label}\"")
            edge_attrs.append(f"fontsize={font_size - 2}")
            edge_attrs.append("fontname=\"Sinkin Sans 400 Regular\"")
        
        lines.append(f"  {from_id} -- {to_id} [")
        lines.append(f"    {', '.join(edge_attrs)}")
        lines.append("  ];")
    
    lines.append("")
    lines.append("}")
    
    return "\n".join(lines)

# -------------------------------------------------
# Export inventory to CSV
# -------------------------------------------------
def export_inventory_csv(inventory, output_file="output/computer_info.csv"):
    """Export inventory to CSV format"""
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Header
        writer.writerow([
            "Device Name",
            "Part Number",
            "Port #",
            "Adapter/Network",
            "MAC Address",
            "IP Address"
        ])
        
        # Data rows
        for device in inventory:
            device_name = device.get("device_name", "")
            part_number = device.get("arena_part_number", "")
            ports = device.get("ethernet_ports", [])
            
            if not ports:
                writer.writerow([device_name, part_number, "", "", "", ""])
            else:
                for idx, port in enumerate(ports, 1):
                    writer.writerow([
                        device_name,
                        part_number,
                        idx,
                        port.get("adapter", ""),
                        port.get("mac", ""),
                        port.get("ip", "")
                    ])
    
    print(f"Exported inventory to {output_file}")

# -------------------------------------------------
# Export inventory to JSON
# -------------------------------------------------
def export_inventory_json(inventory, output_file="output/computer_info.json"):
    """Export inventory to JSON format"""
    with open(output_file, 'w') as f:
        json.dump(inventory, f, indent=2)
    
    print(f"Exported inventory to {output_file}")

# -------------------------------------------------
# Export inventory to HTML
# -------------------------------------------------
def export_inventory_html(inventory, output_file="output/computer_info.html"):
    """Export inventory to HTML table"""
    html = """<!DOCTYPE html>
<html>
<head>
    <title>Computer Inventory</title>
    <style>
        body {
            font-family: 'Sinkin Sans', Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        h1 {
            color: #333;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            background-color: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        th {
            background-color: #5af282;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: bold;
            border-bottom: 2px solid #333;
        }
        td {
            padding: 10px 12px;
            border-bottom: 1px solid #ddd;
        }
        tr:hover {
            background-color: #f9f9f9;
        }
        .device-name {
            font-weight: bold;
            color: #333;
        }
        .port-number {
            background-color: #f0f0f0;
            text-align: center;
            width: 60px;
        }
        .mac-address {
            font-family: monospace;
            font-size: 0.9em;
        }
        .ip-address {
            font-family: monospace;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <h1>Computer Inventory</h1>
    <table>
        <thead>
            <tr>
                <th>Device Name</th>
                <th>Part Number</th>
                <th>Port #</th>
                <th>Adapter/Network</th>
                <th>MAC Address</th>
                <th>IP Address</th>
            </tr>
        </thead>
        <tbody>
"""
    
    for device in inventory:
        device_name = device.get("device_name", "")
        part_number = device.get("arena_part_number", "")
        ports = device.get("ethernet_ports", [])
        
        if not ports:
            html += f"""            <tr>
                <td class="device-name">{device_name}</td>
                <td>{part_number}</td>
                <td class="port-number">-</td>
                <td>-</td>
                <td class="mac-address">-</td>
                <td class="ip-address">-</td>
            </tr>
"""
        else:
            for idx, port in enumerate(ports, 1):
                html += f"""            <tr>
                <td class="device-name">{device_name}</td>
                <td>{part_number}</td>
                <td class="port-number">{idx}</td>
                <td>{port.get('adapter', '')}</td>
                <td class="mac-address">{port.get('mac', '')}</td>
                <td class="ip-address">{port.get('ip', '')}</td>
            </tr>
"""
    
    html += """        </tbody>
    </table>
</body>
</html>
"""
    
    with open(output_file, 'w') as f:
        f.write(html)
    
    print(f"Exported inventory to {output_file}")

# -------------------------------------------------
# Generate inventory summary
# -------------------------------------------------
def generate_inventory_summary(inventory):
    """Generate summary statistics"""
    if not inventory:
        print("\nNo inventory data found in system.yaml\n")
        return
    
    total_devices = len(inventory)
    total_ports = sum(len(d.get("ethernet_ports", [])) for d in inventory)
    
    print("\n" + "="*70)
    print("INVENTORY SUMMARY")
    print("="*70)
    print(f"Total devices: {total_devices}")
    print(f"Total ethernet ports: {total_ports}")
    print(f"Average ports per device: {total_ports / total_devices:.1f}" if total_devices > 0 else "")
    
    # Group by adapter
    adapters = {}
    for device in inventory:
        for port in device.get("ethernet_ports", []):
            adapter = port.get("adapter", "Unknown")
            adapters[adapter] = adapters.get(adapter, 0) + 1
    
    if adapters:
        print("\nPorts by Adapter/Network:")
        for adapter in sorted(adapters.keys()):
            print(f"  {adapter}: {adapters[adapter]} ports")
    
    print("="*70 + "\n")

# -------------------------------------------------
# Main
# -------------------------------------------------
def main():
    config = load_config()
    
    # Extract type color mappings from config
    type_colors = config.get("type_colors", {})
    
    # Create output directory if it doesn't exist
    if not os.path.exists("output"):
        os.mkdir("output")
    
    if "racks" in config:
        racks_config = config["racks"]
        all_devices = build_device_map(racks_config)
        
        # Generate single comprehensive layout
        layout_dot = generate_rack_layout_dot(racks_config, type_colors)
        with open("output/rack_layout.dot", "w") as f:
            f.write(layout_dot)
        print("Generated output/rack_layout.dot")
        
        # Build device map for wiring (from both front and rear)
        all_devices = {}
        for rack_config in racks_config:
            rack_id = rack_config["rack"].get("id", "rack")
            
            for side in ['front', 'rear']:
                if side in rack_config:
                    for dev in rack_config[side]:
                        dev["rack_id"] = rack_id
                        all_devices[dev["name"]] = dev
        
        print(f"Device map built with {len(all_devices)} devices")

        layers = config.get("wiring_layers", [])
        for layer in layers:
            layer_name = layer["name"]
            safe_name = layer_name.replace(" ", "_").replace("/", "_").lower()
            filename = f"output/{safe_name}.dot"
            
            wiring_dot = generate_wiring_diagram(layer, all_devices, type_colors)
            with open(filename, "w") as f:
                f.write(wiring_dot)
            print(f"Generated {filename}")
        
        # Process inventory
        inventory = config.get("inventory", [])
        if inventory:
            export_inventory_csv(inventory)
            export_inventory_json(inventory)
            export_inventory_html(inventory)
            generate_inventory_summary(inventory)
    
    else:
        print("Error: Configuration must have 'racks' with consolidated front/rear")
        return

if __name__ == "__main__":
    main()