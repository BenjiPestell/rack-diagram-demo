import csv
import math
import re
from clusters import expand_wiring_clusters

# -------------------------------------------------
# Cable length calculation
# -------------------------------------------------
def calculate_cable_length(from_device, to_device, all_devices, rack_configs, config):
    """
    Calculate minimum cable length needed for a connection.
    
    Formula: (unit_delta * 0.045) + (front_to_back * 1 or 0) + (inter_rack * 1 or 0) + cable_slack
    
    where:
    - unit_delta: 
      * Intra-rack: absolute difference in bottom U positions
      * Inter-rack: (start_u - 1) on from device + (start_u - 1) on to device
      * Undefined devices: 0
    - front_to_back: 0.5m if connection spans from front to rear within same rack, else 0
    - inter_rack: inter-rack distance if devices in different racks, else 0
    - cable_slack: configured slack length
    """
    
    # Get device info
    from_info = all_devices.get(from_device)
    to_info = all_devices.get(to_device)
    
    if not from_info or not to_info:
        return None
    
    # Get config values
    cable_slack = config.get("cable_slack_length", 0.2)  # Default 0.2m
    standard_u_height = config.get("standard_u_height", 0.045)  # Default 0.045m
    front_to_back = config.get("front_to_back_length", 0.5)  # Default 0.5m
    inter_rack_distance = config.get("inter_rack_distance", 2.5)  # Default 2.5m
    
    # Build rack name map
    rack_name_map = {}
    rack_position_map = {}
    rack_position = 0
    for rack_config in rack_configs:
        rack_id = rack_config["rack"].get("id", "rack")
        rack_name = rack_config["rack"].get("name", rack_id)
        rack_name_map[rack_id] = rack_name
        rack_position_map[rack_id] = rack_position
        rack_position += 1
    
    from_rack = from_info.get("rack_id")
    to_rack = to_info.get("rack_id")
    from_side = from_info.get("side", "front")
    to_side = to_info.get("side", "front")
    from_start_u = from_info.get("start_u", 0)
    to_start_u = to_info.get("start_u", 0)
    from_units = from_info.get("units", 1)
    to_units = to_info.get("units", 1)
    
    # Get rack names for display
    from_rack_name = rack_name_map.get(from_rack, from_rack)
    to_rack_name = rack_name_map.get(to_rack, to_rack)
    
    # Calculate unit distance
    if from_rack != to_rack and from_rack != "external" and to_rack != "external":
        # Inter-rack connection
        # If devices have start_u, include U distance from device to U1 on both ends
        # Otherwise (undefined devices), use 0
        from_u_dist = (from_start_u - 1) if from_start_u else 0
        to_u_dist = (to_start_u - 1) if to_start_u else 0
        unit_delta = from_u_dist + to_u_dist
        f2b_length = 0  # No F2B for inter-rack
    else:
        # Intra-rack connection
        if from_start_u and to_start_u:
            # Both devices have positions - use bottom U
            from_bottom_u = from_start_u - from_units + 1
            to_bottom_u = to_start_u - to_units + 1
            unit_delta = abs(from_bottom_u - to_bottom_u)
        else:
            # One or both devices undefined - use 0 for U distance
            unit_delta = 0
        
        # Calculate front-to-back distance (only if same rack, different sides)
        f2b_length = 0
        if from_rack == to_rack and from_side != to_side and from_side != "external" and to_side != "external":
            f2b_length = front_to_back
    
    unit_length = unit_delta * standard_u_height
    
    # Calculate inter-rack distance
    inter_rack_length = 0
    if from_rack != to_rack and from_rack != "external" and to_rack != "external":
        from_pos = rack_position_map.get(from_rack, 0)
        to_pos = rack_position_map.get(to_rack, 0)
        rack_delta = abs(from_pos - to_pos)
        inter_rack_length = rack_delta * inter_rack_distance
    
    # Total cable length
    total_length = unit_length + f2b_length + inter_rack_length + cable_slack
    total_length = math.ceil(total_length * 2) / 2
    
    return {
        "from_rack": from_rack_name,
        "to_rack": to_rack_name,
        "unit_delta": unit_delta,
        "unit_length": unit_length,
        "f2b_length": f2b_length,
        "inter_rack_length": inter_rack_length,
        "cable_slack": cable_slack,
        "total_length": total_length
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
            font-weight: bold;
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
                <th class="metric">Slack (m)</th>
                <th class="metric total">Min Length (m)</th>
            </tr>
        </thead>
        <tbody>
"""
    
    # Process each wiring layer
    for layer in wiring_layers:
        layer_name = layer["name"]
        connections_raw = layer.get("connections", [])
        
        # Expand connections
        layer_cable_type = layer.get("cable_type", "")
        connections = expand_wiring_clusters(connections_raw, layer_cable_type)
        
        # Output each connection
        for conn in connections:
            from_dev = conn["from"]
            to_dev = conn["to"]
            
            # Get device info
            from_info = all_devices.get(from_dev)
            to_info = all_devices.get(to_dev)
            
            if not from_info or not to_info:
                continue
            
            # Calculate cable length
            cable_data = calculate_cable_length(from_dev, to_dev, all_devices, racks_config, config)
            
            if cable_data:
                cable_type = conn.get("cable_type", "")
                html += f"""            <tr>
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
# Generate cable length table
# -------------------------------------------------
def generate_cable_length_table(all_devices, racks_config, wiring_layers, config, output_file="output/cable_lengths.csv"):
    """Generate a table with cable length calculations for all connections"""
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Header
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
            "Cable Slack (m)",
            "Min Cable Length (m)"
        ])
        
        # Process each wiring layer
        for layer in wiring_layers:
            layer_name = layer["name"]
            connections_raw = layer.get("connections", [])
            
            # Expand connections
            layer_cable_type = layer.get("cable_type", "")
            connections = expand_wiring_clusters(connections_raw, layer_cable_type)
            
            # Output each connection
            for conn in connections:
                from_dev = conn["from"]
                to_dev = conn["to"]
                
                # Get device info
                from_info = all_devices.get(from_dev)
                to_info = all_devices.get(to_dev)
                
                if not from_info or not to_info:
                    continue
                
                # Calculate cable length
                cable_data = calculate_cable_length(from_dev, to_dev, all_devices, racks_config, config)
                
                if cable_data:
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
                        f"{cable_data['cable_slack']:.3f}",
                        f"{cable_data['total_length']:.2f}"
                    ])
    
    print(f"Generated cable length table: {output_file}")
