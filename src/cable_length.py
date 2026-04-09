import csv
import math
import re
from clusters import expand_wiring_clusters
from utils import hex_to_color_name


# -------------------------------------------------
# Helper geometry functions
# -------------------------------------------------
def _u_dist_to_rack_bottom(start_u, units, u_order='bottom_top', total_u=42):
    """U count from physical bottom edge of device to physical rack bottom."""
    if start_u is None or units is None:
        return 0
    if u_order == 'bottom_top':
        # U1 = physical rack bottom; device bottom edge = start_u - units + 1
        return max(0, (start_u - units + 1) - 1)
    else:
        # top_bottom: U1 = physical rack top; device bottom edge = start_u + units - 1
        return max(0, total_u - (start_u + units - 1))

def _intra_rack_u_delta(from_start_u, from_units, to_start_u, to_units, u_order='bottom_top'):
    """U delta between physical bottom edges of two devices in the same rack."""
    if from_start_u is None or from_units is None or to_start_u is None or to_units is None:
        return 0
    if u_order == 'bottom_top':
        a_bot = from_start_u - from_units + 1
        b_bot = to_start_u - to_units + 1
    else:
        a_bot = from_start_u + from_units - 1
        b_bot = to_start_u + to_units - 1
    return abs(a_bot - b_bot)

def _round_cable_length(length):
    """Round up to nearest 0.2 m for lengths ≤ 1.0 m, then nearest 0.5 m."""
    if length <= 1.0:
        return math.ceil(length * 5) / 5
    return math.ceil(length * 2) / 2

def _stepped_slack(raw_total, slack_max):
    """Step-based slack: scales from 0 to slack_max based on raw cable length."""
    if raw_total < 1.0:
        return 0.0
    elif raw_total < 3.0:
        return slack_max * 0.25
    elif raw_total < 10.0:
        return slack_max * 0.5
    else:
        return slack_max


# -------------------------------------------------
# Build all_devices lookup from parsed YAML config
# -------------------------------------------------
def build_all_devices(rack_configs, external_device_groups=None):
    """
    Build the all_devices dict consumed by calculate_cable_length.

    Each entry:
        {
            "rack_id":             str,    # rack id string, or "external"
            "side":                str,    # "front" | "rear" | "external"
            "start_u":             int,    # top U position (None for undefined / external)
            "units":               int,    # height in U (1 for external)
            "distance_from_racks": float,  # metres; 0 for rack devices
        }
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

                on_rails      = bool(dev.get("on_rails", False))
                is_patch_panel = "patch panel" in (dev.get("type") or "").lower()
                if start_n is not None and end_n is not None and "{N}" in name:
                    step = units + (spacing or 0)
                    for i, n in enumerate(range(start_n, end_n + 1)):
                        resolved_name  = name.replace("{N}", str(n))
                        member_start_u = (start_u - i * step) if start_u else None
                        all_devices[resolved_name] = {
                            "rack_id":             rack_id,
                            "side":                side,
                            "start_u":             member_start_u,
                            "units":               units,
                            "distance_from_racks": 0,
                            "on_rails":            on_rails,
                            "is_patch_panel":      is_patch_panel,
                            "cable_exit":          dev.get("cable_exit", "rear"),
                            "u_order":             rack_config["rack"].get("u_order", "bottom_top"),
                            "total_u":             int(rack_config["rack"].get("total_u", 42)),
                        }
                else:
                    all_devices[name] = {
                        "rack_id":             rack_id,
                        "side":                side,
                        "start_u":             start_u,
                        "units":               units,
                        "distance_from_racks": 0,
                        "on_rails":            on_rails,
                        "is_patch_panel":      is_patch_panel,
                        "cable_exit":          dev.get("cable_exit", "rear"),
                        "u_order":             rack_config["rack"].get("u_order", "bottom_top"),
                        "total_u":             int(rack_config["rack"].get("total_u", 42)),
                    }

    # --- External devices ---
    for group in (external_device_groups or []):
        dist       = float(group.get("distance_from_racks", 0) or 0)
        group_name = group.get("name", "External Devices")
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
                        "group_name":          group_name,
                    }
            else:
                all_devices[name] = {
                    "rack_id":             "external",
                    "side":                "external",
                    "start_u":             None,
                    "units":               1,
                    "distance_from_racks": dist,
                    "group_name":          group_name,
                }

    return all_devices


# -------------------------------------------------
# Cable length calculation (single point-to-point)
# -------------------------------------------------
def calculate_cable_length(from_device, to_device, all_devices, rack_configs, config):
    """
    Calculate minimum cable length for a single point-to-point segment.
    This function is the core calculator — it knows nothing about patch panels.
    Patch routing is handled by calculate_cable_length_for_conn().

    Formula:
        unit_length + f2b_length + inter_rack_length + external_length + cable_slack
        rounded up to nearest 0.5 m.
    """
    from_info = all_devices.get(from_device)
    to_info   = all_devices.get(to_device)

    if not from_info or not to_info:
        return None

    cable_slack_max     = config.get("cable_slack_length",  0.2)
    standard_u_height   = config.get("standard_u_height",   0.045)
    front_to_back       = config.get("front_to_back_length", 0.5)
    inter_rack_distance = config.get("inter_rack_distance",  2.5)
    rail_extension      = config.get("rail_extension_length", 0.5)

    rack_name_map     = {}
    rack_position_map = {}
    for pos, rack_config in enumerate(rack_configs):
        rack_id   = rack_config["rack"].get("id",   "rack")
        rack_name = rack_config["rack"].get("name",  rack_id)
        rack_name_map[rack_id]     = rack_name
        rack_position_map[rack_id] = pos

    from_rack    = from_info.get("rack_id")
    to_rack      = to_info.get("rack_id")
    from_start_u = from_info.get("start_u")
    to_start_u   = to_info.get("start_u")
    from_units   = from_info.get("units",   1)
    to_units     = to_info.get("units",     1)

    from_is_ext = (from_rack == "external")
    to_is_ext   = (to_rack   == "external")

    from_rack_name = from_info.get("group_name", "External") if from_is_ext else rack_name_map.get(from_rack, from_rack)
    to_rack_name   = to_info.get("group_name",   "External") if to_is_ext   else rack_name_map.get(to_rack,   to_rack)

    from_cable_exit = from_info.get("cable_exit", "rear")
    to_cable_exit   = to_info.get("cable_exit",   "rear")

    # Patch panels accept cables on either face — adopt the peer's cable exit
    from_is_pp = from_info.get("is_patch_panel", False)
    to_is_pp   = to_info.get("is_patch_panel",   False)
    if from_is_pp and not to_is_pp:
        from_cable_exit = to_cable_exit
    elif to_is_pp and not from_is_pp:
        to_cable_exit = from_cable_exit

    from_u_order    = from_info.get("u_order",    "bottom_top")
    to_u_order      = to_info.get("u_order",      "bottom_top")
    from_total_u    = from_info.get("total_u",    42)
    to_total_u      = to_info.get("total_u",      42)
    from_rails      = from_info.get("on_rails",   False)
    to_rails        = to_info.get("on_rails",     False)

    # --- Route calculation ---
    if not from_is_ext and not to_is_ext and from_rack == to_rack:
        # INTRA-RACK
        if from_cable_exit == to_cable_exit:
            unit_delta = _intra_rack_u_delta(from_start_u, from_units, to_start_u, to_units, from_u_order)
            f2b_length = 0.0
        else:
            # Different exits: direct U delta between devices + one f2b crossing
            unit_delta = _intra_rack_u_delta(from_start_u, from_units, to_start_u, to_units, from_u_order)
            f2b_length = front_to_back
        unit_length       = unit_delta * standard_u_height
        inter_rack_length = 0.0
        external_length   = 0.0

    elif not from_is_ext and not to_is_ext:
        # INTER-RACK
        from_to_bot = _u_dist_to_rack_bottom(from_start_u, from_units, from_u_order, from_total_u)
        to_to_bot   = _u_dist_to_rack_bottom(to_start_u,   to_units,   to_u_order,   to_total_u)
        unit_delta  = from_to_bot + to_to_bot
        unit_length = unit_delta * standard_u_height

        f2b_length = 0.0
        if from_cable_exit == 'front': f2b_length += front_to_back
        if to_cable_exit   == 'front': f2b_length += front_to_back

        from_pos          = rack_position_map.get(from_rack, 0)
        to_pos            = rack_position_map.get(to_rack,   0)
        inter_rack_length = abs(from_pos - to_pos) * inter_rack_distance
        external_length   = 0.0

    elif from_is_ext and not to_is_ext:
        # FROM external, TO rack
        to_to_bot   = _u_dist_to_rack_bottom(to_start_u, to_units, to_u_order, to_total_u)
        unit_delta  = to_to_bot
        unit_length = unit_delta * standard_u_height
        f2b_length  = front_to_back if to_cable_exit == 'front' else 0.0
        inter_rack_length = 0.0
        external_length   = from_info.get("distance_from_racks", 0) or 0

    elif not from_is_ext and to_is_ext:
        # FROM rack, TO external
        from_to_bot = _u_dist_to_rack_bottom(from_start_u, from_units, from_u_order, from_total_u)
        unit_delta  = from_to_bot
        unit_length = unit_delta * standard_u_height
        f2b_length  = front_to_back if from_cable_exit == 'front' else 0.0
        inter_rack_length = 0.0
        external_length   = to_info.get("distance_from_racks", 0) or 0

    else:
        # BOTH external
        unit_delta        = 0
        unit_length       = 0.0
        f2b_length        = 0.0
        inter_rack_length = 0.0
        if from_info.get("group_name") == to_info.get("group_name"):
            external_length = 0.0
        else:
            external_length = (
                (from_info.get("distance_from_racks", 0) or 0)
                + (to_info.get("distance_from_racks", 0) or 0)
                + inter_rack_distance
            )

    # Rail extension
    rail_length = 0.0
    if not from_is_ext and from_rails: rail_length += rail_extension
    if not to_is_ext   and to_rails:   rail_length += rail_extension

    # Slack (stepped) + total
    raw_total   = unit_length + f2b_length + inter_rack_length + external_length + rail_length
    # Both-external same-group: zero slack
    if from_is_ext and to_is_ext and from_info.get("group_name") == to_info.get("group_name"):
        cable_slack = 0.0
    else:
        cable_slack = _stepped_slack(raw_total, cable_slack_max)
    total_length = _round_cable_length(raw_total + cable_slack)

    return {
        "from_rack":         from_rack_name,
        "to_rack":           to_rack_name,
        "unit_delta":        unit_delta,
        "unit_length":       unit_length,
        "f2b_length":        f2b_length,
        "inter_rack_length": inter_rack_length,
        "external_length":   external_length,
        "rail_length":       rail_length,
        "cable_slack":       cable_slack,
        "total_length":      total_length,
    }


# -------------------------------------------------
# Per-connection segment resolver (patch-aware)
# -------------------------------------------------
def calculate_cable_length_for_conn(conn, all_devices, rack_configs, config):
    """
    Return a list of cable segment dicts for a single connection.

    A non-patched connection produces one segment.
    A patched connection produces 2 or 3 segments — one per physical cable:

        via_patch_from only:   [from -> pp_from,  pp_from -> to]
        via_patch_to   only:   [from -> pp_to,    pp_to   -> to]
        both:                  [from -> pp_from,  pp_from -> pp_to,  pp_to -> to]

    Each segment dict is the result of calculate_cable_length() extended with:
        "from_dev"   : str   — source device name
        "to_dev"     : str   — destination device name
        "seg_label"  : str   — e.g. "1/3" for first of three segments
        "route"      : str   — full route string, same on every segment of a conn
        "is_patched" : bool  — True if this connection uses patch panels
        "cable_type" : str   — from the connection dict
    """
    from_dev   = conn["from"]
    to_dev     = conn["to"]
    pp_from    = conn.get("via_patch_from", "")
    pp_to      = conn.get("via_patch_to",   "")
    cable_type = conn.get("cable_type", "")

    # Build the ordered list of device name pairs for each physical cable
    if pp_from and pp_to:
        segments    = [(from_dev, pp_from), (pp_from, pp_to), (pp_to, to_dev)]
        route       = f"{from_dev} -> {pp_from} -> {pp_to} -> {to_dev}"
        is_patched  = True
    elif pp_from:
        segments    = [(from_dev, pp_from), (pp_from, to_dev)]
        route       = f"{from_dev} -> {pp_from} -> {to_dev}"
        is_patched  = True
    elif pp_to:
        segments    = [(from_dev, pp_to), (pp_to, to_dev)]
        route       = f"{from_dev} -> {pp_to} -> {to_dev}"
        is_patched  = True
    else:
        segments    = [(from_dev, to_dev)]
        route       = f"{from_dev} -> {to_dev}"
        is_patched  = False

    total_segs = len(segments)
    results    = []

    for i, (seg_from, seg_to) in enumerate(segments):
        data = calculate_cable_length(seg_from, seg_to, all_devices, rack_configs, config)
        if data is None:
            # Device not found — emit a placeholder so the row still appears
            data = {
                "from_rack":         "?",
                "to_rack":           "?",
                "unit_delta":        0,
                "unit_length":       0,
                "f2b_length":        0,
                "inter_rack_length": 0,
                "external_length":   0,
                "rail_length":       0,
                "cable_slack":       config.get("cable_slack_length", 0.2),
                "total_length":      0,
            }
        data["from_dev"]   = seg_from
        data["to_dev"]     = seg_to
        data["seg_label"]  = f"{i + 1}/{total_segs}" if total_segs > 1 else ""
        data["route"]      = route
        data["is_patched"] = is_patched
        data["cable_type"] = cable_type
        results.append(data)

    return results


# -------------------------------------------------
# Generate cable length HTML table
# -------------------------------------------------
def generate_cable_length_html(all_devices, racks_config, wiring_layers, config, output_file="output/cable_lengths.html"):
    """Generate an HTML table with cable length calculations, patch-panel-aware."""

    html = """\
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Cable Length Calculations</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: Arial, sans-serif;
            font-size: 13px;
            background: #f0f2f5;
            color: #222;
            padding: 24px;
        }
        h1 { font-size: 22px; font-weight: 700; margin-bottom: 6px; }
        .subtitle {
            color: #666; font-size: 12px; margin-bottom: 20px;
        }
        .card {
            background: #fff;
            border-radius: 8px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.12);
            overflow: hidden;
            margin-bottom: 28px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        thead tr {
            background: #2d7d46;
            color: #fff;
        }
        thead th {
            padding: 10px 12px;
            text-align: left;
            font-weight: 600;
            font-size: 12px;
            white-space: nowrap;
            border-right: 1px solid rgba(255,255,255,0.15);
        }
        thead th:last-child { border-right: none; }
        thead th.num { text-align: right; }

        tbody tr { border-bottom: 1px solid #e8eaed; }
        tbody tr:last-child { border-bottom: none; }
        tbody tr:hover td:not(.min-len) { background: #f7f9fc !important; }

        td {
            padding: 8px 12px;
            vertical-align: middle;
            font-size: 12px;
        }
        td.num {
            text-align: right;
            font-family: 'Courier New', monospace;
            font-size: 12px;
        }
        td.network { font-weight: 600; }
        td.seg-badge {
            text-align: center;
            font-family: monospace;
            font-size: 11px;
            color: #555;
        }

        /* Min Length column — always teal, always readable */
        td.min-len {
            text-align: right;
            font-family: 'Courier New', monospace;
            font-weight: 700;
            font-size: 13px;
            background: #1a7f5a !important;
            color: #fff !important;
            padding: 8px 14px;
        }
        thead th.min-len {
            background: #145f43;
            text-align: right;
        }

        /* Plain rows */
        tbody tr.plain td { background: #fff; }
        tbody tr.ext td   { background: #fffbf0; }

        /* Patch group — subtle blue tint, left border accent */
        tbody tr.patch-first td {
            background: #f0f5ff;
            border-top: 2px solid #4a7fcb;
        }
        tbody tr.patch-first td.min-len {
            border-top: 2px solid #4a7fcb;
        }
        tbody tr.patch-mid td {
            background: #f0f5ff;
            border-bottom: none;
            border-top: none;
        }
        tbody tr.patch-last td {
            background: #f0f5ff;
            border-bottom: 2px solid #4a7fcb;
        }
        tbody tr.patch-last td.min-len {
            border-bottom: 2px solid #4a7fcb;
        }
        /* Left accent bar on patch rows */
        tbody tr.patch-first td:first-child,
        tbody tr.patch-mid   td:first-child,
        tbody tr.patch-last  td:first-child {
            border-left: 4px solid #4a7fcb;
        }

        /* Route shown inline as small secondary text */
        .route-hint {
            display: block;
            font-size: 10px;
            color: #888;
            margin-top: 2px;
            font-style: italic;
        }

        /* Inline CSS tooltip for breakdown */
        .tip-wrap {
            position: relative;
            cursor: help;
        }
        .tip {
            display: none;
            position: absolute;
            right: 0;
            bottom: 100%;
            margin-bottom: 6px;
            z-index: 100;
            background: #1a1a2e;
            color: #fff;
            font-size: 11px;
            font-family: 'Courier New', monospace;
            font-weight: normal;
            padding: 8px 10px;
            border-radius: 5px;
            white-space: nowrap;
            box-shadow: 0 4px 12px rgba(0,0,0,0.35);
            line-height: 1.7;
            pointer-events: none;
            min-width: 200px;
            text-align: left;
        }
        .tip::before {
            content: '';
            position: absolute;
            bottom: -5px;
            right: 14px;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid #1a1a2e;
        }
        .tip-wrap:hover .tip { display: block; }

        /* Flip tooltip below when it would clip off the top */
        .tip.below {
            bottom: auto;
            top: 100%;
            margin-bottom: 0;
            margin-top: 6px;
        }
        .tip.below::before {
            bottom: auto;
            top: -5px;
            border-top: none;
            border-bottom: 5px solid #1a1a2e;
        }
    </style>
</head>
<body>
    <h1>Cable Length Calculations</h1>
    <p class="subtitle">
        Patched connections are shown as individual cable segments.
        Hover over <strong>Min Length</strong> to see the full breakdown.
        Segment labels (e.g. <code>2/3</code>) show position in the patched route.
    </p>
    <div class="card">
    <table>
        <thead>
            <tr>
                <th>Network</th>
                <th>From</th>
                <th>To</th>
                <th style="text-align:center">Seg</th>
                <th>Cable Type</th>
                <th>From Rack</th>
                <th>To Rack</th>
                <th class="min-len">Min Length (m)</th>
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
            if not all_devices.get(conn["from"]) or not all_devices.get(conn["to"]):
                continue

            segments  = calculate_cable_length_for_conn(conn, all_devices, racks_config, config)
            n_segs    = len(segments)

            for si, seg in enumerate(segments):
                is_ext = (
                    all_devices.get(seg["from_dev"], {}).get("rack_id") == "external"
                    or all_devices.get(seg["to_dev"],   {}).get("rack_id") == "external"
                )

                # Row class
                if not seg["is_patched"]:
                    row_cls = "ext" if is_ext else "plain"
                elif n_segs == 1:
                    row_cls = "plain"
                elif si == 0:
                    row_cls = "patch-first"
                elif si == n_segs - 1:
                    row_cls = "patch-last"
                else:
                    row_cls = "patch-mid"

                # Breakdown tooltip on Min Length cell
                breakdown = (
                    f"U distance: {seg['unit_delta']} units = {seg['unit_length']:.3f} m\n"
                    f"Front-to-back: {seg['f2b_length']:.3f} m\n"
                    f"Inter-rack: {seg['inter_rack_length']:.1f} m\n"
                    f"External: {seg['external_length']:.1f} m\n"
                    f"Rail extension: {seg['rail_length']:.3f} m\n"
                    f"Slack: {seg['cable_slack']:.3f} m\n"
                    f"Total: {seg['total_length']:.2f} m"
                )
                if seg["is_patched"]:
                    breakdown = f"Route: {seg['route']}\n\n" + breakdown

                # Route hint shown as secondary line under From device on first seg
                route_hint = ""
                if seg["is_patched"] and si == 0:
                    route_hint = f'<span class="route-hint">{seg["route"]}</span>'

                seg_badge = f'<td class="seg-badge">{seg["seg_label"]}</td>' if seg["seg_label"] else '<td class="seg-badge" style="color:#ccc">—</td>'

                html += f'        <tr class="{row_cls}">\n'
                html += f'            <td class="network">{layer_name}</td>\n'
                html += f'            <td>{seg["from_dev"]}{route_hint}</td>\n'
                html += f'            <td>{seg["to_dev"]}</td>\n'
                html += f'            {seg_badge}\n'
                html += f'            <td>{seg["cable_type"]}</td>\n'
                html += f'            <td>{seg["from_rack"]}</td>\n'
                html += f'            <td>{seg["to_rack"]}</td>\n'
                breakdown_html = breakdown.replace("\n", "<br>").replace('"', '&quot;')
                html += f'            <td class="min-len"><span class="tip-wrap">{seg["total_length"]:.2f}<span class="tip">{breakdown_html}</span></span></td>\n'
                html += f'        </tr>\n'

    html += """\
        </tbody>
    </table>
    </div>
    <script>
        document.querySelectorAll('.tip-wrap').forEach(function(wrap) {
            wrap.addEventListener('mouseenter', function() {
                var tip = wrap.querySelector('.tip');
                if (!tip) return;
                tip.classList.remove('below');
                var rect = tip.getBoundingClientRect();
                if (rect.top < 8) {
                    tip.classList.add('below');
                }
            });
        });
    </script>
</body>
</html>
"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Generated cable length HTML: {output_file}")


def generate_cable_length_table(all_devices, racks_config, wiring_layers, config, output_file="output/cable_lengths.csv"):
    """Generate a CSV table with cable length calculations, patch-panel-aware."""

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            "Network", "From", "To", "Seg", "Route",
            "Cable Type", "From Rack", "To Rack",
            "U Distance (units)", "Unit Length (m)", "F2B Length (m)",
            "Inter-rack Length (m)", "External Length (m)",
            "Cable Slack (m)", "Min Cable Length (m)",
        ])

        for layer in wiring_layers:
            layer_name       = layer["name"]
            connections_raw  = layer.get("connections", [])
            layer_cable_type = layer.get("cable_type",  "")
            connections      = expand_wiring_clusters(connections_raw, layer_cable_type)

            for conn in connections:
                if not all_devices.get(conn["from"]) or not all_devices.get(conn["to"]):
                    continue

                segments = calculate_cable_length_for_conn(conn, all_devices, racks_config, config)

                for seg in segments:
                    writer.writerow([
                        layer_name,
                        seg["from_dev"],
                        seg["to_dev"],
                        seg["seg_label"],
                        seg["route"] if seg["is_patched"] else "",
                        seg["cable_type"],
                        seg["from_rack"],
                        seg["to_rack"],
                        seg["unit_delta"],
                        f"{seg['unit_length']:.3f}",
                        f"{seg['f2b_length']:.3f}",
                        f"{seg['inter_rack_length']:.1f}",
                        f"{seg['external_length']:.1f}",
                        f"{seg['cable_slack']:.3f}",
                        f"{seg['total_length']:.2f}",
                    ])

    print(f"Generated cable length table: {output_file}")


# -------------------------------------------------
# Generate cable summary (for ordering) — CSV
# -------------------------------------------------
def generate_cable_summary_csv(all_devices, racks_config, wiring_layers, config, output_file="output/cable_summary.csv"):
    """
    Generate a summary of cables needed for ordering.
    Each patch segment counts as a separate physical cable.
    """
    cable_summary = {}

    for layer in wiring_layers:
        connections_raw  = layer.get("connections", [])
        layer_cable_type = layer.get("cable_type",  "")
        connections      = expand_wiring_clusters(connections_raw, layer_cable_type)

        for conn in connections:
            if not all_devices.get(conn["from"]) or not all_devices.get(conn["to"]):
                continue

            segments    = calculate_cable_length_for_conn(conn, all_devices, racks_config, config)
            cable_color = conn.get("edge_color", layer.get("edge_color", "323232"))
            color_name, _ = hex_to_color_name(cable_color)

            for seg in segments:
                cable_type = seg["cable_type"] or layer_cable_type
                if cable_type.lower() == "included":
                    continue
                cable_key = (cable_type, color_name)
                cable_summary.setdefault(cable_key, {})
                length = seg["total_length"]
                cable_summary[cable_key][length] = cable_summary[cable_key].get(length, 0) + 1

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Cable Type", "Color", "Length (m)", "Quantity", "Total Length (m)"])
        for cable_type, color_name in sorted(cable_summary.keys()):
            for length in sorted(cable_summary[(cable_type, color_name)].keys()):
                quantity     = cable_summary[(cable_type, color_name)][length]
                total_length = length * quantity
                writer.writerow([cable_type, color_name, f"{length:.1f}", quantity, f"{total_length:.1f}"])

    print(f"Generated cable summary CSV: {output_file}")
    return cable_summary


# -------------------------------------------------
# Generate cable summary HTML
# -------------------------------------------------
def generate_cable_summary_html(all_devices, racks_config, wiring_layers, config, output_file="output/cable_summary.html"):
    """Generate an HTML cable ordering summary. Each patch segment = one physical cable."""

    cable_summary = {}

    for layer in wiring_layers:
        connections_raw  = layer.get("connections", [])
        layer_cable_type = layer.get("cable_type",  "")
        connections      = expand_wiring_clusters(connections_raw, layer_cable_type)

        for conn in connections:
            if not all_devices.get(conn["from"]) or not all_devices.get(conn["to"]):
                continue

            segments    = calculate_cable_length_for_conn(conn, all_devices, racks_config, config)
            cable_color = conn.get("edge_color", layer.get("edge_color", "#323232"))
            color_name, _ = hex_to_color_name(cable_color)

            for seg in segments:
                cable_type = seg["cable_type"] or layer_cable_type
                if cable_type.lower() == "included":
                    continue
                cable_key = (cable_type, color_name, cable_color)
                cable_summary.setdefault(cable_key, {})
                length = seg["total_length"]
                cable_summary[cable_key][length] = cable_summary[cable_key].get(length, 0) + 1

    # HTML identical to original except file write uses utf-8
    html = """<!DOCTYPE html>
<html>
<head>
    <title>Cable Ordering Summary</title>
    <style>
        body { font-family: 'Sinkin Sans', Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
        h1 { color: #333; border-bottom: 3px solid #5af282; padding-bottom: 10px; }
        h2 { color: #555; margin-top: 30px; font-size: 18px; }
        .summary-card { background-color: white; border-radius: 8px; padding: 20px;
                        margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .cable-type-section { margin-bottom: 30px; }
        .cable-type-header { font-size: 18px; font-weight: bold; color: white;
                             background-color: #5af282; padding: 12px 15px;
                             border-radius: 4px 4px 0 0; margin-bottom: 0; }
        table { width: 100%; border-collapse: collapse; background-color: white; }
        table th { background-color: #f0f0f0; color: #333; padding: 12px; text-align: left;
                   font-weight: bold; border-bottom: 2px solid #ddd; }
        table td { padding: 10px 12px; border-bottom: 1px solid #ddd; }
        table tr:hover { background-color: #f9f9f9; }
        .metric { text-align: right; font-family: monospace; font-weight: bold; }
        .total-row { background-color: #4297a1; color: white; font-weight: bold; }
        .total-row .metric { color: white; }
        .notes { background-color: #e8f5e9; padding: 15px; border-radius: 4px;
                 margin-top: 20px; border-left: 4px solid #5af282; }
        .notes p { margin: 5px 0; color: #333; }
        .notes strong { color: #2e7d32; }
    </style>
</head>
<body>
    <h1>Cable Ordering Summary</h1>
    <p>Cables grouped by type and length (rounded to nearest 0.5m).
       Patch panel connections count as separate cables per segment.</p>
"""

    total_quantity_all = 0
    total_length_all   = 0

    cable_by_type = {}
    for (cable_type, color_name, color_hex), lengths in cable_summary.items():
        cable_by_type.setdefault(cable_type, {})
        cable_by_type[cable_type][(color_name, color_hex)] = lengths

    for cable_type in sorted(cable_by_type.keys()):
        colors              = cable_by_type[cable_type]
        type_total_quantity = 0
        type_total_length   = 0

        html += f'    <div class="summary-card cable-type-section">\n'
        html += f'        <div class="cable-type-header">{cable_type}</div>\n'

        for (color_name, color_hex) in sorted(colors.keys()):
            lengths = colors[(color_name, color_hex)]
            try:
                r = int(color_hex[1:3], 16); g = int(color_hex[3:5], 16); b = int(color_hex[5:7], 16)
                text_color = "#FFFFFF" if (r*299 + g*587 + b*114)/1000 < 128 else "#000000"
            except Exception:
                text_color = "#000000"

            html += f'        <div style="margin-top:15px;padding:10px;background-color:#f5f5f5;border-left:4px solid {color_hex};">\n'
            html += f'            <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">\n'
            html += f'                <div style="width:30px;height:30px;background-color:{color_hex};border:2px solid #333;border-radius:4px;"></div>\n'
            html += f'                <strong style="font-size:16px;">{color_name}</strong>\n'
            html += f'                <span style="color:#666;font-size:12px;">({color_hex})</span>\n'
            html += f'            </div>\n'
            html += f'            <table style="margin-top:10px;width:100%;">\n'
            html += f'                <thead><tr style="background-color:#e8f5e9;">\n'
            html += f'                    <th style="padding:8px;text-align:left;">Length (m)</th>\n'
            html += f'                    <th style="padding:8px;text-align:right;font-family:monospace;">Quantity</th>\n'
            html += f'                    <th style="padding:8px;text-align:right;font-family:monospace;">Total (m)</th>\n'
            html += f'                </tr></thead><tbody>\n'

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
                html += f'                    <tr><td style="padding:8px;">{length:.1f}</td>'
                html += f'<td style="padding:8px;text-align:right;font-family:monospace;font-weight:bold;">{quantity}</td>'
                html += f'<td style="padding:8px;text-align:right;font-family:monospace;font-weight:bold;">{total_length:.1f}</td></tr>\n'

            html += f'                    <tr style="background-color:#e0f2f1;font-weight:bold;">'
            html += f'<td style="padding:8px;">{color_name} Subtotal</td>'
            html += f'<td style="padding:8px;text-align:right;font-family:monospace;">{color_quantity}</td>'
            html += f'<td style="padding:8px;text-align:right;font-family:monospace;">{color_length:.1f}</td></tr>\n'
            html += f'                </tbody></table>\n        </div>\n'

        html += f'        <div style="margin-top:10px;padding:10px;background-color:#c8e6c9;font-weight:bold;">\n'
        html += f'            {cable_type} Total: {type_total_quantity} cables, {type_total_length:.1f}m\n        </div>\n    </div>\n'

    html += f"""    <div class="summary-card">
        <table>
            <thead><tr><th>Overall Summary</th><th class="metric">Total Quantity</th><th class="metric">Total Length (m)</th></tr></thead>
            <tbody><tr class="total-row"><td>GRAND TOTAL</td><td class="metric">{total_quantity_all}</td><td class="metric">{total_length_all:.1f}</td></tr></tbody>
        </table>
    </div>
    <div class="summary-card notes">
        <h3>Notes for Ordering</h3>
        <p><strong>Cable Lengths:</strong> Rounded up to nearest 0.5m to match common stock lengths.</p>
        <p><strong>Patch panel connections</strong> are split into individual segments in both the detail table and this summary. Each segment represents one physical cable.</p>
        <p><strong>External Devices:</strong> Connections to/from external device groups include the group distance_from_racks value.</p>
        <p><strong>Extra Stock:</strong> Consider ordering 10-15% extra for contingencies.</p>
    </div>
</body>
</html>
"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Generated cable summary HTML: {output_file}")