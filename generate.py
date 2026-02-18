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
# Main
# -------------------------------------------------
def main():
    config = load_config()
    
    # Extract type color mappings from config
    type_colors = config.get("type_colors", {})
    
    if "racks" in config:
        racks_config = config["racks"]
        
        # Generate single comprehensive layout
        layout_dot = generate_rack_layout_dot(racks_config, type_colors)
        with open("rack_layout.dot", "w") as f:
            f.write(layout_dot)
        print("Generated rack_layout.dot")
        
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
    
    else:
        print("Error: Configuration must have 'racks' with consolidated front/rear")
        return

if __name__ == "__main__":
    main()