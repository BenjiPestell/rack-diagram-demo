from dataclasses import dataclass
from clusters import expand_clusters, expand_wiring_clusters


@dataclass
class PatchAssignment:
    port:       int
    side_a:     str    # local side label, e.g. "dSPACE" or "← R1 Patch panel port 3"
    side_b:     str    # other side label, e.g. "Ethercat drives" or "→ R2 Patch panel port 1"
    cable_type: str
    layer_name: str
    edge_color: str
    note:       str    # from port_notes on the patch panel device


# -------------------------------------------------
# Colour helper
# -------------------------------------------------
def _lighten_hex(hex_color: str, factor: float = 0.65) -> str:
    """Blend hex_color toward white by factor (0 = original, 1 = white)."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
    except (ValueError, IndexError):
        return "#EEEEEE"
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return f"#{r:02X}{g:02X}{b:02X}"


# -------------------------------------------------
# Port assignment
# -------------------------------------------------
def _assign_ports(pending_entries: list, port_count: int, panel_name: str) -> list:
    """
    Takes a list of pending entry dicts (each with 'requested_port' int or None).
    Returns a list of (port_num, entry) sorted by port_num.

    Manual ports are placed first; remaining entries are auto-filled in order.
    Overflows (beyond port_count) are assigned and flagged; a warning is printed.
    """
    used = {}    # port_num -> entry
    unassigned = []

    # Pass A: manually-specified ports
    for entry in pending_entries:
        req = entry.get("requested_port")
        if req is not None:
            req = int(req)
            if req < 1:
                print(f"Warning: [{panel_name}] port {req} < 1 — auto-assigning")
                unassigned.append(entry)
            elif req in used:
                print(f"Warning: [{panel_name}] port {req} conflict — auto-assigning duplicate")
                unassigned.append(entry)
            else:
                used[req] = entry
        else:
            unassigned.append(entry)

    # Pass B: auto-fill
    next_port = 1
    for entry in unassigned:
        while next_port in used:
            next_port += 1
        if next_port > port_count:
            print(f"Warning: [{panel_name}] overflow — {len(pending_entries)} connections exceed {port_count} ports. Assigning port {next_port}.")
        used[next_port] = entry
        next_port += 1

    return sorted(used.items())


# -------------------------------------------------
# Collect patch assignments
# -------------------------------------------------
def collect_patch_assignments(racks_config: list, wiring_layers: list) -> dict:
    """
    Scan racks_config to discover all Patch panel devices, then scan
    wiring_layers to collect every connection that routes through each panel.
    Port numbers are assigned (hybrid: manual-first, then auto-fill).

    Returns:
        {panel_name: (port_count, [PatchAssignment, ...])}
    """
    # ------------------------------------------------------------------
    # Phase 1: discover patch panels
    # ------------------------------------------------------------------
    panels = {}   # name -> {port_count, port_notes, rack_name}
    for rack_cfg in racks_config:
        rack_name = rack_cfg["rack"].get("name", rack_cfg["rack"].get("id", ""))
        for side in ("front", "rear"):
            for dev in expand_clusters(rack_cfg.get(side, [])):
                if dev.get("type") == "Patch panel":
                    panels[dev["name"]] = {
                        "port_count": int(dev.get("ports", 24)),
                        "port_notes": dev.get("port_notes", {}) or {},
                        "rack_name":  rack_name,
                    }

    if not panels:
        return {}

    # ------------------------------------------------------------------
    # Phase 2: collect raw pending assignments
    # ------------------------------------------------------------------
    pending = {name: [] for name in panels}

    # Each pending entry dict:
    #   side_a, side_b          : str | None  (None = deferred cross-panel label)
    #   side_b_panel            : str | None  (name of partner panel for cross-panel label)
    #   side_a_panel            : str | None
    #   link                    : dict | None  (shared {from_port, to_port} for cross-panel pairs)
    #   link_role               : "from" | "to" | None
    #   cable_type, layer_name, edge_color : str
    #   requested_port          : int | None

    links = []

    for layer in wiring_layers:
        layer_name  = layer.get("name", "")
        edge_color  = layer.get("edge_color", "#333333")
        cable_type  = layer.get("cable_type", "")
        connections = expand_wiring_clusters(
            layer.get("connections", []), cable_type, edge_color
        )

        for conn in connections:
            from_dev   = conn["from"]
            to_dev     = conn["to"]
            vpf        = conn.get("via_patch_from", "")
            vpt        = conn.get("via_patch_to",   "")
            ppf        = conn.get("patch_port_from")
            ppt        = conn.get("patch_port_to")
            conn_cable = conn.get("cable_type", cable_type)
            conn_color = conn.get("edge_color", edge_color)

            if not vpf and not vpt:
                continue

            if vpf and not vpf in panels:
                print(f"Warning: via_patch_from '{vpf}' does not match any Patch panel device")
            if vpt and not vpt in panels:
                print(f"Warning: via_patch_to '{vpt}' does not match any Patch panel device")

            if vpf and vpt:
                # Both panels — linked pair with deferred cross-panel labels
                link = {"from_port": None, "to_port": None}
                links.append(link)

                if vpf in pending:
                    pending[vpf].append({
                        "side_a":       from_dev,
                        "side_b":       None,
                        "side_b_panel": vpt,
                        "side_a_panel": None,
                        "link":         link,
                        "link_role":    "from",
                        "cable_type":   conn_cable,
                        "layer_name":   layer_name,
                        "edge_color":   conn_color,
                        "requested_port": ppf,
                    })

                if vpt in pending:
                    pending[vpt].append({
                        "side_a":       None,
                        "side_b":       to_dev,
                        "side_b_panel": None,
                        "side_a_panel": vpf,
                        "link":         link,
                        "link_role":    "to",
                        "cable_type":   conn_cable,
                        "layer_name":   layer_name,
                        "edge_color":   conn_color,
                        "requested_port": ppt,
                    })

            elif vpf:
                if vpf in pending:
                    pending[vpf].append({
                        "side_a":       from_dev,
                        "side_b":       to_dev,
                        "side_b_panel": None,
                        "side_a_panel": None,
                        "link":         None,
                        "link_role":    None,
                        "cable_type":   conn_cable,
                        "layer_name":   layer_name,
                        "edge_color":   conn_color,
                        "requested_port": ppf,
                    })

            else:  # only vpt
                if vpt in pending:
                    pending[vpt].append({
                        "side_a":       from_dev,
                        "side_b":       to_dev,
                        "side_b_panel": None,
                        "side_a_panel": None,
                        "link":         None,
                        "link_role":    None,
                        "cable_type":   conn_cable,
                        "layer_name":   layer_name,
                        "edge_color":   conn_color,
                        "requested_port": ppt,
                    })

    # ------------------------------------------------------------------
    # Phase 3: assign port numbers per panel
    # ------------------------------------------------------------------
    resolved = {}   # panel_name -> [(port_num, entry), ...]
    for panel_name, entries in pending.items():
        port_count = panels[panel_name]["port_count"]
        resolved[panel_name] = _assign_ports(entries, port_count, panel_name)

    # ------------------------------------------------------------------
    # Phase 4: record assigned port numbers into link objects, then
    #          build deferred cross-panel labels
    # ------------------------------------------------------------------
    for panel_name, sorted_entries in resolved.items():
        for port_num, entry in sorted_entries:
            link = entry.get("link")
            if link is None:
                continue
            role = entry["link_role"]
            if role == "from":
                link["from_port"] = port_num
            else:
                link["to_port"] = port_num

    for panel_name, sorted_entries in resolved.items():
        for port_num, entry in sorted_entries:
            link = entry.get("link")
            if link is None:
                continue
            role = entry["link_role"]
            if role == "from":
                partner = entry["side_b_panel"]
                partner_port = link.get("to_port")
                if partner_port is not None:
                    entry["side_b"] = f"-> {partner} port {partner_port}"
                else:
                    entry["side_b"] = f"-> {partner} (unknown port)"
            else:
                partner = entry["side_a_panel"]
                partner_port = link.get("from_port")
                if partner_port is not None:
                    entry["side_a"] = f"<- {partner} port {partner_port}"
                else:
                    entry["side_a"] = f"<- {partner} (unknown port)"

    # ------------------------------------------------------------------
    # Phase 5: attach port_notes and build final PatchAssignment objects
    # ------------------------------------------------------------------
    result = {}
    for panel_name in panels:
        port_count  = panels[panel_name]["port_count"]
        port_notes  = panels[panel_name]["port_notes"]
        sorted_entries = resolved[panel_name]

        assignments = []
        for port_num, entry in sorted_entries:
            # port_notes keys may be int or string depending on YAML
            note = str(port_notes.get(port_num) or port_notes.get(str(port_num)) or "")
            assignments.append(PatchAssignment(
                port=port_num,
                side_a=entry.get("side_a") or "?",
                side_b=entry.get("side_b") or "?",
                cable_type=entry.get("cable_type", ""),
                layer_name=entry.get("layer_name", ""),
                edge_color=entry.get("edge_color", "#333333"),
                note=note,
            ))

        result[panel_name] = (port_count, assignments)

    return result


# -------------------------------------------------
# Generate DOT diagram
# -------------------------------------------------
def _esc(s: str) -> str:
    """Escape characters that are special in Graphviz HTML labels."""
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _abbrev(s: str, max_len: int = 14) -> str:
    """Truncate string to max_len chars, appending '..' if truncated."""
    s = (s or "").strip()
    return s if len(s) <= max_len else s[:max_len - 2] + ".."


def generate_patch_panel_dot(
    panel_name: str,
    port_count: int,
    assignments: list,
    type_colors: dict,
) -> str:
    """
    Generate a Graphviz DOT diagram for a single patch panel.
    Ports are arranged in a physical front-panel grid (12 ports per bank).
    Each port shows abbreviated Side A / Side B labels, colour-coded by layer.
    """
    PORTS_PER_ROW   = 12
    PORT_WIDTH      = 90          # px per port cell
    FONT_FACE       = "Sinkin Sans 400 Regular"
    TITLE_FONT      = 14
    PORT_NUM_FONT   = 9
    CONTENT_FONT    = 8
    PORT_NUM_BG     = "#383838"   # dark grey for port number strip
    PORT_NUM_OVF_BG = "#cc2222"   # red for overflow port numbers
    EMPTY_BG        = "#d0d0d0"   # light grey for unused ports
    HEADER_BG       = "#5af282"   # green title bar (matches rack layout)
    OVERFLOW_BG     = "#FFD0D0"   # light red for overflow port content

    assigned_by_port = {a.port: a for a in assignments}
    max_assigned = max((a.port for a in assignments), default=0)
    max_port = max(port_count, max_assigned)

    # Split into banks of PORTS_PER_ROW
    banks = []
    for start in range(1, max_port + 1, PORTS_PER_ROW):
        banks.append(list(range(start, min(start + PORTS_PER_ROW, max_port + 1))))

    TABLE_WIDTH = PORTS_PER_ROW * PORT_WIDTH
    safe_id = "".join(c if c.isalnum() or c == "_" else "_" for c in panel_name)

    lines = []
    lines.append(f'digraph "{_esc(panel_name)}" {{')
    lines.append('  graph [rankdir=TB, bgcolor="white"];')
    lines.append(f'  node [shape=plain, fontname="{FONT_FACE}"];')
    lines.append("")
    lines.append(f"  {safe_id} [label=<")
    lines.append(f'<TABLE BORDER="2" CELLBORDER="1" CELLSPACING="0" CELLPADDING="3" WIDTH="{TABLE_WIDTH}">')

    # Title row
    lines.append("<TR>")
    lines.append(
        f'<TD COLSPAN="{PORTS_PER_ROW}" BGCOLOR="{HEADER_BG}">'
        f'<FONT POINT-SIZE="{TITLE_FONT}" FACE="{FONT_FACE}"><B>{_esc(panel_name)}</B></FONT>'
        f'</TD>'
    )
    lines.append("</TR>")

    for bank in banks:
        pad = PORTS_PER_ROW - len(bank)

        # ── Port number strip ──────────────────────────────────────────────
        lines.append("<TR>")
        for port in bank:
            bg = PORT_NUM_OVF_BG if port > port_count else PORT_NUM_BG
            lines.append(
                f'<TD WIDTH="{PORT_WIDTH}" BGCOLOR="{bg}">'
                f'<FONT POINT-SIZE="{PORT_NUM_FONT}" FACE="{FONT_FACE}" COLOR="white"><B>{port}</B></FONT>'
                f'</TD>'
            )
        if pad:
            lines.append(f'<TD COLSPAN="{pad}" BGCOLOR="{PORT_NUM_BG}"></TD>')
        lines.append("</TR>")

        # ── Port content strip ─────────────────────────────────────────────
        lines.append("<TR>")
        for port in bank:
            a = assigned_by_port.get(port)
            if a:
                bg = OVERFLOW_BG if port > port_count else _lighten_hex(a.edge_color, factor=0.55)
                sa = _esc(_abbrev(a.side_a))
                sb = _esc(_abbrev(a.side_b))
                lines.append(
                    f'<TD BGCOLOR="{bg}">'
                    f'<FONT POINT-SIZE="{CONTENT_FONT}" FACE="{FONT_FACE}"><B>{sa}</B><BR/>{sb}</FONT>'
                    f'</TD>'
                )
            else:
                lines.append(f'<TD BGCOLOR="{EMPTY_BG}"></TD>')
        if pad:
            lines.append(f'<TD COLSPAN="{pad}" BGCOLOR="{EMPTY_BG}"></TD>')
        lines.append("</TR>")

    lines.append("</TABLE>")
    lines.append("  >];")
    lines.append("}")

    return "\n".join(lines)
