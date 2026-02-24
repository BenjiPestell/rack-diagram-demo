import csv
import json

# -------------------------------------------------
# Export computer_info to CSV
# -------------------------------------------------
def export_computer_info_csv(computer_info, output_file="output/computer_info.csv"):
    """Export computer_info to CSV format"""
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Header
        writer.writerow([
            "Device Name",
            "Part Number",
            "Port #",
            "Adapter/Network",
            "MAC Address",
            "IP Address"
        ])
        
        # Data rows
        for device in computer_info:
            device_name = device.get("device_name", "")
            part_number = device.get("arena_part_number", "")
            ports = device.get("ethernet_ports", [])
            
            if not ports:
                writer.writerow([device_name, part_number, "", "", "", ""])
            else:
                for idx, port in enumerate(ports, 1):
                    writer.writerow([
                        device_name,
                        part_number,
                        idx,
                        port.get("adapter", ""),
                        port.get("mac", ""),
                        port.get("ip", "")
                    ])
    
    print(f"Exported computer_info to {output_file}")

# -------------------------------------------------
# Export computer_info to JSON
# -------------------------------------------------
def export_computer_info_json(computer_info, output_file="output/computer_info.json"):
    """Export computer_info to JSON format"""
    with open(output_file, 'w') as f:
        json.dump(computer_info, f, indent=2)
    
    print(f"Exported computer_info to {output_file}")

# -------------------------------------------------
# Export computer_info to HTML
# -------------------------------------------------
def export_computer_info_html(computer_info, output_file="output/computer_info.html"):
    """Export computer_info to HTML table"""
    html = """<!DOCTYPE html>
<html>
<head>
    <title>Computer Info</title>
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
        .device-name {
            font-weight: bold;
            color: #333;
        }
        .port-number {
            background-color: #f0f0f0;
            text-align: center;
            width: 60px;
        }
        .mac-address {
            font-family: monospace;
            font-size: 0.9em;
        }
        .ip-address {
            font-family: monospace;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <h1>Computer Info</h1>
    <table>
        <thead>
            <tr>
                <th>Device Name</th>
                <th>Part Number</th>
                <th>Port #</th>
                <th>Adapter/Network</th>
                <th>MAC Address</th>
                <th>IP Address</th>
            </tr>
        </thead>
        <tbody>
"""
    
    for device in computer_info:
        device_name = device.get("device_name", "")
        part_number = device.get("arena_part_number", "")
        ports = device.get("ethernet_ports", [])
        
        if not ports:
            html += f"""            <tr>
                <td class="device-name">{device_name}</td>
                <td>{part_number}</td>
                <td class="port-number">-</td>
                <td>-</td>
                <td class="mac-address">-</td>
                <td class="ip-address">-</td>
            </tr>
"""
        else:
            for idx, port in enumerate(ports, 1):
                html += f"""            <tr>
                <td class="device-name">{device_name}</td>
                <td>{part_number}</td>
                <td class="port-number">{idx}</td>
                <td>{port.get('adapter', '')}</td>
                <td class="mac-address">{port.get('mac', '')}</td>
                <td class="ip-address">{port.get('ip', '')}</td>
            </tr>
"""
    
    html += """        </tbody>
    </table>
</body>
</html>
"""
    
    with open(output_file, 'w') as f:
        f.write(html)
    
    print(f"Exported computer_info to {output_file}")