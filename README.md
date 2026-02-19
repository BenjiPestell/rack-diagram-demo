# Rack Infrastructure and Wiring Diagram Generator

This tool parses a single system definition file (`system.yaml`) to
produce:

-   Physical rack elevation diagrams (front and rear)
-   Logical network and power wiring diagrams
-   Detailed device inventory exports

All system information is maintained in one structured configuration
file, ensuring consistency between documentation, wiring, and hardware
deployment.

------------------------------------------------------------------------

## Features

-   **Automated Rack Elevations**\
    Generates Graphviz DOT files for multi-rack layouts with color-coded
    devices.

-   **Layered Wiring Diagrams**\
    Produces logical connection maps for power, visuals, host, and
    corporate networks.

-   **Dynamic Cluster Expansion**\
    Uses `{N}` placeholders to define ranges of devices, connections,
    and IP addresses.

-   **Inventory Export**\
    Creates CSV and HTML reports containing part numbers and network
    details.

-   **Single Source of Truth**\
    Rack layout, wiring, and inventory are all derived from
    `system.yaml`.

------------------------------------------------------------------------

## Prerequisites

To run the generator, you will need:

-   Python 3.x
-   PyYAML
-   Graphviz

Graphviz is required to render `.dot` files into PNG or PDF images.

------------------------------------------------------------------------

## Project Structure

Typical layout:

``` text
project/
├── system.yaml
├── generate.py
└── output/
```

Generated files are written to the `output/` directory.

------------------------------------------------------------------------

## Configuration (`system.yaml`)

All configuration is stored in `system.yaml`.\
The main sections are:

-   `type_colors` --- Device styling
-   `racks` --- Physical rack layout
-   `wiring_layers` --- Logical connections
-   `computer_info` --- Inventory data

------------------------------------------------------------------------

## 1. Device Type Colors (`type_colors`)

Each device type maps to a color used in diagrams.

Example:

``` yaml
type_colors:
  pc: "#E8F4F8"
  pdu: "#AAAAAA"
  Shelf: "#ced3db"
  realtime: "#FFE8D8"
  cable management: "#C4C4C4"
  switch: "#B8D6D6"
  customer: "#ffd9d6"
```

These names must match the `type` field used in rack definitions.

Example:

``` yaml
- name: Operator PC
  type: pc
```

------------------------------------------------------------------------

## 2. Rack Definitions (`racks`)

Each rack is defined as an entry in the `racks` list.

### 2.1 Basic Rack Definition

``` yaml
- rack:
    id: rack1
    name: Rack 1
    total_u: 42
```

  Field     Description
  --------- --------------------------
  id        Unique rack identifier
  name      Display name
  total_u   Rack height in units (U)

Each rack may contain:

-   `front` --- Front-mounted devices
-   `rear` --- Rear-mounted devices

------------------------------------------------------------------------

### 2.2 Standard Devices

Devices occupying rack space define their position and size.

Example:

``` yaml
- name: Operator PC
  start_u: 27
  units: 4
  type: pc
```

  Field     Description
  --------- -----------------------------
  name      Device name
  start_u   Topmost rack unit
  units     Height in rack units
  type      Device type (color mapping)

Rack units count downward from the top.

------------------------------------------------------------------------

### 2.3 Clustered Devices (`{N}` Expansion)

Repeated devices can be defined using placeholders.

Example:

``` yaml
- name: "IG {N}"
  start_u: 8
  start: 1
  end: 2
  units: 4
  spacing: 0
  type: pc
```

Expands to:

``` text
IG 1
IG 2
```

  Field     Description
  --------- -----------------------
  start     First index
  end       Last index
  spacing   Gap between units (U)

Clusters simplify configuration for large identical systems.

------------------------------------------------------------------------

### 2.4 Non-Positioned Devices

Some devices are logical only and do not occupy rack space.

Example:

``` yaml
- name: Vertical PDU 1
  type: pdu

- name: Mains in 1
  type: pdu
```

These appear in wiring diagrams but not in rack elevations.

------------------------------------------------------------------------

## 3. Wiring Layers (`wiring_layers`)

Wiring layers define logical connections between devices.

Each layer becomes a separate diagram.

Example:

``` yaml
- name: Visuals Subnet
  edge_color: "#b551a9"
  connections:
```

  Field         Description
  ------------- -----------------------
  name          Layer name
  edge_color    Link color (optional)
  connections   Connection list

------------------------------------------------------------------------

### 3.1 Simple Connections

``` yaml
- from: Graphics Switch 1
  to: Operator PC
```

Creates a direct link between two devices.

------------------------------------------------------------------------

### 3.2 Cluster Connections

``` yaml
- from: Graphics Switch 2
  to: "RVD {N}"
  start: 1
  end: 3
```

Expands to:

``` text
Graphics Switch 2 → RVD 1
Graphics Switch 2 → RVD 2
Graphics Switch 2 → RVD 3
```

------------------------------------------------------------------------

### 3.3 Offset and Daisy-Chain Connections

Arithmetic expressions may be used.

Example:

``` yaml
- from: "Graphics Switch {N}"
  to: "Graphics Switch {N+1}"
  start: 1
  end: 3
```

Expands to:

``` text
GS1 → GS2 → GS3 → GS4
```

This is useful for stacked switches and serial links.

------------------------------------------------------------------------

### 3.4 Power Distribution Example

``` yaml
- from: Vertical PDU 1
  to: R1 16A PDU A

- from: R1 16A PDU C
  to: Graphics Switch 1
```

Models:

``` text
Mains → Vertical PDU → Rack PDUs → Devices
```

Allowing complete power-path tracing.

------------------------------------------------------------------------

## 4. Computer Inventory (`computer_info`)

Defines technical metadata for devices.

Example:

``` yaml
- device_name: "Operator PC"
  arena_part_number: "902-00008"
  ethernet_ports:
```

  Field               Description
  ------------------- ----------------------
  device_name         Must match rack name
  arena_part_number   Internal part number
  ethernet_ports      NIC definitions

------------------------------------------------------------------------

### 4.1 Ethernet Ports

``` yaml
ethernet_ports:
  - adapter: "rFpro"
    ip: "192.168.2.80"
    mac: "00-14-5E-EA-4C-DC"
```

  Field     Description
  --------- ----------------
  adapter   Interface name
  ip        IP address
  mac       MAC address

------------------------------------------------------------------------

### 4.2 Clustered Inventory Entries

Inventory also supports `{N}` expansion.

``` yaml
- device_name: "IG {N}"
  start: 1
  end: 13
  ethernet_ports:
    - adapter: "rFpro"
      ip: "192.168.2.{N+10}"
```

Expands to:

``` text
IG 1 → 192.168.2.11
IG 2 → 192.168.2.12
...
IG 13 → 192.168.2.23
```

This keeps naming, wiring, and IP addressing synchronized.

------------------------------------------------------------------------

## 5. Naming Consistency (Critical)

All references are matched by device name.

Example:

``` yaml
- name: Operator PC
- device_name: "Operator PC"
- to: Operator PC
```

If names differ, wiring and inventory links will fail.

------------------------------------------------------------------------

## Usage

1.  Create or edit `system.yaml`.

2.  Run the generator:

    ``` bash
    python generate.py
    ```

3.  View results in the `output/` directory.

------------------------------------------------------------------------

## Output Files

Typical outputs:

-   `output/rack_layout.dot`\
    Full rack elevation diagram

-   `output/<layer>.dot`\
    Wiring diagrams per layer

-   `output/computer_info.csv`\
    Inventory table

-   `output/computer_info.html`\
    Inventory report

Rendered image formats depend on Graphviz.

------------------------------------------------------------------------

## Best Practices

-   Keep device names consistent
-   Use clusters for repeated hardware
-   Group wiring by function
-   Validate `system.yaml` after changes
-   Keep inventory entries aligned with rack devices

------------------------------------------------------------------------

## Summary

This generator provides a unified, automated way to:

-   Design multi-rack systems
-   Document physical layouts
-   Visualize power and networks
-   Manage large clustered systems
-   Maintain accurate inventories

All outputs are derived from a single configuration file, making the
system easy to maintain and scale.
