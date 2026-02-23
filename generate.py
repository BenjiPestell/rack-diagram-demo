import yaml
import math
import os
import csv
import json
import re
from collections import defaultdict
from math import sqrt

# -------------------------------------------------
# Load config
# -------------------------------------------------
def load_config():
    with open("system.yaml") as f:
        return yaml.safe_load(f)

# -------------------------------------------------
# Expand wiring clusters
# -------------------------------------------------
def expand_wiring_clusters(connections, layer_cable_type="", layer_edge_color="#333333"):
    """
    Expand wiring connection clusters into individual connections.
    
    Supports cable_type at both layer and connection level:
    - Layer cable_type: default for all connections in the layer
    - Connection cable_type: overrides layer cable_type for that connection
    
    Cluster format with single 'to':
    - from: "R4 16A PDU B"
      to: "IG {N}"
      start: 8
      end: 10
    
    Cluster format with multiple 'to' targets:
    - from: "Graphics Switch"
      to:
        - "Operator PC"
        - "Speedgoat"
    
    Supports per-connection cable_type and edge_color override:
    - from: "Switch"
      to: "Device"
      cable_type: "Cat6"
      edge_color: "#FF0000"
    """
    expanded = []
    
    for conn in connections:
        from_template = conn.get("from", "")
        to_field = conn.get("to", "")
        label = conn.get("label", "")
        color = conn.get("color", "")
        edge_color = conn.get("edge_color", "")
        style = conn.get("style", "")
        width = conn.get("width", "")
        cable_type = conn.get("cable_type", layer_cable_type)  # Use connection cable_type or fallback to layer
        
        # Normalize to_field to always be a list
        if isinstance(to_field, str):
            to_list = [to_field]
        elif isinstance(to_field, list):
            to_list = to_field
        else:
            to_list = [to_field]
        
        # Check if this is a cluster definition (with start/end)
        if "start" in conn and "end" in conn:
            start = int(conn["start"]) if isinstance(conn["start"], str) else conn["start"]
            end = int(conn["end"]) if isinstance(conn["end"], str) else conn["end"]
            
            # Expand each 'to' template with the cluster range
            for to_template in to_list:
                for n in range(start, end + 1):
                    # Replace {N} placeholders
                    from_dev = from_template.replace("{N}", str(n))
                    to_dev = to_template.replace("{N}", str(n))
                    
                    # Replace {N+X} placeholders
                    match = re.search(r'\{N\+(\d+)\}', from_dev)
                    if match:
                        offset = int(match.group(1))
                        from_dev = from_dev.replace(match.group(0), str(n + offset))
                    
                    match = re.search(r'\{N\+(\d+)\}', to_dev)
                    if match:
                        offset = int(match.group(1))
                        to_dev = to_dev.replace(match.group(0), str(n + offset))
                    
                    # Replace {N-X} placeholders
                    match = re.search(r'\{N-(\d+)\}', from_dev)
                    if match:
                        offset = int(match.group(1))
                        from_dev = from_dev.replace(match.group(0), str(n - offset))
                    
                    match = re.search(r'\{N-(\d+)\}', to_dev)
                    if match:
                        offset = int(match.group(1))
                        to_dev = to_dev.replace(match.group(0), str(n - offset))
                    
                    # Create expanded connection
                    expanded_conn = {
                        "from": from_dev,
                        "to": to_dev
                    }
                    
                    # Add optional fields if present
                    if label:
                        expanded_conn["label"] = label
                    if color:
                        expanded_conn["color"] = color
                    if edge_color:
                        expanded_conn["edge_color"] = edge_color
                    if style:
                        expanded_conn["style"] = style
                    if width:
                        expanded_conn["width"] = width
                    if cable_type:
                        expanded_conn["cable_type"] = cable_type
                    expanded.append(expanded_conn)
        else:
            # No cluster - just handle multiple 'to' targets
            for to_template in to_list:
                expanded_conn = {
                    "from": from_template,
                    "to": to_template
                }
                
                # Add optional fields if present
                if label:
                    expanded_conn["label"] = label
                if color:
                    expanded_conn["color"] = color
                if edge_color:
                    expanded_conn["edge_color"] = edge_color
                if style:
                    expanded_conn["style"] = style
                if width:
                    expanded_conn["width"] = width
                if cable_type:
                    expanded_conn["cable_type"] = cable_type
                
                expanded.append(expanded_conn)
    
    return expanded

# -------------------------------------------------
# Expand computer_info clusters
# -------------------------------------------------
def expand_computer_info_clusters(computer_info_raw):
    """
    Expand computer_info entries with start/end ranges.
    
    Example:
    - device_name: "IG {N}"
      start: 1
      end: 13
      arena_part_number: "902-00011"
      ethernet_ports:
        - adapter: "rFpro"
          ip: "192.168.2.{N+50}"
    
    Expands to 13 individual devices: IG 1, IG 2, ..., IG 13
    """
    expanded = []
    
    for entry in computer_info_raw:
        # Check if this is a cluster definition
        if "start" in entry and "end" in entry:
            device_template = entry.get("device_name", "Device {N}")
            start = entry["start"]
            end = entry["end"]
            part_number = entry.get("arena_part_number", "")
            ports_template = entry.get("ethernet_ports", [])
            
            # Generate individual devices
            for n in range(start, end + 1):
                # Expand device name
                device_name = device_template.replace("{N}", str(n))
                
                # Expand ports
                ports = []
                for port_template in ports_template:
                    port = {}
                    for key, value in port_template.items():
                        if isinstance(value, str):
                            # Replace {N} placeholders
                            value = value.replace("{N}", str(n))
                            # Replace {N+X} placeholders
                            match = re.search(r'\{N\+(\d+)\}', value)
                            if match:
                                offset = int(match.group(1))
                                value = value.replace(match.group(0), str(n + offset))
                            # Replace {N-X} placeholders
                            match = re.search(r'\{N-(\d+)\}', value)
                            if match:
                                offset = int(match.group(1))
                                value = value.replace(match.group(0), str(n - offset))
                        port[key] = value
                    ports.append(port)
                
                # Create expanded entry
                expanded.append({
                    "device_name": device_name,
                    "arena_part_number": part_number,
                    "ethernet_ports": ports
                })
        else:
            # Regular entry, no expansion needed
            expanded.append(entry)
    
    return expanded

# -------------------------------------------------
# Expand external devices (with group support)
# -------------------------------------------------
def expand_external_devices(external_devices_config):
    """
    Expand external devices, handling both grouped and ungrouped formats.
    
    Ungrouped format (flat):
    - name: "Device {N}"
      start: 1
      end: 3
      type: pc
    
    Grouped format (nested):
    - name: Operator Room
      devices:
        - name: "Operator room beltpack {N}"
          start: 1
          end: 7
          type: beltpack
    
    Returns a dict with group names as keys and lists of expanded devices as values.
    Ungrouped devices go into "default" group.
    """
    expanded = {}
    
    if not external_devices_config:
        return expanded
    
    for entry in external_devices_config:
        # Check if this is a grouped entry
        if "devices" in entry:
            group_name = entry.get("name", "External Devices")
            group_devices = []
            
            # Expand devices within the group
            for dev_template in entry.get("devices", []):
                if "start" in dev_template and "end" in dev_template:
                    # This is a cluster definition
                    name_template = dev_template.get("name", "Device {N}")
                    start = dev_template["start"]
                    end = dev_template["end"]
                    dev_type = dev_template.get("type", "")
                    
                    for n in range(start, end + 1):
                        dev_name = name_template.replace("{N}", str(n))
                        group_devices.append({
                            "name": dev_name,
                            "type": dev_type
                        })
                else:
                    # Regular device entry
                    group_devices.append(dev_template)
            
            expanded[group_name] = group_devices
        else:
            # Ungrouped device (flat format)
            if "start" in entry and "end" in entry:
                # This is a cluster definition
                name_template = entry.get("name", "Device {N}")
                start = entry["start"]
                end = entry["end"]
                dev_type = entry.get("type", "")
                
                group_devices = []
                for n in range(start, end + 1):
                    dev_name = name_template.replace("{N}", str(n))
                    group_devices.append({
                        "name": dev_name,
                        "type": dev_type
                    })
                
                expanded["External Devices"] = group_devices
            else:
                # Regular ungrouped device
                if "External Devices" not in expanded:
                    expanded["External Devices"] = []
                expanded["External Devices"].append(entry)
    
    return expanded

# -------------------------------------------------
# Expand cluster definitions
# -------------------------------------------------
def expand_clusters(devices):
    """
    Expand cluster device definitions into individual devices.
    
    Cluster format:
    - name: "RVD {N}"
      start_u: 20
      start: 1
      end: 3
      units: 4
      spacing: 0
      type: pc
    
    Expands to:
    - name: "RVD 1", start_u: 20, units: 4, type: pc
    - name: "RVD 2", start_u: 16, units: 4, type: pc
    - name: "RVD 3", start_u: 12, units: 4, type: pc
    """
    expanded = []
    
    for dev in devices:
        # Check if this is a cluster definition
        if "start" in dev and "end" in dev and "{N}" in dev.get("name", ""):
            start_num = dev["start"]
            end_num = dev["end"]
            start_u = dev["start_u"]
            units = dev["units"]
            spacing = dev.get("spacing", 0)
            
            # Expand the cluster
            for i in range(start_num, end_num + 1):
                # Calculate U position for this item
                items_before = i - start_num
                u_offset = (units + spacing) * items_before
                current_start_u = start_u - u_offset
                
                # Create expanded device
                expanded_dev = dev.copy()
                expanded_dev["name"] = dev["name"].replace("{N}", str(i))
                expanded_dev["start_u"] = current_start_u
                
                # Remove cluster-specific fields
                for key in ["start", "end", "spacing"]:
                    expanded_dev.pop(key, None)
                
                expanded.append(expanded_dev)
        else:
            # Regular device, add as-is
            expanded.append(dev)
    
    return expanded

# -------------------------------------------------
# Build device map
# -------------------------------------------------
def build_device_map(racks_config, external_devices_config=None):
    """
    Build a map of device name -> {rack_id, device_info}
    Includes both rack devices and external devices
    
    External devices are organized in groups
    """
    all_devices = {}
    
    # Add rack devices
    for rack_config in racks_config:
        rack_id = rack_config["rack"].get("id", "rack")
        
        for side in ['front', 'rear']:
            if side in rack_config:
                # Expand clusters first
                devices = expand_clusters(rack_config[side])
                
                for dev in devices:
                    dev_copy = dev.copy()
                    dev_copy["rack_id"] = rack_id
                    dev_copy["side"] = side
                    all_devices[dev["name"]] = dev_copy
    
    # Add external devices
    if external_devices_config:
        expanded_ext_devices = expand_external_devices(external_devices_config)
        
        # Flatten all grouped devices into the device map
        for group_name, devices in expanded_ext_devices.items():
            for dev in devices:
                dev_copy = dev.copy()
                dev_copy["rack_id"] = "external"
                dev_copy["external_group"] = group_name
                dev_copy["side"] = "external"
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
    # First expand clusters
    devices = expand_clusters(devices)
    
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
        except Exception as e:
            print(f"Skipping layout for device '{name}'. {str(e)}")
    
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
    connections_raw = layer.get("connections", [])
    
    # Styling - layer defaults
    layer_edge_color = layer.get("edge_color", "#333333")
    layer_cable_type = layer.get("cable_type", "")
    edge_style = layer.get("edge_style", "solid")
    edge_width = layer.get("edge_width", "2.0")
    font_size = layer.get("font_size", 12)
    
    # Expand connection clusters with layer defaults
    connections = expand_wiring_clusters(connections_raw, layer_cable_type, layer_edge_color)
    
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
    lines.append(f"    color=\"{layer_edge_color}\",")
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
        else:
            # Log missing devices
            if not from_info:
                print(f"Warning: Device '{from_dev}' not found in device map (used in {layer_name})")
            if not to_info:
                print(f"Warning: Device '{to_dev}' not found in device map (used in {layer_name})")
    
    # Find central nodes per rack (any device with >1 connection)
    rack_central = defaultdict(list)
    for rack_id in rack_devices:
        for dev_name, conn_count in rack_connection_count[rack_id].items():
            if conn_count > 1:
                rack_central[rack_id].append(dev_name)
    
    # Create nodes grouped by rack and external groups
    lines.append("  // Devices grouped by rack and external groups")
    lines.append("")
    
    # Track external groups
    external_groups = {}
    for rack_id in sorted(rack_devices.keys()):
        if rack_id == "external":
            # Organize external devices by group
            for dev_name in sorted(rack_devices[rack_id]):
                dev_info = all_devices.get(dev_name)
                group_name = dev_info.get("external_group", "External Devices")
                
                if group_name not in external_groups:
                    external_groups[group_name] = set()
                external_groups[group_name].add(dev_name)
    
    # Create clusters for racks first
    for rack_id in sorted(rack_devices.keys()):
        if rack_id == "external":
            continue  # Handle external separately
        
        devices = rack_devices[rack_id]
        
        lines.append(f"  subgraph cluster_{rack_id} {{")
        rack_label = f"Rack {rack_id.replace('rack', '').replace('_front', '').replace('_rear', '').strip('_')}"
        lines.append(f"    label=\"{rack_label}\";")
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
    
    # Create clusters for external device groups
    for group_name in sorted(external_groups.keys()):
        devices = external_groups[group_name]
        
        group_id = group_name.replace(" ", "_").replace("/", "_")
        lines.append(f"  subgraph cluster_external_{group_id} {{")
        lines.append(f"    label=\"{group_name}\";")
        lines.append("    style=filled;")
        lines.append("    color=\"#E0E0E0\";")
        lines.append("    fontname=\"Sinkin Sans 400 Regular\";")
        lines.append("")
        
        # Central nodes
        central_nodes = rack_central.get("external", [])
        for dev_name in sorted(devices):
            if dev_name not in central_nodes:
                continue
            
            node_id = dev_name.replace(" ", "_").replace("/", "_")
            dev_info = all_devices.get(dev_name)
            color = get_device_color(dev_info, type_colors)
            connection_count = rack_connection_count["external"][dev_name]
            
            lines.append(f"    \"{node_id}\" [")
            lines.append(f"      label=\"{dev_name}\\n({connection_count} conn)\",")
            lines.append(f"      fillcolor=\"{color}\",")
            lines.append("      penwidth=2.5")
            lines.append("    ];")
        
        # Peripheral nodes
        for dev_name in sorted(devices):
            if dev_name in central_nodes:
                continue
            
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
        cable_type = conn.get("cable_type", "")
        
        # Use cable_type as label if no explicit label is set
        if not label and cable_type:
            label = cable_type
        
        # Use per-connection edge_color if set, otherwise use layer default
        conn_edge_color = conn.get("edge_color", layer_edge_color)
        
        conn_color = conn.get("color", "")
        conn_style = conn.get("style", edge_style)
        conn_width = conn.get("width", edge_width)
        
        edge_attrs = [
            f"color=\"{conn_edge_color}\"",
            f"style={conn_style}",
            f"penwidth={conn_width}"
        ]
        
        if label:
            edge_attrs.append(f"label=\"{" "*3 + label}\"")
            edge_attrs.append(f"fontsize={font_size - 2}")
            edge_attrs.append("fontname=\"Sinkin Sans 400 Regular\"")
        
        # Format edge attributes properly (commas added by join)
        edge_attrs_str = ", ".join(edge_attrs)
        
        lines.append(f"  {from_id} -- {to_id} [")
        lines.append(f"    {edge_attrs_str}")
        lines.append("  ];")
    
    lines.append("")
    lines.append("}")
    
    return "\n".join(lines)

# -------------------------------------------------
# Export computer_info to CSV
# -------------------------------------------------
def export_computer_info_csv(computer_info, output_file="output/computer_info.csv"):
    """Export computer_info to CSV format"""
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
        for device in computer_info:
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
    
    print(f"Exported computer_info to {output_file}")

# -------------------------------------------------
# Export computer_info to JSON
# -------------------------------------------------
def export_computer_info_json(computer_info, output_file="output/computer_info.json"):
    """Export computer_info to JSON format"""
    with open(output_file, 'w') as f:
        json.dump(computer_info, f, indent=2)
    
    print(f"Exported computer_info to {output_file}")

# -------------------------------------------------
# Export computer_info to HTML
# -------------------------------------------------
def export_computer_info_html(computer_info, output_file="output/computer_info.html"):
    """Export computer_info to HTML table"""
    html = """<!DOCTYPE html>
<html>
<head>
    <title>Computer Info</title>
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
    <h1>Computer Info</h1>
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
    
    for device in computer_info:
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
    
    print(f"Exported computer_info to {output_file}")


# -------------------------------------------------
# Cable length calculation
# -------------------------------------------------
def calculate_cable_length(from_device, to_device, all_devices, rack_configs, config):
    """
    Calculate minimum cable length needed for a connection.
    
    Formula: (unit_delta * 0.045) + (front_to_back * 1 or 0) + (inter_rack * 1 or 0) + cable_slack
    
    where:
    - unit_delta: 
      * Intra-rack: absolute difference in bottom U positions
      * Inter-rack: (start_u - 1) on from device + (start_u - 1) on to device
      * Undefined devices: 0
    - front_to_back: 0.5m if connection spans from front to rear within same rack, else 0
    - inter_rack: inter-rack distance if devices in different racks, else 0
    - cable_slack: configured slack length
    """
    
    # Get device info
    from_info = all_devices.get(from_device)
    to_info = all_devices.get(to_device)
    
    if not from_info or not to_info:
        return None
    
    # Get config values
    cable_slack = config.get("cable_slack_length", 0.2)  # Default 0.2m
    standard_u_height = config.get("standard_u_height", 0.045)  # Default 0.045m
    front_to_back = config.get("front_to_back_length", 0.5)  # Default 0.5m
    inter_rack_distance = config.get("inter_rack_distance", 10)  # Default 10m
    
    # Build rack name map
    rack_name_map = {}
    rack_position_map = {}
    rack_position = 0
    for rack_config in rack_configs:
        rack_id = rack_config["rack"].get("id", "rack")
        rack_name = rack_config["rack"].get("name", rack_id)
        rack_name_map[rack_id] = rack_name
        rack_position_map[rack_id] = rack_position
        rack_position += 1
    
    from_rack = from_info.get("rack_id")
    to_rack = to_info.get("rack_id")
    from_side = from_info.get("side", "front")
    to_side = to_info.get("side", "front")
    from_start_u = from_info.get("start_u", 0)
    to_start_u = to_info.get("start_u", 0)
    from_units = from_info.get("units", 1)
    to_units = to_info.get("units", 1)
    
    # Get rack names for display
    from_rack_name = rack_name_map.get(from_rack, from_rack)
    to_rack_name = rack_name_map.get(to_rack, to_rack)
    
    # Calculate unit distance
    if from_rack != to_rack and from_rack != "external" and to_rack != "external":
        # Inter-rack connection
        # If devices have start_u, include U distance from device to U1 on both ends
        # Otherwise (undefined devices), use 0
        from_u_dist = (from_start_u - 1) if from_start_u else 0
        to_u_dist = (to_start_u - 1) if to_start_u else 0
        unit_delta = from_u_dist + to_u_dist
        f2b_length = 0  # No F2B for inter-rack
    else:
        # Intra-rack connection
        if from_start_u and to_start_u:
            # Both devices have positions - use bottom U
            from_bottom_u = from_start_u - from_units + 1
            to_bottom_u = to_start_u - to_units + 1
            unit_delta = abs(from_bottom_u - to_bottom_u)
        else:
            # One or both devices undefined - use 0 for U distance
            unit_delta = 0
        
        # Calculate front-to-back distance (only if same rack, different sides)
        f2b_length = 0
        if from_rack == to_rack and from_side != to_side and from_side != "external" and to_side != "external":
            f2b_length = front_to_back
    
    unit_length = unit_delta * standard_u_height
    
    # Calculate inter-rack distance
    inter_rack_length = 0
    if from_rack != to_rack and from_rack != "external" and to_rack != "external":
        from_pos = rack_position_map.get(from_rack, 0)
        to_pos = rack_position_map.get(to_rack, 0)
        rack_delta = abs(from_pos - to_pos)
        inter_rack_length = rack_delta * inter_rack_distance
    
    # Total cable length
    total_length = unit_length + f2b_length + inter_rack_length + cable_slack
    total_length = math.ceil(total_length * 2) / 2
    
    return {
        "from_rack": from_rack_name,
        "to_rack": to_rack_name,
        "unit_delta": unit_delta,
        "unit_length": unit_length,
        "f2b_length": f2b_length,
        "inter_rack_length": inter_rack_length,
        "cable_slack": cable_slack,
        "total_length": total_length
    }

# -------------------------------------------------
# Generate cable length HTML table
# -------------------------------------------------
def generate_cable_length_html(all_devices, racks_config, wiring_layers, config, output_file="output/cable_lengths.html"):
    """Generate an HTML table with cable length calculations"""
    
    html = """<!DOCTYPE html>
<html>
<head>
    <title>Cable Length Calculations</title>
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
            margin-bottom: 20px;
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
        .network {
            font-weight: bold;
            color: #333;
        }
        .metric {
            text-align: right;
            font-family: monospace;
        }
        .total {
            background-color: #4297a1;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <h1>Cable Length Calculations</h1>
    <table>
        <thead>
            <tr>
                <th>Network</th>
                <th>From</th>
                <th>To</th>
                <th>Cable Type</th>
                <th>From Rack</th>
                <th>To Rack</th>
                <th class="metric">U Distance</th>
                <th class="metric">U Length (m)</th>
                <th class="metric">F2B (m)</th>
                <th class="metric">Inter-rack (m)</th>
                <th class="metric">Slack (m)</th>
                <th class="metric total">Min Length (m)</th>
            </tr>
        </thead>
        <tbody>
"""
    
    # Process each wiring layer
    for layer in wiring_layers:
        layer_name = layer["name"]
        connections_raw = layer.get("connections", [])
        
        # Expand connections
        layer_cable_type = layer.get("cable_type", "")
        connections = expand_wiring_clusters(connections_raw, layer_cable_type)
        
        # Output each connection
        for conn in connections:
            from_dev = conn["from"]
            to_dev = conn["to"]
            
            # Get device info
            from_info = all_devices.get(from_dev)
            to_info = all_devices.get(to_dev)
            
            if not from_info or not to_info:
                continue
            
            # Calculate cable length
            cable_data = calculate_cable_length(from_dev, to_dev, all_devices, racks_config, config)
            
            if cable_data:
                cable_type = conn.get("cable_type", "")
                html += f"""            <tr>
                <td class="network">{layer_name}</td>
                <td>{from_dev}</td>
                <td>{to_dev}</td>
                <td>{cable_type}</td>
                <td>{cable_data['from_rack']}</td>
                <td>{cable_data['to_rack']}</td>
                <td class="metric">{cable_data['unit_delta']}</td>
                <td class="metric">{cable_data['unit_length']:.3f}</td>
                <td class="metric">{cable_data['f2b_length']:.3f}</td>
                <td class="metric">{cable_data['inter_rack_length']:.1f}</td>
                <td class="metric">{cable_data['cable_slack']:.3f}</td>
                <td class="metric total">{cable_data['total_length']:.2f}</td>
            </tr>
"""
    
    html += """        </tbody>
    </table>
</body>
</html>
"""
    
    with open(output_file, 'w') as f:
        f.write(html)
    
    print(f"Generated cable length HTML: {output_file}")

# -------------------------------------------------
# Generate cable length table
# -------------------------------------------------
def generate_cable_length_table(all_devices, racks_config, wiring_layers, config, output_file="output/cable_lengths.csv"):
    """Generate a table with cable length calculations for all connections"""
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Header
        writer.writerow([
            "Network",
            "From",
            "To",
            "Cable Type",
            "From Rack",
            "To Rack",
            "U Distance (units)",
            "Unit Length (m)",
            "F2B Length (m)",
            "Inter-rack Length (m)",
            "Cable Slack (m)",
            "Min Cable Length (m)"
        ])
        
        # Process each wiring layer
        for layer in wiring_layers:
            layer_name = layer["name"]
            connections_raw = layer.get("connections", [])
            
            # Expand connections
            layer_cable_type = layer.get("cable_type", "")
            connections = expand_wiring_clusters(connections_raw, layer_cable_type)
            
            # Output each connection
            for conn in connections:
                from_dev = conn["from"]
                to_dev = conn["to"]
                
                # Get device info
                from_info = all_devices.get(from_dev)
                to_info = all_devices.get(to_dev)
                
                if not from_info or not to_info:
                    continue
                
                # Calculate cable length
                cable_data = calculate_cable_length(from_dev, to_dev, all_devices, racks_config, config)
                
                if cable_data:
                    cable_type = conn.get("cable_type", "")
                    writer.writerow([
                        layer_name,
                        from_dev,
                        to_dev,
                        cable_type,
                        cable_data["from_rack"],
                        cable_data["to_rack"],
                        cable_data["unit_delta"],
                        f"{cable_data['unit_length']:.3f}",
                        f"{cable_data['f2b_length']:.3f}",
                        f"{cable_data['inter_rack_length']:.1f}",
                        f"{cable_data['cable_slack']:.3f}",
                        f"{cable_data['total_length']:.2f}"
                    ])
    
    print(f"Generated cable length table: {output_file}")

# -------------------------------------------------
# Main
# -------------------------------------------------
def main():
    config = load_config()
    
    # Extract type color mappings from config
    type_colors = config.get("type_colors", {})
    
    # Get cable length calculation parameters from config
    cable_config = {
        "cable_slack_length": config.get("cable_slack_length", 0.2),
        "standard_u_height": config.get("standard_u_height", 0.045),
        "front_to_back_length": config.get("front_to_back_length", 0.5),
        "inter_rack_distance": config.get("inter_rack_distance", 10)
    }
    
    # Create output directory if it doesn't exist
    if not os.path.exists("output"):
        os.mkdir("output")
    
    if "racks" in config:
        racks_config = config["racks"]
        external_devices_config = config.get("external_devices", [])
        
        all_devices = build_device_map(racks_config, external_devices_config)
        
        # Generate single comprehensive layout
        layout_dot = generate_rack_layout_dot(racks_config, type_colors)
        with open("output/rack_layout.dot", "w") as f:
            f.write(layout_dot)
        print("Generated output/rack_layout.dot")
        
        # Build device map for wiring (from both front and rear + external)
        all_devices = {}
        
        # Add rack devices
        for rack_config in racks_config:
            rack_id = rack_config["rack"].get("id", "rack")
            
            for side in ['front', 'rear']:
                if side in rack_config:
                    devices = expand_clusters(rack_config[side])
                    for dev in devices:
                        dev["rack_id"] = rack_id
                        dev["side"] = side
                        all_devices[dev["name"]] = dev
        
        # Add external devices (organized by group)
        if external_devices_config:
            expanded_ext_devices = expand_external_devices(external_devices_config)
            for group_name, devices in expanded_ext_devices.items():
                for dev in devices:
                    dev_copy = dev.copy()
                    dev_copy["rack_id"] = "external"
                    dev_copy["external_group"] = group_name
                    all_devices[dev["name"]] = dev_copy
        
        external_device_count = len(all_devices) - sum(len(expand_clusters(rack_config.get(side, []))) 
                                                        for rack_config in racks_config 
                                                        for side in ['front', 'rear'])
        print(f"Device map built with {len(all_devices)} devices ({external_device_count} external)")

        layers = config.get("wiring_layers", [])
        for layer in layers:
            layer_name = layer["name"]
            safe_name = layer_name.replace(" ", "_").replace("/", "_").lower()
            filename = f"output/{safe_name}.dot"
            
            wiring_dot = generate_wiring_diagram(layer, all_devices, type_colors)
            with open(filename, "w") as f:
                f.write(wiring_dot)
            print(f"Generated {filename}")
        
        # Generate cable length table
        generate_cable_length_table(all_devices, racks_config, layers, cable_config)
        generate_cable_length_html(all_devices, racks_config, layers, cable_config)
        
        # Process computer_info
        computer_info_raw = config.get("computer_info", [])
        if computer_info_raw:
            # Expand clusters
            computer_info = expand_computer_info_clusters(computer_info_raw)
            print(f"Expanded computer_info from {len(computer_info_raw)} entries to {len(computer_info)} devices")
            
            # Export
            export_computer_info_csv(computer_info)
            # export_computer_info_json(computer_info)
            export_computer_info_html(computer_info)
    
    else:
        print("Error: Configuration must have 'racks' with consolidated front/rear")
        return

if __name__ == "__main__":
    main()