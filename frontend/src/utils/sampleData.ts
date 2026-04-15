/** Minimal but realistic sample YAML configuration for the "Load Example" button. */
export const SAMPLE_DATA = `
inter_rack_distance: 2.5
cable_slack_length: 0.2
front_to_back_length: 0.5
rail_extension_length: 0.5
standard_u_height: 0.045

cable_types:
  - Ethernet
  - Fibre
  - HDMI
  - SDI

type_colors:
  Switch:
    color: "#1f6feb"
    units: 1
  Patch panel:
    color: "#388bfd"
    units: 1
    ported: true
  Server:
    color: "#2ea043"
    units: 2
  PDU:
    color: "#d29922"
    units: 1
  UPS:
    color: "#6e40c9"
    units: 2
  Media:
    color: "#1b7c83"
    units: 1
  Encoder:
    color: "#c0392b"
    units: 1
  Decoder:
    color: "#2980b9"
    units: 1

racks:
  - rack:
      id: rack1
      name: "Rack A"
      total_u: 42
      u_order: bottom_top
    front:
      - name: "Core Switch A"
        type: Switch
        start_u: 42
        units: 1
      - name: "PP-A {N}"
        type: Patch panel
        start_u: 40
        units: 1
        start: 1
        end: 2
        ports: 24
      - name: "Server {N}"
        type: Server
        start_u: 37
        units: 2
        start: 1
        end: 4
        spacing: 0
      - name: "UPS A"
        type: UPS
        start_u: 28
        units: 2
    rear:
      - name: "PDU A1"
        type: PDU
        start_u: 42
        units: 1
      - name: "PDU A2"
        type: PDU
        start_u: 41
        units: 1

  - rack:
      id: rack2
      name: "Rack B"
      total_u: 42
      u_order: bottom_top
    front:
      - name: "Core Switch B"
        type: Switch
        start_u: 42
        units: 1
      - name: "PP-B {N}"
        type: Patch panel
        start_u: 40
        units: 1
        start: 1
        end: 2
        ports: 24
      - name: "Encoder {N}"
        type: Encoder
        start_u: 38
        units: 1
        start: 1
        end: 3
      - name: "Decoder {N}"
        type: Decoder
        start_u: 34
        units: 1
        start: 1
        end: 3
    rear:
      - name: "PDU B1"
        type: PDU
        start_u: 42
        units: 1

external_devices:
  - name: "Operator Room"
    distance_from_racks: 15
    devices:
      - name: "Workstation {N}"
        type: Server
        start: 1
        end: 3
      - name: "Control Panel"
        type: Media

wiring_layers:
  - name: "Management Network"
    edge_color: "#1f6feb"
    cable_type: Ethernet
    connections:
      - from: "Core Switch A"
        to: "PP-A 1"
        via_patch_from: "PP-A 1"
      - from: "Core Switch A"
        to: "Core Switch B"
      - from: "Core Switch B"
        to: "PP-B 1"

  - name: "Video"
    edge_color: "#c0392b"
    cable_type: SDI
    connections:
      - from: "Encoder {N}"
        to: "Decoder {N}"
        start: 1
        end: 3
      - from: "Encoder 1"
        to: "Workstation 1"
      - from: "Decoder 1"
        to: "Control Panel"
`.trim()
