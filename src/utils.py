import yaml
import colorsys

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

# -------------------------------------------------
# Color utilities
# -------------------------------------------------

def hex_to_color_name(hex_color):
    """
    Convert hex color code to a human-friendly color name
    using HSV color space (closer to human perception).
    """

    if not hex_color:
        return "Unknown"

    hex_color = hex_color.lstrip("#")

    # Already a name
    if not all(c in "0123456789ABCDEFabcdef" for c in hex_color):
        return hex_color.capitalize()

    # Expand shorthand
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)

    if len(hex_color) != 6:
        return "Unknown"

    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
    except ValueError:
        return "Unknown"

    # Normalize to 0–1
    r, g, b = r / 255, g / 255, b / 255

    # Convert to HSV
    h, s, v = colorsys.rgb_to_hsv(r, g, b)

    h = h * 360  # degrees

    # Grayscale detection
    if s < 0.15:
        if v < 0.2:
            return "Black"
        elif v > 0.9:
            return "White"
        else:
            return "Gray"

    # Color classification by hue
    if h < 15 or h >= 345:
        return "Red"
    elif h < 45:
        return "Orange"
    elif h < 65:
        return "Yellow"
    elif h < 150:
        return "Green"
    elif h < 200:
        return "Cyan"
    elif h < 260:
        return "Blue"
    elif h < 290:
        return "Purple"
    elif h < 330:
        return "Magenta"
    else:
        return "Red"