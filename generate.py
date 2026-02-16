import yaml

# -------------------------------------------------
# Load config
# -------------------------------------------------
def load_config():
    with open("demo_system.yaml") as f:
        return yaml.safe_load(f)

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
def generate_rack_dot(rack, devices):
    total_u = rack["total_u"]
    rack_id = rack.get("id", "rack")
    
    # -----------------------------
    # Layout + font settings
    # -----------------------------
    table_width = rack.get("table_width", 240)
    device_width = rack.get("device_width", 200)
    u_col_width = rack.get("u_col_width", 28)
    base_device_font = rack.get("device_font_size", 14)
    unit_font = rack.get("unit_font_size", 10)
    title_font = rack.get("title_font_size", 16)
    auto_scale = rack.get("auto_scale_font", True)
    
    slots = build_occupancy(devices, total_u)
    
    lines = []
    
    # -----------------------------
    # Graph header
    # -----------------------------
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
    lines.append("    fontname=\"Arial\"")
    lines.append("  ];")
    lines.append("")
    
    # -----------------------------
    # Rack node
    # -----------------------------
    lines.append(f"  {rack_id} [")
    lines.append("    label=<")
    lines.append("")
    
    # -----------------------------
    # Table start
    # -----------------------------
    lines.append("<TABLE")
    lines.append("  BORDER=\"2\"")
    lines.append("  CELLBORDER=\"1\"")
    lines.append("  CELLSPACING=\"0\"")
    lines.append("  CELLPADDING=\"4\"")
    lines.append(f"  WIDTH=\"{table_width}\"")
    lines.append(">")
    lines.append("")
    
    # -----------------------------
    # Title row
    # -----------------------------
    lines.append("<TR>")
    lines.append(
        f"<TD COLSPAN=\"3\" BGCOLOR=\"#DDDDDD\">"
        f"<FONT POINT-SIZE=\"{title_font}\">"
        f"<B>{rack['name']} ({total_u}U)</B>"
        f"</FONT></TD>"
    )
    lines.append("</TR>")
    
    processed = set()
    
    # -----------------------------
    # Rack rows (top to bottom)
    # -----------------------------
    for u in range(total_u, 0, -1):
        if u in processed:
            continue
        
        dev = slots.get(u)
        
        # -------------------------
        # Empty slot
        # -------------------------
        if not dev:
            lines.append("<TR>")
            lines.append(
                f"<TD WIDTH=\"{u_col_width}\">{u}</TD>"
            )
            lines.append("<TD COLSPAN=\"2\"></TD>")
            lines.append("</TR>")
            continue
        
        # -------------------------
        # Device slot
        # -------------------------
        name = dev["name"]
        units = dev["units"]
        color = dev.get("color", "#FFFFFF")
        
        # Auto-scale font for big devices
        if auto_scale:
            device_font = min(base_device_font + units, 20)
        else:
            device_font = base_device_font
        
        # First row
        lines.append("<TR>")
        lines.append(
            f"<TD WIDTH=\"{u_col_width}\">{u}</TD>"
        )
        lines.append(
            f"<TD COLSPAN=\"2\" "
            f"ROWSPAN=\"{units}\" "
            f"BGCOLOR=\"{color}\" "
            f"WIDTH=\"{device_width}\">"
            f"<FONT POINT-SIZE=\"{device_font}\">"
            f"<B>{name}</B>"
            f"</FONT>"
            f"<BR/>"
            f"<FONT POINT-SIZE=\"{unit_font}\">"
            f"{units}U"
            f"</FONT>"
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
                f"<TD WIDTH=\"{u_col_width}\">{u - i}</TD>"
            )
            lines.append("</TR>")
    
    # -----------------------------
    # Table end
    # -----------------------------
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
def generate_multi_rack_dot(racks_config):
    """
    Generate a diagram showing multiple racks side by side
    """
    lines = []
    
    # -----------------------------
    # Graph header
    # -----------------------------
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
    lines.append("    fontname=\"Arial\"")
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
        base_device_font = rack.get("device_font_size", 14)
        unit_font = rack.get("unit_font_size", 10)
        title_font = rack.get("title_font_size", 16)
        auto_scale = rack.get("auto_scale_font", True)
        
        slots = build_occupancy(devices, total_u)
        
        # -----------------------------
        # Rack node
        # -----------------------------
        lines.append(f"  {rack_id} [")
        lines.append("    label=<")
        lines.append("")
        
        # -----------------------------
        # Table start
        # -----------------------------
        lines.append("<TABLE")
        lines.append("  BORDER=\"2\"")
        lines.append("  CELLBORDER=\"1\"")
        lines.append("  CELLSPACING=\"0\"")
        lines.append("  CELLPADDING=\"4\"")
        lines.append(f"  WIDTH=\"{table_width}\"")
        lines.append(">")
        lines.append("")
        
        # -----------------------------
        # Title row
        # -----------------------------
        lines.append("<TR>")
        lines.append(
            f"<TD COLSPAN=\"3\" BGCOLOR=\"#DDDDDD\">"
            f"<FONT POINT-SIZE=\"{title_font}\">"
            f"<B>{rack['name']} ({total_u}U)</B>"
            f"</FONT></TD>"
        )
        lines.append("</TR>")
        
        processed = set()
        
        # -----------------------------
        # Rack rows (top to bottom)
        # -----------------------------
        for u in range(total_u, 0, -1):
            if u in processed:
                continue
            
            dev = slots.get(u)
            
            # -------------------------
            # Empty slot
            # -------------------------
            if not dev:
                lines.append("<TR>")
                lines.append(
                    f"<TD WIDTH=\"{u_col_width}\">{u}</TD>"
                )
                lines.append("<TD COLSPAN=\"2\"></TD>")
                lines.append("</TR>")
                continue
            
            # -------------------------
            # Device slot
            # -------------------------
            name = dev["name"]
            units = dev["units"]
            color = dev.get("color", "#FFFFFF")
            
            # Auto-scale font for big devices
            if auto_scale:
                device_font = min(base_device_font + units, 20)
            else:
                device_font = base_device_font
            
            # First row
            lines.append("<TR>")
            lines.append(
                f"<TD WIDTH=\"{u_col_width}\">{u}</TD>"
            )
            lines.append(
                f"<TD COLSPAN=\"2\" "
                f"ROWSPAN=\"{units}\" "
                f"BGCOLOR=\"{color}\" "
                f"WIDTH=\"{device_width}\">"
                f"<FONT POINT-SIZE=\"{device_font}\">"
                f"<B>{name}</B>"
                f"</FONT>"
                f"<BR/>"
                f"<FONT POINT-SIZE=\"{unit_font}\">"
                f"{units}U"
                f"</FONT>"
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
                    f"<TD WIDTH=\"{u_col_width}\">{u - i}</TD>"
                )
                lines.append("</TR>")
        
        # -----------------------------
        # Table end
        # -----------------------------
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
# DOT Generator - Wiring Diagram
# -------------------------------------------------
def generate_wiring_dot(layer, all_devices, rack_info=None):
    """
    Generate a wiring diagram for a specific layer
    all_devices is a dict mapping device name -> device info (including rack_id)
    rack_info is a dict mapping rack_id -> rack dict (with name, etc.)
    """
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
    
    lines = []
    
    # -----------------------------
    # Graph header (use 'graph' for undirected)
    # -----------------------------
    lines.append(f"graph \"{layer_name}\" {{")
    lines.append("")
    lines.append("  graph [")
    lines.append("    rankdir=TB,")
    lines.append("    nodesep=0.5,")
    lines.append("    ranksep=1.0,")
    lines.append("    bgcolor=\"white\",")
    lines.append(f"    label=\"{layer_name}\",")
    lines.append(f"    labelloc=t,")
    lines.append(f"    fontsize={font_size + 4},")
    lines.append("    fontname=\"Arial Bold\"")
    lines.append("  ];")
    lines.append("")
    lines.append("  node [")
    lines.append(f"    shape={node_shape},")
    lines.append(f"    style=\"{node_style}\",")
    lines.append(f"    fillcolor=\"{node_color}\",")
    lines.append(f"    fontsize={font_size},")
    lines.append("    fontname=\"Arial\",")
    lines.append("    margin=0.2")
    lines.append("  ];")
    lines.append("")
    lines.append("  edge [")
    lines.append(f"    color=\"{edge_color}\",")
    lines.append(f"    style={edge_style},")
    lines.append(f"    penwidth={edge_width}")
    lines.append("  ];")
    lines.append("")
    
    # -----------------------------
    # Collect all devices in this layer
    # -----------------------------
    devices_in_layer = set()
    for conn in connections:
        devices_in_layer.add(conn["from"])
        devices_in_layer.add(conn["to"])
    
    # Group devices by rack
    devices_by_rack = {}
    external_devices = []
    
    for dev_name in devices_in_layer:
        dev = all_devices.get(dev_name)
        if dev and "rack_id" in dev:
            rack_id = dev["rack_id"]
            if rack_id not in devices_by_rack:
                devices_by_rack[rack_id] = []
            devices_by_rack[rack_id].append((dev_name, dev))
        else:
            external_devices.append(dev_name)
    
    # -----------------------------
    # Define nodes grouped by rack
    # -----------------------------
    lines.append("  // Devices by rack")
    
    for rack_id in sorted(devices_by_rack.keys()):
        if show_rack_labels and len(devices_by_rack) > 1:
            # Get rack name if available, otherwise use rack_id
            rack_label = rack_id
            if rack_info and rack_id in rack_info:
                rack_label = rack_info[rack_id].get("name", rack_id)
            
            lines.append(f"  subgraph cluster_{rack_id} {{")
            lines.append(f"    label=\"{rack_label}\";")
            lines.append("    style=dashed;")
            lines.append("    color=\"#999999\";")
            lines.append("")
        
        for dev_name, dev in sorted(devices_by_rack[rack_id]):
            color = dev.get("color", node_color)
            node_id = dev_name.replace(" ", "_").replace("/", "_")
            lines.append(f"    \"{node_id}\" [")
            lines.append(f"      label=\"{dev_name}\",")
            lines.append(f"      fillcolor=\"{color}\"")
            lines.append("    ];")
        
        if show_rack_labels and len(devices_by_rack) > 1:
            lines.append("  }")
        
        lines.append("")
    
    # External devices
    if external_devices:
        lines.append("  // External devices")
        for dev_name in sorted(external_devices):
            node_id = dev_name.replace(" ", "_").replace("/", "_")
            lines.append(f"  \"{node_id}\" [")
            lines.append(f"    label=\"{dev_name}\"")
            lines.append("  ];")
        lines.append("")
    
    # -----------------------------
    # Define connections
    # -----------------------------
    lines.append("  // Connections")
    for conn in connections:
        from_id = conn["from"].replace(" ", "_").replace("/", "_")
        to_id = conn["to"].replace(" ", "_").replace("/", "_")
        
        # Optional connection label (port, cable type, etc.)
        label = conn.get("label", "")
        
        # Optional per-connection styling
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
    
    # Check if this is single rack or multi-rack config
    if "rack" in config and "devices" in config:
        # Single rack mode (backward compatible)
        rack = config["rack"]
        devices = config["devices"]
        
        # Add default rack_id if not present
        rack.setdefault("id", "rack")
        
        # Generate single rack layout
        rack_dot = generate_rack_dot(rack, devices)
        with open("rack_layout.dot", "w") as f:
            f.write(rack_dot)
        print("Generated rack_layout.dot")
        
        # Build device map with rack_id
        all_devices = {}
        for dev in devices:
            dev["rack_id"] = rack["id"]
            all_devices[dev["name"]] = dev
        
        # Build rack_info map
        rack_info = {rack["id"]: rack}
        
        # Generate wiring diagrams
        layers = config.get("wiring_layers", [])
        for layer in layers:
            layer_name = layer["name"]
            safe_name = layer_name.replace(" ", "_").replace("/", "_").lower()
            filename = f"wiring_{safe_name}.dot"
            
            wiring_dot = generate_wiring_dot(layer, all_devices, rack_info)
            with open(filename, "w") as f:
                f.write(wiring_dot)
            print(f"Generated {filename}")
    
    elif "racks" in config:
        # Multi-rack mode
        racks_config = config["racks"]
        
        # Generate individual rack layouts
        for rack_config in racks_config:
            rack = rack_config["rack"]
            devices = rack_config["devices"]
            rack_id = rack.get("id", "rack")
            
            rack_dot = generate_rack_dot(rack, devices)
            filename = f"rack_{rack_id}.dot"
            with open(filename, "w") as f:
                f.write(rack_dot)
            print(f"Generated {filename}")
        
        # Generate multi-rack overview
        multi_rack_dot = generate_multi_rack_dot(racks_config)
        with open("rack_layout_all.dot", "w") as f:
            f.write(multi_rack_dot)
        print("Generated rack_layout_all.dot")
        
        # Build combined device map and rack_info map
        all_devices = {}
        rack_info = {}
        for rack_config in racks_config:
            rack = rack_config["rack"]
            devices = rack_config["devices"]
            rack_id = rack.get("id", "rack")
            
            # Store rack info
            rack_info[rack_id] = rack
            
            for dev in devices:
                dev["rack_id"] = rack_id
                all_devices[dev["name"]] = dev
        
        # Generate wiring diagrams
        layers = config.get("wiring_layers", [])
        for layer in layers:
            layer_name = layer["name"]
            safe_name = layer_name.replace(" ", "_").replace("/", "_").lower()
            filename = f"wiring_{safe_name}.dot"
            
            wiring_dot = generate_wiring_dot(layer, all_devices, rack_info)
            with open(filename, "w") as f:
                f.write(wiring_dot)
            print(f"Generated {filename}")
    
    else:
        print("Error: Configuration must have either 'rack'+'devices' or 'racks'")
        return

if __name__ == "__main__":
    main()