import re

# -------------------------------------------------
# Expand computer_info clusters
# -------------------------------------------------
def expand_computer_info_clusters(computer_info_raw):
    """
    Expand computer_info entries with start/end ranges.
    
    Example:
    - device_name: "IG {N}"
      start: 1
      end: 13
      arena_part_number: "902-00011"
      ethernet_ports:
        - adapter: "rFpro"
          ip: "192.168.2.{N+50}"
    
    Expands to 13 individual devices: IG 1, IG 2, ..., IG 13
    """
    expanded = []
    
    for entry in computer_info_raw:
        # Check if this is a cluster definition
        if "start" in entry and "end" in entry:
            device_template = entry.get("device_name", "Device {N}")
            start = entry["start"]
            end = entry["end"]
            part_number = entry.get("arena_part_number", "")
            ports_template = entry.get("ethernet_ports", [])
            
            # Generate individual devices
            for n in range(start, end + 1):
                # Expand device name
                device_name = device_template.replace("{N}", str(n))
                
                # Expand ports
                ports = []
                for port_template in ports_template:
                    port = {}
                    for key, value in port_template.items():
                        if isinstance(value, str):
                            # Replace {N} placeholders
                            value = value.replace("{N}", str(n))
                            # Replace {N+X} placeholders
                            match = re.search(r'\{N\+(\d+)\}', value)
                            if match:
                                offset = int(match.group(1))
                                value = value.replace(match.group(0), str(n + offset))
                            # Replace {N-X} placeholders
                            match = re.search(r'\{N-(\d+)\}', value)
                            if match:
                                offset = int(match.group(1))
                                value = value.replace(match.group(0), str(n - offset))
                        port[key] = value
                    ports.append(port)
                
                # Create expanded entry
                expanded.append({
                    "device_name": device_name,
                    "arena_part_number": part_number,
                    "ethernet_ports": ports
                })
        else:
            # Regular entry, no expansion needed
            expanded.append(entry)
    
    return expanded

# -------------------------------------------------
# Expand external devices (with group support)
# -------------------------------------------------
def expand_external_devices(external_devices_config):
    """
    Expand external devices, handling both grouped and ungrouped formats.
    
    Ungrouped format (flat):
    - name: "Device {N}"
      start: 1
      end: 3
      type: pc
    
    Grouped format (nested):
    - name: Operator Room
      distance_from_racks: 30  # m
      devices:
        - name: "Operator room beltpack {N}"
          start: 1
          end: 7
          type: beltpack
    
    Returns a dict with group names as keys and lists of expanded devices as values.
    Each device dict includes a "distance_from_racks" key (float, metres) inherited
    from its group.  Ungrouped devices go into "default" group with distance 0.
    """
    expanded = {}
    
    if not external_devices_config:
        return expanded
    
    for entry in external_devices_config:
        # Check if this is a grouped entry
        if "devices" in entry:
            group_name = entry.get("name", "External Devices")
            distance_from_racks = float(entry.get("distance_from_racks", 0) or 0)
            group_devices = []
            
            # Expand devices within the group
            for dev_template in entry.get("devices", []):
                if "start" in dev_template and "end" in dev_template:
                    # This is a cluster definition
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
                    # Regular device entry — merge in the group distance and name
                    group_devices.append({
                        **dev_template,
                        "distance_from_racks": distance_from_racks,
                        "group_name": group_name,
                    })
            
            expanded[group_name] = group_devices
        else:
            # Ungrouped device (flat format) — no group-level distance available
            distance_from_racks = float(entry.get("distance_from_racks", 0) or 0)

            if "start" in entry and "end" in entry:
                # This is a cluster definition
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
                # Regular ungrouped device
                if "External Devices" not in expanded:
                    expanded["External Devices"] = []
                expanded["External Devices"].append({
                    **entry,
                    "distance_from_racks": distance_from_racks,
                    "group_name": "External Devices",
                })
    
    return expanded

# -------------------------------------------------
# Expand wiring clusters
# -------------------------------------------------
def expand_wiring_clusters(connections, layer_cable_type="", layer_edge_color="#333333"):
    """
    Expand wiring connection clusters into individual connections.
    
    Supports cable_type at both layer and connection level:
    - Layer cable_type: default for all connections in the layer
    - Connection cable_type: overrides layer cable_type for that connection
    
    Cluster format with single 'to':
    - from: "R4 16A PDU B"
      to: "IG {N}"
      start: 8
      end: 10
    
    Cluster format with multiple 'to' targets:
    - from: "Graphics Switch"
      to:
        - "Operator PC"
        - "Speedgoat"
    
    Supports per-connection cable_type and edge_color override:
    - from: "Switch"
      to: "Device"
      cable_type: "Cat6"
      edge_color: "#FF0000"
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
        cable_type = conn.get("cable_type", layer_cable_type)  # Use connection cable_type or fallback to layer
        
        # Normalize to_field to always be a list
        if isinstance(to_field, str):
            to_list = [to_field]
        elif isinstance(to_field, list):
            to_list = to_field
        else:
            to_list = [to_field]
        
        # Check if this is a cluster definition (with start/end)
        if "start" in conn and "end" in conn:
            start = int(conn["start"]) if isinstance(conn["start"], str) else conn["start"]
            end = int(conn["end"]) if isinstance(conn["end"], str) else conn["end"]
            
            # Expand each 'to' template with the cluster range
            for to_template in to_list:
                for n in range(start, end + 1):
                    # Replace {N} placeholders
                    from_dev = from_template.replace("{N}", str(n))
                    to_dev = to_template.replace("{N}", str(n))
                    
                    # Replace {N+X} placeholders
                    match = re.search(r'\{N\+(\d+)\}', from_dev)
                    if match:
                        offset = int(match.group(1))
                        from_dev = from_dev.replace(match.group(0), str(n + offset))
                    
                    match = re.search(r'\{N\+(\d+)\}', to_dev)
                    if match:
                        offset = int(match.group(1))
                        to_dev = to_dev.replace(match.group(0), str(n + offset))
                    
                    # Replace {N-X} placeholders
                    match = re.search(r'\{N-(\d+)\}', from_dev)
                    if match:
                        offset = int(match.group(1))
                        from_dev = from_dev.replace(match.group(0), str(n - offset))
                    
                    match = re.search(r'\{N-(\d+)\}', to_dev)
                    if match:
                        offset = int(match.group(1))
                        to_dev = to_dev.replace(match.group(0), str(n - offset))
                    
                    # Create expanded connection
                    expanded_conn = {
                        "from": from_dev,
                        "to": to_dev
                    }
                    
                    # Add optional fields if present
                    if label:
                        expanded_conn["label"] = label
                    if color:
                        expanded_conn["color"] = color
                    if edge_color:
                        expanded_conn["edge_color"] = edge_color
                    if style:
                        expanded_conn["style"] = style
                    if width:
                        expanded_conn["width"] = width
                    if cable_type:
                        expanded_conn["cable_type"] = cable_type
                    expanded.append(expanded_conn)
        else:
            # No cluster - just handle multiple 'to' targets
            for to_template in to_list:
                expanded_conn = {
                    "from": from_template,
                    "to": to_template
                }
                
                # Add optional fields if present
                if label:
                    expanded_conn["label"] = label
                if color:
                    expanded_conn["color"] = color
                if edge_color:
                    expanded_conn["edge_color"] = edge_color
                if style:
                    expanded_conn["style"] = style
                if width:
                    expanded_conn["width"] = width
                if cable_type:
                    expanded_conn["cable_type"] = cable_type
                
                expanded.append(expanded_conn)
    
    return expanded

# -------------------------------------------------
# Expand cluster definitions
# -------------------------------------------------
def expand_clusters(devices):
    """
    Expand cluster device definitions into individual devices.
    
    Cluster format:
    - name: "RVD {N}"
      start_u: 20
      start: 1
      end: 3
      units: 4
      spacing: 0
      type: pc
    
    Expands to:
    - name: "RVD 1", start_u: 20, units: 4, type: pc
    - name: "RVD 2", start_u: 16, units: 4, type: pc
    - name: "RVD 3", start_u: 12, units: 4, type: pc
    """
    expanded = []
    
    for dev in devices:
        # Check if this is a cluster definition
        if "start" in dev and "end" in dev and "{N}" in dev.get("name", ""):
            start_num = dev["start"]
            end_num = dev["end"]
            start_u = dev["start_u"]
            units = dev["units"]
            spacing = dev.get("spacing", 0)
            
            # Expand the cluster
            for i in range(start_num, end_num + 1):
                # Calculate U position for this item
                items_before = i - start_num
                u_offset = (units + spacing) * items_before
                current_start_u = start_u - u_offset
                
                # Create expanded device
                expanded_dev = dev.copy()
                expanded_dev["name"] = dev["name"].replace("{N}", str(i))
                expanded_dev["start_u"] = current_start_u
                
                # Remove cluster-specific fields
                for key in ["start", "end", "spacing"]:
                    expanded_dev.pop(key, None)
                
                expanded.append(expanded_dev)
        else:
            # Regular device, add as-is
            expanded.append(dev)
    
    return expanded
