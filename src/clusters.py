import re

# -------------------------------------------------
# Expand computer_info clusters
# -------------------------------------------------
def expand_computer_info_clusters(computer_info_raw):
    """
    Expand computer_info entries with start/end ranges.
    """
    expanded = []
    
    for entry in computer_info_raw:
        if "start" in entry and "end" in entry:
            device_template = entry.get("device_name", "Device {N}")
            start = entry["start"]
            end = entry["end"]
            part_number = entry.get("arena_part_number", "")
            ports_template = entry.get("ethernet_ports", [])
            
            for n in range(start, end + 1):
                device_name = device_template.replace("{N}", str(n))
                
                ports = []
                for port_template in ports_template:
                    port = {}
                    for key, value in port_template.items():
                        if isinstance(value, str):
                            value = value.replace("{N}", str(n))
                            match = re.search(r'\{N\+(\d+)\}', value)
                            if match:
                                offset = int(match.group(1))
                                value = value.replace(match.group(0), str(n + offset))
                            match = re.search(r'\{N-(\d+)\}', value)
                            if match:
                                offset = int(match.group(1))
                                value = value.replace(match.group(0), str(n - offset))
                        port[key] = value
                    ports.append(port)
                
                expanded.append({
                    "device_name": device_name,
                    "arena_part_number": part_number,
                    "ethernet_ports": ports
                })
        else:
            expanded.append(entry)
    
    return expanded

# -------------------------------------------------
# Expand external devices (with group support)
# -------------------------------------------------
def expand_external_devices(external_devices_config):
    """
    Expand external devices, handling both grouped and ungrouped formats.
    Returns a dict with group names as keys and lists of expanded devices as values.
    """
    expanded = {}
    
    if not external_devices_config:
        return expanded
    
    for entry in external_devices_config:
        if "devices" in entry:
            group_name = entry.get("name", "External Devices")
            distance_from_racks = float(entry.get("distance_from_racks", 0) or 0)
            group_devices = []
            
            for dev_template in entry.get("devices", []):
                if "start" in dev_template and "end" in dev_template:
                    name_template = dev_template.get("name", "Device {N}")
                    start = dev_template["start"]
                    end = dev_template["end"]
                    dev_type = dev_template.get("type", "")
                    
                    for n in range(start, end + 1):
                        dev_name = name_template.replace("{N}", str(n))
                        group_devices.append({
                            "name": dev_name,
                            "type": dev_type,
                            "distance_from_racks": distance_from_racks,
                            "group_name": group_name,
                        })
                else:
                    group_devices.append({
                        **dev_template,
                        "distance_from_racks": distance_from_racks,
                        "group_name": group_name,
                    })
            
            expanded[group_name] = group_devices
        else:
            distance_from_racks = float(entry.get("distance_from_racks", 0) or 0)

            if "start" in entry and "end" in entry:
                name_template = entry.get("name", "Device {N}")
                start = entry["start"]
                end = entry["end"]
                dev_type = entry.get("type", "")
                
                group_devices = []
                for n in range(start, end + 1):
                    dev_name = name_template.replace("{N}", str(n))
                    group_devices.append({
                        "name": dev_name,
                        "type": dev_type,
                        "distance_from_racks": distance_from_racks,
                        "group_name": "External Devices",
                    })
                
                expanded["External Devices"] = group_devices
            else:
                if "External Devices" not in expanded:
                    expanded["External Devices"] = []
                expanded["External Devices"].append({
                    **entry,
                    "distance_from_racks": distance_from_racks,
                    "group_name": "External Devices",
                })
    
    return expanded

# -------------------------------------------------
# Patch panel expansion
# -------------------------------------------------
def _annotate_patch(conn):
    """
    If a connection has via_patch_from / via_patch_to, return it unchanged but
    with two extra fields added:

        _patch_label : str   e.g. "via PP Front 1 -> PP Front 2"
        _patch_style : "patched"

    These are used by wiring_diagram.py to render the edge as dashed with an
    annotation label, while keeping the graph structure as a single A -- B edge.
    Connections without patch fields are returned unchanged.
    """
    pp_from = conn.get("via_patch_from")
    pp_to   = conn.get("via_patch_to")

    if not pp_from and not pp_to:
        return conn

    if pp_from and pp_to:
        patch_label = f"via {pp_from} -> {pp_to}"
    elif pp_from:
        patch_label = f"via {pp_from}"
    else:
        patch_label = f"via {pp_to}"

    return {**conn, "_patch_label": patch_label, "_patch_style": "patched"}


# -------------------------------------------------
# Expand wiring clusters
# -------------------------------------------------
def expand_wiring_clusters(connections, layer_cable_type="", layer_edge_color="#333333"):
    """
    Expand wiring connection clusters into individual connections, then expand
    any patch panel hops.

    Expansion order:
      1. {N} / {N+X} / {N-X} cluster expansion (existing behaviour)
      2. Multiple 'to' targets flattened to individual connections
      3. via_patch_from / via_patch_to split into 2-3 hop connections

    Downstream consumers (wiring_diagram.py, cable_length.py) receive only plain
    from/to connections. Patch hops carry _patch_hop=True and _patch_style so
    wiring_diagram.py can render the inter-rack segment as dashed.
    """
    expanded = []
    
    for conn in connections:
        from_template = conn.get("from", "")
        to_field = conn.get("to", "")
        label = conn.get("label", "")
        color = conn.get("color", "")
        edge_color = conn.get("edge_color", "")
        style = conn.get("style", "")
        width = conn.get("width", "")
        cable_type = conn.get("cable_type", layer_cable_type)

        # via_patch fields -- passed through to _expand_patch_hops after {N} expansion
        via_patch_from = conn.get("via_patch_from", "")
        via_patch_to   = conn.get("via_patch_to",   "")

        # port assignment fields -- passed through unchanged
        from_port       = conn.get("from_port")
        to_port         = conn.get("to_port")
        patch_port_from = conn.get("patch_port_from")
        patch_port_to   = conn.get("patch_port_to")
        from_ip         = conn.get("from_ip")
        to_ip           = conn.get("to_ip")
        
        # Normalize to_field to always be a list
        if isinstance(to_field, str):
            to_list = [to_field]
        elif isinstance(to_field, list):
            to_list = to_field
        else:
            to_list = [to_field]
        
        # -- Step 1 & 2: {N} cluster expansion -------------------------------
        # Tuple: (from, to, via_patch_from, via_patch_to, from_ip, to_ip)
        base_conns = []

        if "start" in conn and "end" in conn:
            start = int(conn["start"]) if isinstance(conn["start"], str) else conn["start"]
            end   = int(conn["end"])   if isinstance(conn["end"],   str) else conn["end"]

            for to_template in to_list:
                for n in range(start, end + 1):
                    def _sub(s, n=n):
                        if not isinstance(s, str):
                            return s
                        s = s.replace("{N}", str(n))
                        m = re.search(r'\{N\+(\d+)\}', s)
                        if m:
                            s = s.replace(m.group(0), str(n + int(m.group(1))))
                        m = re.search(r'\{N-(\d+)\}', s)
                        if m:
                            s = s.replace(m.group(0), str(n - int(m.group(1))))
                        return s

                    base_conns.append((
                        _sub(from_template),
                        _sub(to_template),
                        _sub(via_patch_from) if via_patch_from else "",
                        _sub(via_patch_to)   if via_patch_to   else "",
                        _sub(from_ip)        if from_ip is not None else None,
                        _sub(to_ip)          if to_ip   is not None else None,
                    ))
        else:
            for to_template in to_list:
                base_conns.append((from_template, to_template, via_patch_from, via_patch_to, from_ip, to_ip))

        # -- Step 3: build connection dicts and expand patch hops -------------
        for (frm, to, vpf, vpt, fip, tip) in base_conns:
            base = {"from": frm, "to": to}
            if label:       base["label"]      = label
            if color:       base["color"]      = color
            if edge_color:  base["edge_color"] = edge_color
            if style:       base["style"]      = style
            if width:       base["width"]      = width
            if cable_type:  base["cable_type"] = cable_type
            if vpf:         base["via_patch_from"] = vpf
            if vpt:         base["via_patch_to"]   = vpt
            if from_port is not None:       base["from_port"]       = from_port
            if to_port is not None:         base["to_port"]         = to_port
            if patch_port_from is not None: base["patch_port_from"] = patch_port_from
            if patch_port_to is not None:   base["patch_port_to"]   = patch_port_to
            if fip is not None:             base["from_ip"]         = fip
            if tip is not None:             base["to_ip"]           = tip

            # Annotate patch connections (keeps single A--B edge, adds _patch_label)
            expanded.append(_annotate_patch(base))
    
    return expanded

# -------------------------------------------------
# Expand cluster definitions
# -------------------------------------------------
def expand_clusters(devices):
    """
    Expand cluster device definitions into individual devices.
    """
    expanded = []
    
    for dev in devices:
        if "start" in dev and "end" in dev and "{N}" in dev.get("name", ""):
            start_num = dev["start"]
            end_num = dev["end"]
            start_u = dev["start_u"]
            units = dev["units"]
            spacing = dev.get("spacing", 0)
            
            for i in range(start_num, end_num + 1):
                items_before = i - start_num
                u_offset = (units + spacing) * items_before
                current_start_u = start_u - u_offset
                
                expanded_dev = dev.copy()
                expanded_dev["name"] = dev["name"].replace("{N}", str(i))
                expanded_dev["start_u"] = current_start_u
                
                for key in ["start", "end", "spacing"]:
                    expanded_dev.pop(key, None)
                
                expanded.append(expanded_dev)
        else:
            expanded.append(dev)
    
    return expanded