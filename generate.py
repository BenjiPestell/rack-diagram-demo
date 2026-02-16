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
# DOT Generator
# -------------------------------------------------

def generate_dot(rack, devices):

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
# Main
# -------------------------------------------------

def main():

    config = load_config()

    rack = config["rack"]
    devices = config["devices"]

    dot = generate_dot(rack, devices)

    with open("rack.dot", "w") as f:
        f.write(dot)

    print("Generated rack.dot")


if __name__ == "__main__":
    main()
