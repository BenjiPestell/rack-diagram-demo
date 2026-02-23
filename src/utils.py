import yaml

# -------------------------------------------------
# Load config
# -------------------------------------------------
def load_config():
    with open("system.yaml") as f:
        return yaml.safe_load(f)

# -------------------------------------------------
# Get device color based on type or explicit color
# -------------------------------------------------
def get_device_color(device, type_colors):
    """
    Determine device color with priority:
    1. Explicit 'color' attribute in device
    2. Color based on device 'type' from type_colors mapping
    3. Default white if neither specified
    """
    if "color" in device:
        return device["color"]
    
    if "type" in device:
        device_type = device["type"]
        if device_type in type_colors:
            return type_colors[device_type]
    
    return "#FFFFFF"