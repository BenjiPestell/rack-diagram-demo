import math
import os
import csv
import json
import re
import glob
from collections import defaultdict
from math import sqrt

from utils import load_config, get_device_color
from wiring_diagram import generate_wiring_diagram
from cable_length import generate_cable_length_table, generate_cable_length_html, generate_cable_summary_csv, generate_cable_summary_html
from clusters import expand_computer_info_clusters, expand_external_devices, expand_clusters, expand_wiring_clusters
from rack_layout import generate_rack_layout_dot, build_device_map, build_occupancy
from computer_info import export_computer_info_csv, export_computer_info_json, export_computer_info_html
from patch_panel import collect_patch_assignments, generate_patch_panel_dot


# -------------------------------------------------
# Clean output directory
# -------------------------------------------------
def clean_output():
    """Delete all generated files from the output directory before regenerating."""
    if not os.path.exists("output"):
        return

    patterns = [
        "output/*.dot",
        "output/*.png",
        "output/*.svg",
        "output/*.csv",
        "output/*.html",
        "output/*.json",
    ]

    deleted = 0
    for pattern in patterns:
        for path in glob.glob(pattern):
            try:
                os.remove(path)
                deleted += 1
            except OSError as e:
                print(f"Warning: could not delete {path}: {e}")

    if deleted:
        print(f"Cleaned {deleted} file(s) from output/")

# -------------------------------------------------
# Clean PNG directory
# -------------------------------------------------
def clean_png():
    """Delete all generated PNG files from the png directory."""
    if not os.path.exists("pngs"):
        return

    pattern = "pngs/*.png"
    deleted = 0
    for path in glob.glob(pattern):
        try:
            os.remove(path)
            deleted += 1
        except OSError as e:
            print(f"Warning: could not delete {path}: {e}")

    if deleted:
        print(f"Cleaned {deleted} PNG file(s) from pngs/")


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
    
    # Create output directory and clean stale files
    if not os.path.exists("output"):
        os.mkdir("output")
    clean_output()
    clean_png()

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
        
        # Generate patch panel schedule diagrams
        pp_assignments = collect_patch_assignments(racks_config, layers)
        for panel_name, (port_count, assignments) in pp_assignments.items():
            safe_name = re.sub(r"[^a-z0-9]+", "_", panel_name.lower()).strip("_")
            filename = f"output/{safe_name}.dot"
            dot_content = generate_patch_panel_dot(panel_name, port_count, assignments, type_colors)
            with open(filename, "w", encoding="utf-8") as f:
                f.write(dot_content)
            print(f"Generated {filename} ({port_count} ports, {len(assignments)} assigned)")

        # Generate cable length tables
        generate_cable_length_table(all_devices, racks_config, layers, cable_config)
        generate_cable_length_html(all_devices, racks_config, layers, cable_config)
        generate_cable_summary_csv(all_devices, racks_config, layers, config)
        generate_cable_summary_html(all_devices, racks_config, layers, config)
        
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