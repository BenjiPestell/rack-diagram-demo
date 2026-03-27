import re
from collections import OrderedDict


# -------------------------------------------------
# Port schedule building
# -------------------------------------------------

def _safe_name(name):
    return re.sub(r'[^a-z0-9]', '_', name.lower()).strip('_')


def _collect_usages(device_name, all_expanded_conns):
    """
    Scan expanded connections for all appearances of device_name.
    Returns a list of dicts:
      {explicit_port, peer_device, peer_port, layer_name, layer_color, ip, conn, role}
    role: 'from' | 'to' | 'patch_from' | 'patch_to'
    """
    usages = []
    for conn in all_expanded_conns:
        # Ethernet connections only
        cable = (conn.get("cable_type") or "").lower()
        if cable and "ethernet" not in cable:
            continue
        frm = conn.get("from", "")
        to  = conn.get("to",   "")
        vpf = conn.get("via_patch_from", "")
        vpt = conn.get("via_patch_to",   "")
        layer_name  = conn.get("_layer_name", "")
        layer_color = conn.get("_layer_color", "#888888")

        if frm == device_name:
            usages.append({
                "explicit_port": conn.get("from_port"),
                "peer_device":   to,
                "peer_port":     conn.get("to_port"),
                "layer_name":    layer_name,
                "layer_color":   layer_color,
                "ip":            conn.get("from_ip"),
                "conn":          conn,
                "role":          "from",
            })
        elif to == device_name:
            usages.append({
                "explicit_port": conn.get("to_port"),
                "peer_device":   frm,
                "peer_port":     conn.get("from_port"),
                "layer_name":    layer_name,
                "layer_color":   layer_color,
                "ip":            conn.get("to_ip"),
                "conn":          conn,
                "role":          "to",
            })
        if vpf == device_name:
            usages.append({
                "explicit_port": conn.get("patch_port_from"),
                "peer_device":   frm,
                "peer_port":     conn.get("from_port"),
                "layer_name":    layer_name,
                "layer_color":   layer_color,
                "ip":            None,
                "conn":          conn,
                "role":          "patch_from",
            })
        if vpt == device_name:
            usages.append({
                "explicit_port": conn.get("patch_port_to"),
                "peer_device":   to,
                "peer_port":     conn.get("to_port"),
                "layer_name":    layer_name,
                "layer_color":   layer_color,
                "ip":            None,
                "conn":          conn,
                "role":          "patch_to",
            })
    return usages


def build_port_schedule(device_name, device, all_expanded_conns):
    """
    Returns OrderedDict: port_num (int) -> entry dict.
    Keys in entry: interface_label, connected_device, connected_device_port,
                   ip_address, layer_name, layer_color
    """
    usages = _collect_usages(device_name, all_expanded_conns)
    port_notes = device.get("port_notes", {})
    total_ports = device.get("ports", 0)

    # Step 1: Reserve explicitly-numbered ports
    occupied = set()
    for u in usages:
        if u["explicit_port"] is not None:
            occupied.add(int(u["explicit_port"]))

    # Step 2: Auto-assign remaining
    next_free = 1
    assignments = {}  # port_num -> usage
    for u in usages:
        if u["explicit_port"] is not None:
            p = int(u["explicit_port"])
        else:
            while next_free in occupied:
                next_free += 1
            p = next_free
            occupied.add(p)
            next_free += 1

        if p > total_ports and total_ports > 0:
            print(f"Warning: {device_name} port {p} exceeds declared port count {total_ports}")

        # Last write wins if same port appears twice (shouldn't normally happen)
        assignments[p] = u

    # Build full port map including unoccupied rows
    result = OrderedDict()
    max_port = max(total_ports, max(assignments.keys()) if assignments else 0)
    for p in range(1, max_port + 1):
        u = assignments.get(p)
        note_key = str(p)
        label = port_notes.get(note_key) or port_notes.get(p) or ""
        if u:
            result[p] = {
                "interface_label":       label,
                "connected_device":      u["peer_device"],
                "connected_device_port": u["peer_port"],
                "ip_address":            u["ip"],
                "layer_name":            u["layer_name"],
                "layer_color":           u["layer_color"],
                "overflow":              (p > total_ports and total_ports > 0),
            }
        else:
            result[p] = {
                "interface_label":       label,
                "connected_device":      None,
                "connected_device_port": None,
                "ip_address":            None,
                "layer_name":            None,
                "layer_color":           None,
                "overflow":              False,
            }
    return result


