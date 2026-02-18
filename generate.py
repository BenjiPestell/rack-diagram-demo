import yaml

# -------------------------------------------------
# Load config
# -------------------------------------------------
def load_config():
    with open("checkers.yaml") as f:
        return yaml.safe_load(f)

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
    # Explicit color takes precedence
    if "color" in device:
        return device["color"]
    
    # Try to get color from type
    if "type" in device:
        device_type = device["type"]
        if device_type in type_colors:
            return type_colors[device_type]
    
    # Default fallback
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
        start = dev["start_u"]
        units = dev["units"]
        
        if units < 1:
            raise ValueError(f"{name} has invalid unit size")
        
        for u in range(start, start - units, -1):
            if u < 1:
                raise ValueError(
                    f"{name} exceeds bottom of rack"
                )
            if u in slots:
                raise ValueError(
                    f"U{u} conflict between "
                    f"{slots[u]['name']} and {name}"
                )
            slots[u] = dev
    
    return slots

# -------------------------------------------------
# DOT Generator - Single Rack Layout
# -------------------------------------------------
def generate_rack_dot(rack, devices, type_colors):
    total_u = rack["total_u"]
    rack_id = rack.get("id", "rack")
    
    # Layout + font settings
    table_width = rack.get("table_width", 240)
    device_width = rack.get("device_width", 200)
    u_col_width = rack.get("u_col_width", 28)
    base_device_font = rack.get("device_font_size", 13.5)
    unit_font = rack.get("unit_font_size", 15)
    title_font = rack.get("title_font_size", 16)
    auto_scale = rack.get("auto_scale_font", True)
    
    slots = build_occupancy(devices, total_u)
    
    lines = []
    
    # Graph header
    lines.append(f"digraph \"{rack_id}\" {{")
    lines.append("")
    lines.append("  graph [")
    lines.append("    rankdir=TB,")
    lines.append("    nodesep=0,")
    lines.append("    ranksep=0,")
    lines.append("    bgcolor=\"white\"")
    lines.append("  ];")
    lines.append("")
    lines.append("  node [")
    lines.append("    shape=plain,")
    lines.append("    fontname=\"Sinkin Sans 400 Regular\"")
    lines.append("  ];")
    lines.append("")
    
    # Rack node
    lines.append(f"  {rack_id} [")
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
    lines.append("<TR>")
    lines.append(
        f"<TD COLSPAN=\"3\" BGCOLOR=\"#DDDDDD\">"
        f"<FONT POINT-SIZE=\"{title_font}\" FACE=\"Sinkin Sans 400 Regular\">"
        f"<B>{rack['name']} ({total_u}U)</B>"
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
        device_content = f"<FONT POINT-SIZE=\"{device_font}\" FACE=\"Sinkin Sans 400 Regular\">{name}</FONT>"
        
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
    lines.append("}")
    
    return "\n".join(lines)

# -------------------------------------------------
# DOT Generator - Multi-Rack Layout
# -------------------------------------------------
def generate_multi_rack_dot(racks_config, type_colors):
    """
    Generate a diagram showing multiple racks side by side
    """
    lines = []
    
    # Graph header
    lines.append("digraph multi_rack {")
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
    
    # Generate each rack as a subgraph
    for rack_config in racks_config:
        rack = rack_config["rack"]
        devices = rack_config["devices"]
        rack_id = rack.get("id", "rack")
        
        total_u = rack["total_u"]
        table_width = rack.get("table_width", 240)
        device_width = rack.get("device_width", 200)
        u_col_width = rack.get("u_col_width", 28)
        base_device_font = rack.get("device_font_size", 13.5)
        unit_font = rack.get("unit_font_size", 15)
        title_font = rack.get("title_font_size", 16)
        auto_scale = rack.get("auto_scale_font", True)
        
        slots = build_occupancy(devices, total_u)
        
        # Rack node
        lines.append(f"  {rack_id} [")
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
        lines.append("<TR>")
        lines.append(
            f"<TD COLSPAN=\"3\" BGCOLOR=\"#DDDDDD\">"
            f"<FONT POINT-SIZE=\"{title_font}\" FACE=\"Sinkin Sans 400 Regular\">"
            f"<B>{rack['name']} ({total_u}U)</B>"
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
    
    # Force racks to be side by side at same rank
    if len(racks_config) > 1:
        rack_ids = [r["rack"].get("id", "rack") for r in racks_config]
        lines.append(f"  {{ rank=same; {'; '.join(rack_ids)}; }}")
        lines.append("")
    
    lines.append("}")
    
    return "\n".join(lines)

# -------------------------------------------------
# Hierarchical Wiring Diagram Generator
# -------------------------------------------------
def generate_hierarchical_wiring_dot(layer, all_devices, rack_info=None, type_colors=None):
    """
    Generate a hierarchical/layered wiring diagram.
    
    Devices are organized by "tier" (function/role) to create a cleaner,
    more vertical layout instead of spreading horizontally.
    
    Default tier assignments:
    - Tier 0 (Sources): PDUs, switches, external devices
    - Tier 1 (Compute): PCs, servers, processing units
    - Tier 2 (I/O): Shelves, converters, specialized devices
    
    Can be customized via layer config:
      tier_mapping:
        "device_name": 0  # Custom tier assignment
    """
    if type_colors is None:
        type_colors = {}
    
    layer_name = layer["name"]
    connections = layer.get("connections", [])
    
    # Styling options
    node_shape = layer.get("node_shape", "box")
    node_style = layer.get("node_style", "rounded,filled")
    node_color = layer.get("node_color", "#E8F4F8")
    edge_color = layer.get("edge_color", "#333333")
    edge_style = layer.get("edge_style", "solid")
    edge_width = layer.get("edge_width", "2.0")
    font_size = layer.get("font_size", 12)
    show_rack_labels = layer.get("show_rack_labels", True)
    
    # Custom tier mapping
    custom_tiers = layer.get("tier_mapping", {})
    
    lines = []
    
    # Graph header
    lines.append(f"graph \"{layer_name}\" {{")
    lines.append("")
    lines.append("  graph [")
    lines.append("    rankdir=TB,")
    lines.append("    nodesep=0.8,")
    lines.append("    ranksep=1.5,")
    lines.append("    bgcolor=\"white\",")
    lines.append(f"    label=\"{layer_name}\",")
    lines.append(f"    labelloc=t,")
    lines.append(f"    fontsize={font_size + 4},")
    lines.append("    fontname=\"Sinkin Sans 400 Regular\"")
    lines.append("  ];")
    lines.append("")
    lines.append("  node [")
    lines.append(f"    shape={node_shape},")
    lines.append(f"    style=\"{node_style}\",")
    lines.append(f"    fillcolor=\"{node_color}\",")
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
    
    # Collect all devices and assign tiers
    devices_in_layer = {}
    for conn in connections:
        devices_in_layer[conn["from"]] = None
        devices_in_layer[conn["to"]] = None
    
    def assign_tier(dev_name):
        """Assign a device to a tier based on name/type"""
        if dev_name in custom_tiers:
            return custom_tiers[dev_name]
        
        name_lower = dev_name.lower()
        
        # Tier 0: Sources (PDUs, switches, external power/network sources)
        if any(x in name_lower for x in ["pdu", "switch", "power", "source"]):
            return 0
        
        # Tier 2: I/O and infrastructure (shelves, converters, terrain)
        if any(x in name_lower for x in ["shelf", "converter", "fibre", "network", "terrain"]):
            return 2
        
        # Tier 1: Compute (default for PCs, servers, speedgoat, etc.)
        return 1
    
    # Build tier mapping
    device_tiers = {}
    for dev_name in devices_in_layer:
        device_tiers[dev_name] = assign_tier(dev_name)
    
    # Group devices by tier and rack
    tiers = {}
    for dev_name, tier in device_tiers.items():
        if tier not in tiers:
            tiers[tier] = {"by_rack": {}, "external": []}
        
        dev = all_devices.get(dev_name)
        if dev and "rack_id" in dev:
            rack_id = dev["rack_id"]
            if rack_id not in tiers[tier]["by_rack"]:
                tiers[tier]["by_rack"][rack_id] = []
            tiers[tier]["by_rack"][rack_id].append((dev_name, dev))
        else:
            tiers[tier]["external"].append(dev_name)
    
    # Define nodes grouped by tier and rack
    tier_names = {
        0: "Sources",
        1: "Compute",
        2: "Infrastructure"
    }
    
    for tier_num in sorted(tiers.keys()):
        tier_data = tiers[tier_num]
        tier_name = tier_names.get(tier_num, f"Tier {tier_num}")
        
        lines.append(f"  // {tier_name}")
        
        # Racks in this tier
        for rack_id in sorted(tier_data["by_rack"].keys()):
            if show_rack_labels:
                rack_label = rack_id
                if rack_info and rack_id in rack_info:
                    rack_label = rack_info[rack_id].get("name", rack_id)
                
                lines.append(f"  subgraph cluster_tier{tier_num}_{rack_id} {{")
                lines.append(f"    label=\"{rack_label}\";")
                lines.append("    style=dashed;")
                lines.append("    color=\"#999999\";")
                lines.append("    fontname=\"Sinkin Sans 400 Regular\";")
                lines.append("")
            
            for dev_name, dev in sorted(tier_data["by_rack"][rack_id]):
                color = get_device_color(dev, type_colors)
                node_id = dev_name.replace(" ", "_").replace("/", "_")
                lines.append(f"    \"{node_id}\" [")
                lines.append(f"      label=\"{dev_name}\",")
                lines.append(f"      fillcolor=\"{color}\"")
                lines.append("    ];")
            
            if show_rack_labels:
                lines.append("  }")
            
            lines.append("")
        
        # External devices in this tier
        if tier_data["external"]:
            lines.append(f"  // {tier_name} - External")
            for dev_name in sorted(tier_data["external"]):
                node_id = dev_name.replace(" ", "_").replace("/", "_")
                dev = all_devices.get(dev_name)
                color = get_device_color(dev, type_colors) if dev else node_color
                lines.append(f"  \"{node_id}\" [")
                lines.append(f"    label=\"{dev_name}\",")
                lines.append(f"    fillcolor=\"{color}\"")
                lines.append("  ];")
            lines.append("")
    
    # Enforce tier ranks
    for tier_num in sorted(tiers.keys()):
        tier_data = tiers[tier_num]
        tier_nodes = []
        
        for rack_id in tier_data["by_rack"]:
            for dev_name, _ in tier_data["by_rack"][rack_id]:
                node_id = dev_name.replace(" ", "_").replace("/", "_")
                tier_nodes.append(f"\"{node_id}\"")
        
        for dev_name in tier_data["external"]:
            node_id = dev_name.replace(" ", "_").replace("/", "_")
            tier_nodes.append(f"\"{node_id}\"")
        
        if tier_nodes:
            lines.append(f"  {{ rank=same; {'; '.join(tier_nodes)}; }}")
    
    lines.append("")
    
    # Define connections
    lines.append("  // Connections")
    for conn in connections:
        from_id = conn["from"].replace(" ", "_").replace("/", "_")
        to_id = conn["to"].replace(" ", "_").replace("/", "_")
        
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
            edge_attrs.append(f"label=\"  {label}  \"")
            edge_attrs.append(f"fontsize={font_size - 2}")
            edge_attrs.append("fontname=\"Sinkin Sans 400 Regular\"")
        
        lines.append(f"  \"{from_id}\" -- \"{to_id}\" [")
        lines.append(f"    {', '.join(edge_attrs)}")
        lines.append("  ];")
    
    lines.append("")
    lines.append("}")
    
    return "\n".join(lines)

# -------------------------------------------------
# Main
# -------------------------------------------------
def main():
    config = load_config()
    
    # Extract type color mappings from config (if defined)
    type_colors = config.get("type_colors", {})
    
    # Check if this is single rack or multi-rack config
    if "rack" in config and "devices" in config:
        # Single rack mode (backward compatible)
        rack = config["rack"]
        devices = config["devices"]
        
        rack.setdefault("id", "rack")
        
        rack_dot = generate_rack_dot(rack, devices, type_colors)
        with open("rack_layout.dot", "w") as f:
            f.write(rack_dot)
        print("Generated rack_layout.dot")
        
        all_devices = {}
        for dev in devices:
            dev["rack_id"] = rack["id"]
            all_devices[dev["name"]] = dev
        
        rack_info = {rack["id"]: rack}
        
        layers = config.get("wiring_layers", [])
        for layer in layers:
            layer_name = layer["name"]
            safe_name = layer_name.replace(" ", "_").replace("/", "_").lower()
            filename = f"wiring_{safe_name}.dot"
            
            wiring_dot = generate_hierarchical_wiring_dot(layer, all_devices, rack_info, type_colors)
            with open(filename, "w") as f:
                f.write(wiring_dot)
            print(f"Generated {filename}")
    
    elif "racks" in config:
        # Multi-rack mode
        racks_config = config["racks"]
        
        multi_rack_dot = generate_multi_rack_dot(racks_config, type_colors)
        with open("rack_layout.dot", "w") as f:
            f.write(multi_rack_dot)
        print("Generated rack_layout.dot")
        
        all_devices = {}
        rack_info = {}
        for rack_config in racks_config:
            rack = rack_config["rack"]
            devices = rack_config["devices"]
            rack_id = rack.get("id", "rack")
            
            rack_info[rack_id] = rack
            
            for dev in devices:
                dev["rack_id"] = rack_id
                all_devices[dev["name"]] = dev
        
        layers = config.get("wiring_layers", [])
        for layer in layers:
            layer_name = layer["name"]
            safe_name = layer_name.replace(" ", "_").replace("/", "_").lower()
            filename = f"wiring_{safe_name}.dot"
            
            wiring_dot = generate_hierarchical_wiring_dot(layer, all_devices, rack_info, type_colors)
            with open(filename, "w") as f:
                f.write(wiring_dot)
            print(f"Generated {filename}")
    
    else:
        print("Error: Configuration must have either 'rack'+'devices' or 'racks'")
        return

if __name__ == "__main__":
    main()