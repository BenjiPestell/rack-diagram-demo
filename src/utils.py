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
    
    result = "#FFFFFF"

# -------------------------------------------------
# Color utilities
# -------------------------------------------------

def hex_to_color_name(hex_color):
    """
    Convert hex color code to a human-friendly color name
    using HSV color space (closer to human perception).
    """

    if not hex_color:
        return "Unknown", "#FFFFFF"

    result = None    

    hex_color = hex_color.lstrip("#")

    # Already a name
    if not all(c in "0123456789ABCDEFabcdef" for c in hex_color):
        return hex_color.capitalize()

    # Expand shorthand
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)

    if len(hex_color) != 6:
        result = "Unknown"

    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
    except ValueError:
        result = "Unknown"

    # Normalize to 0–1
    r, g, b = r / 255, g / 255, b / 255

    # Convert to HSV
    h, s, v = colorsys.rgb_to_hsv(r, g, b)

    h = h * 360  # degrees

    # Grayscale detection
    if s < 0.25:
        if v < 0.2:
            result = "Black"
        elif v > 0.9:
            result = "White"
        else:
            result = "Grey"

    if not result:
        # Color classification by hue
        if h < 15 or h >= 345:
            result = "Red"
        elif h < 45:
            result = "Orange"
        elif h < 65:
            result = "Yellow"
        elif h < 150:
            result = "Green"
        elif h < 200:
            result = "Cyan"
        elif h < 260:
            result = "Blue"
        elif h < 290:
            result = "Purple"
        elif h < 330:
            result = "Magenta"
        else:
            result = "Red"

    return result, f"#{hex_color.upper()}"

print(hex_to_color_name("#323232"))