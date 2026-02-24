import math
from collections import defaultdict
from utils import get_device_color
from clusters import expand_wiring_clusters

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
    layer_edge_color = layer.get("edge_color", "#323232")
    layer_cable_type = layer.get("cable_type", "")
    edge_style = layer.get("edge_style", "solid")
    edge_width = layer.get("edge_width", "2.0")
    font_size = layer.get("font_size", 11)
    
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
            edge_attrs.append(f"fontsize={font_size - 3}")
            edge_attrs.append("fontname=\"Sinkin Sans 400 Regular\"")
        
        # Format edge attributes properly (commas added by join)
        edge_attrs_str = ", ".join(edge_attrs)
        
        lines.append(f"  {from_id} -- {to_id} [")
        lines.append(f"    {edge_attrs_str}")
        lines.append("  ];")
    
    lines.append("")
    lines.append("}")
    
    return "\n".join(lines)
