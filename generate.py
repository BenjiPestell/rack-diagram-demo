import yaml

# -------------------------------------------------
# Load config
# -------------------------------------------------
def load_config():
    with open("rack.yaml") as f:
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
# DOT Generator - Rack Layout
# -------------------------------------------------
def generate_rack_dot(rack, devices):
    total_u = rack["total_u"]
    
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
    lines.append("digraph rack {")
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
    lines.append("  rack [")
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
# DOT Generator - Wiring Diagram
# -------------------------------------------------
def generate_wiring_dot(layer, devices):
    """
    Generate a wiring diagram for a specific layer
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
    
    # Build device map for quick lookup
    device_map = {dev["name"]: dev for dev in devices}
    
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
    
    # -----------------------------
    # Define nodes
    # -----------------------------
    lines.append("  // Devices")
    for dev_name in sorted(devices_in_layer):
        dev = device_map.get(dev_name)
        if dev:
            # Use device color if available
            color = dev.get("color", node_color)
            node_id = dev_name.replace(" ", "_").replace("/", "_")
            lines.append(f"  \"{node_id}\" [")
            lines.append(f"    label=\"{dev_name}\",")
            lines.append(f"    fillcolor=\"{color}\"")
            lines.append("  ];")
        else:
            # External device not in rack
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
    rack = config["rack"]
    devices = config["devices"]
    
    # Generate rack layout
    rack_dot = generate_rack_dot(rack, devices)
    with open("rack_layout.dot", "w") as f:
        f.write(rack_dot)
    print("Generated rack_layout.dot")
    
    # Generate wiring diagrams for each layer
    layers = config.get("wiring_layers", [])
    for layer in layers:
        layer_name = layer["name"]
        # Create safe filename
        safe_name = layer_name.replace(" ", "_").replace("/", "_").lower()
        filename = f"wiring_{safe_name}.dot"
        
        wiring_dot = generate_wiring_dot(layer, devices)
        with open(filename, "w") as f:
            f.write(wiring_dot)
        print(f"Generated {filename}")

if __name__ == "__main__":
    main()