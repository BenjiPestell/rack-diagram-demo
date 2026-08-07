import math
from collections import defaultdict
from utils import get_device_color
from clusters import expand_wiring_clusters


def _html_escape(text):
    """Escape characters that are special inside a Graphviz HTML-like label."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _key_row(color, text, font_size):
    """One swatch + caption row of the key table."""
    return (
        f"<TR><TD BGCOLOR=\"{color}\" WIDTH=\"22\"> </TD>"
        f"<TD ALIGN=\"LEFT\"><FONT POINT-SIZE=\"{font_size}\" FACE=\"Sinkin Sans 400 Regular\">"
        f"{_html_escape(text)}</FONT></TD></TR>"
    )


def _key_heading(text, font_size):
    """A section heading row spanning the key table."""
    return (
        f"<TR><TD COLSPAN=\"2\" BGCOLOR=\"#E8E8E8\">"
        f"<FONT POINT-SIZE=\"{font_size}\" FACE=\"Sinkin Sans 400 Regular\"><B>"
        f"{_html_escape(text)}</B></FONT></TD></TR>"
    )


def _build_key_cluster(used_types, type_colors, layer_colors, font_size):
    """
    Build the key cluster mapping colours to their meaning.

    used_types   : device type names actually appearing in this diagram
    type_colors  : the config's type_colors mapping
    layer_colors : [(layer_name, edge_color), ...] for the unified diagram, or
                   None for a single-layer diagram (where one colour says nothing)

    Returns a list of DOT lines, empty when there is nothing worth showing.
    """
    type_rows = []
    for type_name in sorted(used_types, key=str.lower):
        entry = type_colors.get(type_name)
        # type_colors values are either {color: "#hex", ...} or a plain hex string
        color = entry.get("color") if isinstance(entry, dict) else entry
        if color:
            type_rows.append((color, type_name))

    if not type_rows and not layer_colors:
        return []

    row_font = max(font_size - 1, 6)

    lines = []
    lines.append("  subgraph cluster_key {")
    lines.append("    label=\"Key\";")
    lines.append("    style=filled;")
    lines.append("    color=\"#FFFFFF\";")
    lines.append("    fontname=\"Sinkin Sans 400 Regular\";")
    lines.append("")
    lines.append("    \"__key__\" [")
    lines.append("      shape=plain,")
    lines.append("      label=<")
    lines.append("<TABLE BORDER=\"0\" CELLBORDER=\"1\" CELLSPACING=\"0\" CELLPADDING=\"4\">")

    if type_rows:
        lines.append(_key_heading("Hardware", row_font))
        for color, type_name in type_rows:
            lines.append(_key_row(color, type_name, row_font))

    if layer_colors:
        lines.append(_key_heading("Wiring layer", row_font))
        for layer_name, edge_color in layer_colors:
            lines.append(_key_row(edge_color, layer_name, row_font))

    lines.append("</TABLE>")
    lines.append("      >")
    lines.append("    ];")
    lines.append("  }")
    lines.append("")
    return lines


# -------------------------------------------------
# Generate Wiring Diagram with Radial Layout
# -------------------------------------------------
def generate_wiring_diagram(layer, all_devices, type_colors, show_key=True, layer_colors=None):
    """
    Generate a radial wiring diagram grouped by rack.

    Patch panel hops (produced by expand_wiring_clusters when via_patch_from /
    via_patch_to are set) are rendered with distinct styles:
      - solid hops  : device -> PP or PP -> device within the same rack
      - dashed hops : PP(from) -> PP(to) inter-rack run

    Patch panel devices appear as normal nodes in their rack cluster and get the
    "central node" bold treatment when they have more than one connection, just
    like any other device.

    show_key adds a "Key" cluster listing the hardware type colours used in this
    diagram. layer_colors, when given, adds a wiring-layer section to that key --
    used by the unified diagram, where edge colour identifies the source layer.
    """
    layer_name = layer["name"]
    connections_raw = layer.get("connections", [])

    # Styling - layer defaults
    layer_edge_color = layer.get("edge_color", "#323232")
    layer_cable_type = layer.get("cable_type", "")
    edge_style = layer.get("edge_style", "solid")
    edge_width = layer.get("edge_width", "2.0")
    font_size = layer.get("font_size", 10)

    # expand_wiring_clusters now also expands patch hops
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

    # ------------------------------------------------------------------
    # Collect devices and connection counts per rack
    # (patch hops are now ordinary from/to connections so this loop is
    #  identical to before -- patch panels appear naturally in their rack)
    # ------------------------------------------------------------------
    rack_devices = defaultdict(set)
    rack_connection_count = defaultdict(lambda: defaultdict(int))
    inter_rack_connections = []

    # rack_id -> display name, taken from the rack's configured name
    rack_names = {}
    for dev_info in all_devices.values():
        dev_rack_id = dev_info.get("rack_id")
        dev_rack_name = dev_info.get("rack_name")
        if dev_rack_id and dev_rack_name:
            rack_names[dev_rack_id] = dev_rack_name

    for conn in connections:
        from_dev = conn["from"]
        to_dev   = conn["to"]

        from_info = all_devices.get(from_dev)
        to_info   = all_devices.get(to_dev)

        if from_info and to_info:
            from_rack = from_info.get("rack_id")
            to_rack   = to_info.get("rack_id")

            rack_devices[from_rack].add(from_dev)
            rack_devices[to_rack].add(to_dev)

            if from_rack == to_rack:
                rack_connection_count[from_rack][from_dev] += 1
                rack_connection_count[from_rack][to_dev]   += 1
            else:
                inter_rack_connections.append((from_dev, to_dev, from_rack, to_rack))
                rack_connection_count[from_rack][from_dev] += 1
                rack_connection_count[to_rack][to_dev]     += 1
        else:
            if not from_info:
                print(f"Warning: Device '{from_dev}' not found in device map (used in {layer_name})")
            if not to_info:
                print(f"Warning: Device '{to_dev}' not found in device map (used in {layer_name})")

    # Central nodes per rack (>1 connection -> bold node)
    rack_central = defaultdict(list)
    for rack_id in rack_devices:
        for dev_name, conn_count in rack_connection_count[rack_id].items():
            if conn_count > 1:
                rack_central[rack_id].append(dev_name)

    # ------------------------------------------------------------------
    # Node clusters
    # ------------------------------------------------------------------
    lines.append("  // Devices grouped by rack and external groups")
    lines.append("")

    external_groups = {}
    for rack_id in sorted(rack_devices.keys()):
        if rack_id == "external":
            for dev_name in sorted(rack_devices[rack_id]):
                dev_info   = all_devices.get(dev_name)
                group_name = dev_info.get("external_group", "External Devices")
                if group_name not in external_groups:
                    external_groups[group_name] = set()
                external_groups[group_name].add(dev_name)

    for rack_id in sorted(rack_devices.keys()):
        if rack_id == "external":
            continue

        devices = rack_devices[rack_id]

        lines.append(f"  subgraph cluster_{rack_id} {{")
        # Prefer the rack's configured name; fall back to a tidied id
        rack_label = rack_names.get(rack_id) or (
            f"Rack {rack_id.replace('rack', '').replace('_front', '').replace('_rear', '').strip('_')}"
        )
        lines.append(f"    label=\"{rack_label}\";")
        lines.append("    style=filled;")
        lines.append("    color=\"#F5F5F5\";")
        lines.append("    fontname=\"Sinkin Sans 400 Regular\";")
        lines.append("")

        central_nodes = rack_central.get(rack_id, [])
        for dev_name in sorted(central_nodes):
            node_id  = dev_name.replace(" ", "_").replace("/", "_")
            dev_info = all_devices.get(dev_name)
            color    = get_device_color(dev_info, type_colors)
            connection_count = rack_connection_count[rack_id][dev_name]

            lines.append(f"    \"{node_id}\" [")
            lines.append(f"      label=\"{dev_name}\\n({connection_count} conn)\",")
            lines.append(f"      fillcolor=\"{color}\",")
            lines.append("      penwidth=2.5")
            lines.append("    ];")

        for dev_name in sorted(devices - set(central_nodes)):
            node_id  = dev_name.replace(" ", "_").replace("/", "_")
            dev_info = all_devices.get(dev_name)
            color    = get_device_color(dev_info, type_colors)

            lines.append(f"    \"{node_id}\" [")
            lines.append(f"      label=\"{dev_name}\",")
            lines.append(f"      fillcolor=\"{color}\"")
            lines.append("    ];")

        lines.append("  }")
        lines.append("")

    for group_name in sorted(external_groups.keys()):
        devices  = external_groups[group_name]
        group_id = group_name.replace(" ", "_").replace("/", "_")

        lines.append(f"  subgraph cluster_external_{group_id} {{")
        lines.append(f"    label=\"{group_name}\";")
        lines.append("    style=filled;")
        lines.append("    color=\"#E0E0E0\";")
        lines.append("    fontname=\"Sinkin Sans 400 Regular\";")
        lines.append("")

        central_nodes = rack_central.get("external", [])
        for dev_name in sorted(devices):
            if dev_name not in central_nodes:
                continue
            node_id  = dev_name.replace(" ", "_").replace("/", "_")
            dev_info = all_devices.get(dev_name)
            color    = get_device_color(dev_info, type_colors)
            connection_count = rack_connection_count["external"][dev_name]

            lines.append(f"    \"{node_id}\" [")
            lines.append(f"      label=\"{dev_name}\\n({connection_count} conn)\",")
            lines.append(f"      fillcolor=\"{color}\",")
            lines.append("      penwidth=2.5")
            lines.append("    ];")

        for dev_name in sorted(devices):
            if dev_name in central_nodes:
                continue
            node_id  = dev_name.replace(" ", "_").replace("/", "_")
            dev_info = all_devices.get(dev_name)
            color    = get_device_color(dev_info, type_colors)

            lines.append(f"    \"{node_id}\" [")
            lines.append(f"      label=\"{dev_name}\",")
            lines.append(f"      fillcolor=\"{color}\"")
            lines.append("    ];")

        lines.append("  }")
        lines.append("")

    # ------------------------------------------------------------------
    # Key -- colour swatches for the hardware types shown in this diagram
    # ------------------------------------------------------------------
    if show_key:
        used_types = set()
        for devices in rack_devices.values():
            for dev_name in devices:
                dev_info = all_devices.get(dev_name) or {}
                # Devices with an explicit colour override aren't type-driven,
                # so listing their type would misrepresent the swatch
                if "color" in dev_info:
                    continue
                dev_type = dev_info.get("type")
                if dev_type:
                    used_types.add(dev_type)

        lines.extend(_build_key_cluster(used_types, type_colors, layer_colors, font_size))

    # ------------------------------------------------------------------
    # Edges
    # ------------------------------------------------------------------
    lines.append("  // Connections")
    for conn in connections:
        from_dev = conn["from"]
        to_dev   = conn["to"]
        from_id  = from_dev.replace(" ", "_").replace("/", "_")
        to_id    = to_dev.replace(" ", "_").replace("/", "_")

        label      = conn.get("label", "")
        cable_type = conn.get("cable_type", "")
        if not label and cable_type:
            label = cable_type

        conn_edge_color = conn.get("edge_color", layer_edge_color)
        conn_width      = conn.get("width", edge_width)

        # -- Patch panel edge styling -------------------------------------
        # _patch_style == "patched" means the connection routes via patch panels.
        # We keep the direct A -- B edge but render it distinctly:
        #   dashed line  : signals the run is not direct copper end-to-end
        #   thicker pen  : remains legible against normal edges
        #   patch label  : shown as a second line below cable type / label
        patch_style = conn.get("_patch_style")
        if patch_style == "patched":
            conn_style  = "dashed"
            conn_width  = str(float(edge_width) + 0.5)
            patch_label = conn.get("_patch_label", "")
            # Append patch annotation to the edge label (second line)
            if patch_label:
                if label:
                    label = label + "\n" + patch_label
                else:
                    label = patch_label
        else:
            # Normal connection -- honour per-conn or layer style
            conn_style = conn.get("style", edge_style)

        edge_attrs = [
            f"color=\"{conn_edge_color}\"",
            f"style={conn_style}",
            f"penwidth={conn_width}",
        ]

        if label:
            edge_attrs.append(f"label=\"{'   ' + label}\"")
            edge_attrs.append(f"fontsize={font_size - 3}")
            edge_attrs.append("fontname=\"Sinkin Sans 400 Regular\"")

        edge_attrs_str = ", ".join(edge_attrs)

        lines.append(f"  \"{from_id}\" -- \"{to_id}\" [")
        lines.append(f"    {edge_attrs_str}")
        lines.append("  ];")

    lines.append("")
    lines.append("}")

    return "\n".join(lines)