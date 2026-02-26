import csv
import math
import re
from clusters import expand_wiring_clusters
from utils import hex_to_color_name


# -------------------------------------------------
# Build all_devices lookup from parsed YAML config
# -------------------------------------------------
def build_all_devices(rack_configs, external_device_groups=None):
    """
    Build the all_devices dict consumed by calculate_cable_length.

    Each entry has the shape:
        {
            "rack_id":             str,    # rack id string, or "external"
            "side":                str,    # "front" | "rear" | "external"
            "start_u":             int,    # top U position (None for undefined / external)
            "units":               int,    # height in U (1 for external)
            "distance_from_racks": float,  # metres; 0 for rack devices, group value for external
        }

    Parameters
    ----------
    rack_configs : list
        Parsed rack list from YAML (each item is a dict with a "rack" sub-dict
        plus "front" and "rear" device lists).
    external_device_groups : list, optional
        Parsed external_devices list from YAML.  Each item:
            {
                "name":                str,
                "distance_from_racks": float,   # metres
                "devices":             list of device dicts
            }
        Cluster patterns (name contains "{N}" with start/end) are expanded here
        so that every resolved name (e.g. "Projector 3") gets its own entry.
    """
    all_devices = {}

    # --- Rack devices ---
    for rack_config in rack_configs:
        rack_id = rack_config["rack"].get("id", "rack")
        for side in ("front", "rear"):
            for dev in rack_config.get(side, []):
                name    = dev.get("name", "")
                start_u = dev.get("start_u")
                units   = dev.get("units", 1)
                start_n = dev.get("start")
                end_n   = dev.get("end")
                spacing = dev.get("spacing", 0)

                if start_n is not None and end_n is not None and "{N}" in name:
                    # Expand cluster pattern
                    step = units + (spacing or 0)
                    for i, n in enumerate(range(start_n, end_n + 1)):
                        resolved_name    = name.replace("{N}", str(n))
                        member_start_u   = (start_u - i * step) if start_u else None
                        all_devices[resolved_name] = {
                            "rack_id":             rack_id,
                            "side":                side,
                            "start_u":             member_start_u,
                            "units":               units,
                            "distance_from_racks": 0,
                        }
                else:
                    all_devices[name] = {
                        "rack_id":             rack_id,
                        "side":                side,
                        "start_u":             start_u,
                        "units":               units,
                        "distance_from_racks": 0,
                    }

    # --- External devices ---
    for group in (external_device_groups or []):
        dist = float(group.get("distance_from_racks", 0) or 0)
        for dev in group.get("devices", []):
            name    = dev.get("name", "")
            start_n = dev.get("start")
            end_n   = dev.get("end")

            if start_n is not None and end_n is not None and "{N}" in name:
                for n in range(start_n, end_n + 1):
                    resolved_name = name.replace("{N}", str(n))
                    all_devices[resolved_name] = {
                        "rack_id":             "external",
                        "side":                "external",
                        "start_u":             None,
                        "units":               1,
                        "distance_from_racks": dist,
                    }
            else:
                all_devices[name] = {
                    "rack_id":             "external",
                    "side":                "external",
                    "start_u":             None,
                    "units":               1,
                    "distance_from_racks": dist,
                }

    return all_devices


# -------------------------------------------------
# Cable length calculation
# -------------------------------------------------
def calculate_cable_length(from_device, to_device, all_devices, rack_configs, config):
    """
    Calculate minimum cable length needed for a connection.

    Formula:
        (unit_delta * 0.045)
        + f2b_length          (see below)
        + inter_rack_length   (inter-rack distance if both devices are in racks)
        + external_length     (distance_from_racks if either/both endpoints are external)
        + cable_slack

    unit_delta:
        Intra-rack (both in same rack):
            Absolute difference in bottom-U positions.
        Inter-rack (both in different racks, neither external):
            (from_start_u - 1) + (to_start_u - 1) — distance to U1 on each end.
        External connection (one or both endpoints external):
            Only the rack-side device contributes its distance to U1 (i.e. to
            the cable exit point at the bottom front of the rack).  The external
            side contributes no U distance; its physical run is in external_length.
        Undefined start_u on either side: contributes 0.

    f2b_length:
        Cables always exit at the bottom REAR of a rack. Each front-mounted
        rack endpoint therefore adds one front-to-back traversal. The total
        f2b_length = (number of front-mounted rack endpoints) * front_to_back.
        External endpoints contribute 0 (no rack to traverse).
        Examples: front→external = 1×, rear→external = 0×,
        front→front (diff rack) = 2×, front→rear (diff rack) = 1×,
        front→front (same rack) = 2×, front→rear (same rack) = 1×,
        rear→rear (any) = 0×.

    external_length:
        Sum of distance_from_racks for every external endpoint.
        Populated via build_all_devices() from the external_devices YAML section.

    inter_rack_length:
        rack_delta * inter_rack_distance, only when both devices are in
        different (non-external) racks.
    """

    # Get device info
    from_info = all_devices.get(from_device)
    to_info   = all_devices.get(to_device)

    if not from_info or not to_info:
        return None

    # Config values
    cable_slack        = config.get("cable_slack_length",  0.2)
    standard_u_height  = config.get("standard_u_height",   0.045)
    front_to_back      = config.get("front_to_back_length", 0.5)
    inter_rack_distance = config.get("inter_rack_distance", 2.5)

    # Build rack name / position maps
    rack_name_map     = {}
    rack_position_map = {}
    for pos, rack_config in enumerate(rack_configs):
        rack_id   = rack_config["rack"].get("id",   "rack")
        rack_name = rack_config["rack"].get("name",  rack_id)
        rack_name_map[rack_id]     = rack_name
        rack_position_map[rack_id] = pos

    from_rack     = from_info.get("rack_id")
    to_rack       = to_info.get("rack_id")
    from_side     = from_info.get("side",    "front")
    to_side       = to_info.get("side",      "front")
    from_start_u  = from_info.get("start_u", 0)
    to_start_u    = to_info.get("start_u",   0)
    from_units    = from_info.get("units",   1)
    to_units      = to_info.get("units",     1)

    from_is_ext = (from_rack == "external")
    to_is_ext   = (to_rack   == "external")

    # Rack display names (show "External" for external endpoints)
    from_rack_name = "External" if from_is_ext else rack_name_map.get(from_rack, from_rack)
    to_rack_name   = "External" if to_is_ext   else rack_name_map.get(to_rack,   to_rack)

    # ------------------------------------------------------------------
    # 1. Unit delta
    # ------------------------------------------------------------------
    if not from_is_ext and not to_is_ext and from_rack != to_rack:
        # Pure inter-rack: distance from each device to U1
        from_u_dist = (from_start_u - 1) if from_start_u else 0
        to_u_dist   = (to_start_u   - 1) if to_start_u   else 0
        unit_delta  = from_u_dist + to_u_dist

    elif from_is_ext and not to_is_ext:
        # External → rack: only the rack-side device contributes U distance
        unit_delta = (to_start_u - 1) if to_start_u else 0

    elif not from_is_ext and to_is_ext:
        # Rack → external: only the rack-side device contributes U distance
        unit_delta = (from_start_u - 1) if from_start_u else 0

    elif from_is_ext and to_is_ext:
        # Both external: no U distance
        unit_delta = 0

    else:
        # Intra-rack: absolute difference in bottom-U positions
        if from_start_u and to_start_u:
            from_bottom_u = from_start_u - from_units + 1
            to_bottom_u   = to_start_u   - to_units   + 1
            unit_delta    = abs(from_bottom_u - to_bottom_u)
        else:
            unit_delta = 0

    unit_length = unit_delta * standard_u_height

    # ------------------------------------------------------------------
    # 2. Front-to-back
    #
    # Cables always exit at the bottom REAR of a rack. A front-mounted
    # device therefore requires one internal front-to-back traversal
    # before the cable can exit; a rear-mounted device does not.
    #
    # F2B multiplier = number of rack-side endpoints that are on the FRONT:
    #
    #   front → external          1 × f2b  (1 front endpoint)
    #   rear  → external          0 × f2b  (0 front endpoints)
    #   front → front, diff rack  2 × f2b  (2 front endpoints)
    #   front → rear,  diff rack  1 × f2b  (1 front endpoint)
    #   rear  → rear,  diff rack  0 × f2b  (0 front endpoints)
    #   front → rear,  same rack  1 × f2b  (1 front endpoint — shared rear)
    #   front → front, same rack  2 × f2b  (2 front endpoints — back and forth)
    #   rear  → rear,  same rack  0 × f2b  (0 front endpoints)
    #   external → external       0 × f2b  (no rack traversal at all)
    # ------------------------------------------------------------------
    f2b_count = 0
    if not from_is_ext and from_side == "front":
        f2b_count += 1
    if not to_is_ext and to_side == "front":
        f2b_count += 1
    f2b_length = f2b_count * front_to_back

    # ------------------------------------------------------------------
    # 3. Inter-rack distance (both devices in different physical racks)
    # ------------------------------------------------------------------
    inter_rack_length = 0
    if not from_is_ext and not to_is_ext and from_rack != to_rack:
        from_pos = rack_position_map.get(from_rack, 0)
        to_pos   = rack_position_map.get(to_rack,   0)
        rack_delta        = abs(from_pos - to_pos)
        inter_rack_length = rack_delta * inter_rack_distance

    # ------------------------------------------------------------------
    # 4. External distance (distance_from_racks for each external endpoint)
    #
    #    This is stored on the device entry as "distance_from_racks" and
    #    must be populated when building all_devices from the YAML
    #    external_devices section.
    # ------------------------------------------------------------------
    external_length = 0
    if from_is_ext:
        external_length += from_info.get("distance_from_racks", 0) or 0
    if to_is_ext:
        external_length += to_info.get("distance_from_racks", 0) or 0

    # ------------------------------------------------------------------
    # 5. Total — round up to nearest 0.5 m
    # ------------------------------------------------------------------
    total_length = unit_length + f2b_length + inter_rack_length + external_length + cable_slack
    total_length = math.ceil(total_length * 2) / 2

    return {
        "from_rack":          from_rack_name,
        "to_rack":            to_rack_name,
        "unit_delta":         unit_delta,
        "unit_length":        unit_length,
        "f2b_length":         f2b_length,
        "inter_rack_length":  inter_rack_length,
        "external_length":    external_length,
        "cable_slack":        cable_slack,
        "total_length":       total_length,
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
            color: white;
            font-weight: bold;
        }
        .ext-row {
            background-color: #fffbf0;
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
                <th class="metric">External (m)</th>
                <th class="metric">Slack (m)</th>
                <th class="metric total">Min Length (m)</th>
            </tr>
        </thead>
        <tbody>
"""

    for layer in wiring_layers:
        layer_name       = layer["name"]
        connections_raw  = layer.get("connections", [])
        layer_cable_type = layer.get("cable_type",  "")
        connections      = expand_wiring_clusters(connections_raw, layer_cable_type)

        for conn in connections:
            from_dev  = conn["from"]
            to_dev    = conn["to"]
            from_info = all_devices.get(from_dev)
            to_info   = all_devices.get(to_dev)

            if not from_info or not to_info:
                continue

            cable_data = calculate_cable_length(from_dev, to_dev, all_devices, racks_config, config)
            if not cable_data:
                continue

            cable_type  = conn.get("cable_type", "")
            has_external = (
                from_info.get("rack_id") == "external"
                or to_info.get("rack_id") == "external"
            )
            row_class = ' class="ext-row"' if has_external else ''

            html += f"""            <tr{row_class}>
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
                <td class="metric">{cable_data['external_length']:.1f}</td>
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
# Generate cable length CSV table
# -------------------------------------------------
def generate_cable_length_table(all_devices, racks_config, wiring_layers, config, output_file="output/cable_lengths.csv"):
    """Generate a CSV table with cable length calculations for all connections"""

    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)

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
            "External Length (m)",
            "Cable Slack (m)",
            "Min Cable Length (m)",
        ])

        for layer in wiring_layers:
            layer_name       = layer["name"]
            connections_raw  = layer.get("connections", [])
            layer_cable_type = layer.get("cable_type",  "")
            connections      = expand_wiring_clusters(connections_raw, layer_cable_type)

            for conn in connections:
                from_dev  = conn["from"]
                to_dev    = conn["to"]
                from_info = all_devices.get(from_dev)
                to_info   = all_devices.get(to_dev)

                if not from_info or not to_info:
                    continue

                cable_data = calculate_cable_length(from_dev, to_dev, all_devices, racks_config, config)
                if not cable_data:
                    continue

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
                    f"{cable_data['external_length']:.1f}",
                    f"{cable_data['cable_slack']:.3f}",
                    f"{cable_data['total_length']:.2f}",
                ])

    print(f"Generated cable length table: {output_file}")


# -------------------------------------------------
# Generate cable summary (for ordering) — CSV
# -------------------------------------------------
def generate_cable_summary_csv(all_devices, racks_config, wiring_layers, config, output_file="output/cable_summary.csv"):
    """
    Generate a summary of cables needed for ordering.
    Groups cables by type and rounded length, showing quantities for each length.
    """

    # {(cable_type, color_name): {length: quantity}}
    cable_summary = {}

    for layer in wiring_layers:
        connections_raw  = layer.get("connections", [])
        layer_cable_type = layer.get("cable_type",  "")
        connections      = expand_wiring_clusters(connections_raw, layer_cable_type)

        for conn in connections:
            from_dev  = conn["from"]
            to_dev    = conn["to"]
            from_info = all_devices.get(from_dev)
            to_info   = all_devices.get(to_dev)

            if not from_info or not to_info:
                continue

            cable_data = calculate_cable_length(from_dev, to_dev, all_devices, racks_config, config)
            if not cable_data:
                continue

            cable_type = conn.get("cable_type", "") or layer_cable_type
            if cable_type.lower() == "included":
                continue

            cable_color = conn.get("edge_color", layer.get("edge_color", "323232"))
            color_name, _ = hex_to_color_name(cable_color)

            cable_length = cable_data["total_length"]
            cable_key    = (cable_type, color_name)
            cable_summary.setdefault(cable_key, {})
            cable_summary[cable_key][cable_length] = cable_summary[cable_key].get(cable_length, 0) + 1

    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "Cable Type",
            "Color",
            "Length (m)",
            "Quantity",
            "Total Length (m)",
        ])

        for cable_type, color_name in sorted(cable_summary.keys()):
            for length in sorted(cable_summary[(cable_type, color_name)].keys()):
                quantity     = cable_summary[(cable_type, color_name)][length]
                total_length = length * quantity
                writer.writerow([
                    cable_type,
                    color_name,
                    f"{length:.1f}",
                    quantity,
                    f"{total_length:.1f}",
                ])

    print(f"Generated cable summary CSV: {output_file}")
    return cable_summary


# -------------------------------------------------
# Generate cable summary HTML
# -------------------------------------------------
def generate_cable_summary_html(all_devices, racks_config, wiring_layers, config, output_file="output/cable_summary.html"):
    """Generate an HTML page with cable summary for ordering, grouped by cable type and color"""

    # {(cable_type, color_name, color_hex): {length: quantity}}
    cable_summary = {}

    for layer in wiring_layers:
        connections_raw  = layer.get("connections", [])
        layer_cable_type = layer.get("cable_type",  "")
        connections      = expand_wiring_clusters(connections_raw, layer_cable_type)

        for conn in connections:
            from_dev  = conn["from"]
            to_dev    = conn["to"]
            from_info = all_devices.get(from_dev)
            to_info   = all_devices.get(to_dev)

            if not from_info or not to_info:
                continue

            cable_data = calculate_cable_length(from_dev, to_dev, all_devices, racks_config, config)
            if not cable_data:
                continue

            cable_type = conn.get("cable_type", "") or layer_cable_type
            if cable_type.lower() == "included":
                continue

            cable_color = conn.get("edge_color", layer.get("edge_color", "#323232"))
            color_name, _ = hex_to_color_name(cable_color)

            cable_length = cable_data["total_length"]
            cable_key    = (cable_type, color_name, cable_color)
            cable_summary.setdefault(cable_key, {})
            cable_summary[cable_key][cable_length] = cable_summary[cable_key].get(cable_length, 0) + 1

    # ------------------------------------------------------------------
    # Build HTML
    # ------------------------------------------------------------------
    html = """<!DOCTYPE html>
<html>
<head>
    <title>Cable Ordering Summary</title>
    <style>
        body {
            font-family: 'Sinkin Sans', Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        h1 {
            color: #333;
            border-bottom: 3px solid #5af282;
            padding-bottom: 10px;
        }
        h2 {
            color: #555;
            margin-top: 30px;
            font-size: 18px;
        }
        .summary-card {
            background-color: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .cable-type-section {
            margin-bottom: 30px;
        }
        .cable-type-header {
            font-size: 18px;
            font-weight: bold;
            color: white;
            background-color: #5af282;
            padding: 12px 15px;
            border-radius: 4px 4px 0 0;
            margin-bottom: 0;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            background-color: white;
        }
        table th {
            background-color: #f0f0f0;
            color: #333;
            padding: 12px;
            text-align: left;
            font-weight: bold;
            border-bottom: 2px solid #ddd;
        }
        table td {
            padding: 10px 12px;
            border-bottom: 1px solid #ddd;
        }
        table tr:hover {
            background-color: #f9f9f9;
        }
        .metric {
            text-align: right;
            font-family: monospace;
            font-weight: bold;
        }
        .subtotal-row {
            background-color: #e8f5e9;
            font-weight: bold;
        }
        .subtotal-row .metric {
            color: #2e7d32;
        }
        .total-row {
            background-color: #4297a1;
            color: white;
            font-weight: bold;
        }
        .total-row .metric {
            color: white;
        }
        .notes {
            background-color: #e8f5e9;
            padding: 15px;
            border-radius: 4px;
            margin-top: 20px;
            border-left: 4px solid #5af282;
        }
        .notes p {
            margin: 5px 0;
            color: #333;
        }
        .notes strong {
            color: #2e7d32;
        }
    </style>
</head>
<body>
    <h1>Cable Ordering Summary</h1>
    <p>Cables grouped by type and length (rounded to nearest 0.5m)</p>
"""

    total_quantity_all = 0
    total_length_all   = 0

    # Group by cable type
    cable_by_type = {}
    for (cable_type, color_name, color_hex), lengths in cable_summary.items():
        cable_by_type.setdefault(cable_type, {})
        cable_by_type[cable_type][(color_name, color_hex)] = lengths

    for cable_type in sorted(cable_by_type.keys()):
        colors              = cable_by_type[cable_type]
        type_total_quantity = 0
        type_total_length   = 0

        html += f"""    <div class="summary-card cable-type-section">
        <div class="cable-type-header">{cable_type}</div>
"""

        for (color_name, color_hex) in sorted(colors.keys()):
            lengths = colors[(color_name, color_hex)]

            try:
                r          = int(color_hex[1:3], 16)
                g          = int(color_hex[3:5], 16)
                b          = int(color_hex[5:7], 16)
                brightness = (r * 299 + g * 587 + b * 114) / 1000
                text_color = "#FFFFFF" if brightness < 128 else "#000000"
            except Exception:
                text_color = "#000000"

            html += f"""        <div style="margin-top: 15px; padding: 10px; background-color: #f5f5f5; border-left: 4px solid {color_hex};">
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
                <div style="width: 30px; height: 30px; background-color: {color_hex}; border: 2px solid #333; border-radius: 4px;"></div>
                <strong style="font-size: 16px;">{color_name}</strong>
                <span style="color: #666; font-size: 12px;">({color_hex})</span>
            </div>
            <table style="margin-top: 10px; width: 100%;">
                <thead>
                    <tr style="background-color: #e8f5e9;">
                        <th style="padding: 8px; text-align: left;">Length (m)</th>
                        <th style="padding: 8px; text-align: right; font-family: monospace;">Quantity</th>
                        <th style="padding: 8px; text-align: right; font-family: monospace;">Total (m)</th>
                    </tr>
                </thead>
                <tbody>
"""

            color_quantity = 0
            color_length   = 0

            for length in sorted(lengths.keys()):
                quantity     = lengths[length]
                total_length = length * quantity
                color_quantity      += quantity
                color_length        += total_length
                type_total_quantity += quantity
                type_total_length   += total_length
                total_quantity_all  += quantity
                total_length_all    += total_length

                html += f"""                    <tr>
                        <td style="padding: 8px;">{length:.1f}</td>
                        <td style="padding: 8px; text-align: right; font-family: monospace; font-weight: bold;">{quantity}</td>
                        <td style="padding: 8px; text-align: right; font-family: monospace; font-weight: bold;">{total_length:.1f}</td>
                    </tr>
"""

            html += f"""                    <tr style="background-color: #e0f2f1; font-weight: bold;">
                        <td style="padding: 8px;">{color_name} Subtotal</td>
                        <td style="padding: 8px; text-align: right; font-family: monospace;">{color_quantity}</td>
                        <td style="padding: 8px; text-align: right; font-family: monospace;">{color_length:.1f}</td>
                    </tr>
                </tbody>
            </table>
        </div>
"""

        html += f"""        <div style="margin-top: 10px; padding: 10px; background-color: #c8e6c9; font-weight: bold;">
            {cable_type} Total: {type_total_quantity} cables, {type_total_length:.1f}m
        </div>
    </div>
"""

    html += f"""    <div class="summary-card">
        <table>
            <thead>
                <tr>
                    <th>Overall Summary</th>
                    <th class="metric">Total Quantity</th>
                    <th class="metric">Total Length (m)</th>
                </tr>
            </thead>
            <tbody>
                <tr class="total-row">
                    <td>GRAND TOTAL</td>
                    <td class="metric">{total_quantity_all}</td>
                    <td class="metric">{total_length_all:.1f}</td>
                </tr>
            </tbody>
        </table>
    </div>

    <div class="summary-card notes">
        <h3>Notes for Ordering</h3>
        <p><strong>Cable Lengths:</strong> All lengths are rounded up to the nearest 0.5m increment to match common spool options (1.0m, 1.5m, 2.0m, etc.).</p>
        <p><strong>External Devices:</strong> Connections to/from external device groups include the group's <em>distance_from_racks</em> value. Verify this distance on-site before finalising orders.</p>
        <p><strong>Ordering Tips:</strong> Use these quantities and lengths to request quotes from cable suppliers. Check with vendors for available spool sizes and bulk discounts.</p>
        <p><strong>Extra Stock:</strong> Consider ordering 10–15% extra for contingencies, future growth, and test purposes.</p>
        <p><strong>Cable Management:</strong> Plan cable routing and pathways before ordering. Ensure cable runs are protected and labelled during installation.</p>
    </div>
</body>
</html>
"""

    with open(output_file, 'w') as f:
        f.write(html)

    print(f"Generated cable summary HTML: {output_file}")