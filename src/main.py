import math
import os
import csv
import json
import re
from collections import defaultdict
from math import sqrt

from utils import load_config, get_device_color
from wiring_diagram import generate_wiring_diagram
from cable_length import generate_cable_length_table, generate_cable_length_html
from clusters import expand_computer_info_clusters, expand_external_devices, expand_clusters, expand_wiring_clusters
from rack_layout import generate_rack_layout_dot, build_device_map, build_occupancy
from computer_info import export_computer_info_csv, export_computer_info_json, export_computer_info_html


# -------------------------------------------------
# Main
# -------------------------------------------------
def main():
    config = load_config()
    
    # Extract type color mappings from config
    type_colors = config.get("type_colors", {})
    
    # Get cable length calculation parameters from config
    cable_config = {
        "cable_slack_length": config.get("cable_slack_length", 0.2),
        "standard_u_height": config.get("standard_u_height", 0.045),
        "front_to_back_length": config.get("front_to_back_length", 0.5),
        "inter_rack_distance": config.get("inter_rack_distance", 2.5)
    }
    
    # Create output directory if it doesn't exist
    if not os.path.exists("output"):
        os.mkdir("output")
    
    if "racks" in config:
        racks_config = config["racks"]
        external_devices_config = config.get("external_devices", [])
        
        all_devices = build_device_map(racks_config, external_devices_config)
        
        # Generate single comprehensive layout
        layout_dot = generate_rack_layout_dot(racks_config, type_colors)
        with open("output/rack_layout.dot", "w") as f:
            f.write(layout_dot)
        print("Generated output/rack_layout.dot")
        
        # Build device map for wiring (from both front and rear + external)
        all_devices = {}
        
        # Add rack devices
        for rack_config in racks_config:
            rack_id = rack_config["rack"].get("id", "rack")
            
            for side in ['front', 'rear']:
                if side in rack_config:
                    devices = expand_clusters(rack_config[side])
                    for dev in devices:
                        dev["rack_id"] = rack_id
                        dev["side"] = side
                        all_devices[dev["name"]] = dev
        
        # Add external devices (organized by group)
        if external_devices_config:
            expanded_ext_devices = expand_external_devices(external_devices_config)
            for group_name, devices in expanded_ext_devices.items():
                for dev in devices:
                    dev_copy = dev.copy()
                    dev_copy["rack_id"] = "external"
                    dev_copy["external_group"] = group_name
                    all_devices[dev["name"]] = dev_copy
        
        external_device_count = len(all_devices) - sum(len(expand_clusters(rack_config.get(side, []))) 
                                                        for rack_config in racks_config 
                                                        for side in ['front', 'rear'])
        print(f"Device map built with {len(all_devices)} devices ({external_device_count} external)")

        layers = config.get("wiring_layers", [])
        for layer in layers:
            layer_name = layer["name"]
            safe_name = layer_name.replace(" ", "_").replace("/", "_").lower()
            filename = f"output/{safe_name}.dot"
            
            wiring_dot = generate_wiring_diagram(layer, all_devices, type_colors)
            with open(filename, "w") as f:
                f.write(wiring_dot)
            print(f"Generated {filename}")
        
        # Generate cable length table
        generate_cable_length_table(all_devices, racks_config, layers, cable_config)
        generate_cable_length_html(all_devices, racks_config, layers, cable_config)
        
        # Process computer_info
        computer_info_raw = config.get("computer_info", [])
        if computer_info_raw:
            # Expand clusters
            computer_info = expand_computer_info_clusters(computer_info_raw)
            print(f"Expanded computer_info from {len(computer_info_raw)} entries to {len(computer_info)} devices")
            
            # Export
            export_computer_info_csv(computer_info)
            # export_computer_info_json(computer_info)
            export_computer_info_html(computer_info)
    
    else:
        print("Error: Configuration must have 'racks' with consolidated front/rear")
        return

if __name__ == "__main__":
    main()