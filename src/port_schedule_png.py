"""
Generate a Graphviz DOT file that renders as a port-schedule PNG.

Each ported device gets a dark-themed grid: port number + source -> destination
for every assigned port.  Empty ports are shown as dim placeholders.
"""

import math
import re


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _esc(s):
    """Escape HTML special chars for Graphviz HTML labels."""
    if s is None:
        return ""
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _trunc(s, n):
    s = str(s)
    return s if len(s) <= n else s[: n - 1] + "\u2026"


def _wrap_html(s, chars=14):
    """Split s into ≤chars-char chunks joined by HTML <BR/>, each chunk escaped."""
    s = str(s)
    chunks = [s[i:i + chars] for i in range(0, len(s), chars)]
    return '<BR/>'.join(_esc(c) for c in chunks)


# ---------------------------------------------------------------------------
# DOT generator
# ---------------------------------------------------------------------------

def generate_port_schedule_dot(device_name, schedule):
    """
    Build a Graphviz DOT string for the port schedule PNG.

    schedule : OrderedDict  port_num (int) -> entry dict
      entry keys: connected_device, patch_src, patch_dst,
                  layer_color, interface_label, overflow
    """
    ports = list(schedule.items())
    n_ports = len(ports)
    if n_ports == 0:
        return None

    cols = 6 if n_ports <= 12 else 12 if n_ports <= 24 else 16

    # ── Cell builder ────────────────────────────────────────────────────────
    def _cell(port_num, entry):
        peer     = entry.get("connected_device")
        psrc     = entry.get("patch_src")
        pdst     = entry.get("patch_dst")
        color    = entry.get("layer_color") or "#3a3f47"
        note     = entry.get("interface_label") or ""
        overflow = entry.get("overflow", False)

        if peer is not None:
            # Patch panel port: show full source -> destination path
            if psrc and pdst:
                line1 = psrc
                line2 = pdst
            else:
                line1 = peer
                line2 = ""

            bg     = "#3d1a1a" if overflow else "#1c2128"
            border = color
            n_col  = "#8b949e"
            t_col  = "#c9d1d9"
            s_col  = "#6e7681"

            content = (
                f'<FONT POINT-SIZE="8" COLOR="{n_col}"><B>{port_num}</B></FONT><BR/>'
                f'<FONT POINT-SIZE="7" COLOR="{color}">&#9679;</FONT><BR/>'
                f'<FONT POINT-SIZE="8" COLOR="{t_col}">{_wrap_html(line1)}</FONT>'
            )
            if line2:
                content += f'<BR/><FONT POINT-SIZE="8" COLOR="{s_col}">{_wrap_html(line2)}</FONT>'
            if note:
                content += f'<BR/><FONT POINT-SIZE="7" COLOR="#484f58"><I>{_esc(note)}</I></FONT>'

        else:
            bg     = "#0d1117"
            border = "#21262d"
            n_col  = "#484f58"
            s_col  = "#484f58"

            content = f'<FONT POINT-SIZE="8" COLOR="{n_col}">{port_num}</FONT>'
            if note:
                content += f'<BR/><FONT POINT-SIZE="7" COLOR="{s_col}">{_esc(note)}</FONT>'

        return (
            f'<TD WIDTH="80" HEIGHT="40" BGCOLOR="{bg}" '
            f'BORDER="1" COLOR="{border}" ALIGN="CENTER" VALIGN="MIDDLE">'
            f'{content}'
            f'</TD>'
        )

    # ── Build grid rows ──────────────────────────────────────────────────────
    empty_cell = (
        '<TD WIDTH="80" HEIGHT="40" BGCOLOR="#0d1117" '
        'BORDER="1" COLOR="#21262d" ALIGN="CENTER" VALIGN="MIDDLE">'
        '<FONT POINT-SIZE="8" COLOR="#21262d"> </FONT>'
        '</TD>'
    )

    rows_html = []
    for row_start in range(0, n_ports, cols):
        chunk = ports[row_start: row_start + cols]
        cells = [_cell(pn, entry) for pn, entry in chunk]
        # Pad last row to full width
        cells += [empty_cell] * (cols - len(cells))
        rows_html.append("      <TR>" + "".join(cells) + "</TR>")

    grid_rows = "\n".join(rows_html)

    # ── DOT source ───────────────────────────────────────────────────────────
    dot = f"""\
digraph ports {{
  graph [bgcolor="#0d1117", pad=0.4, splines=false, rankdir=TB]
  node  [shape=plaintext, fontname="Courier New"]
  edge  [style=invis]

  title [label=<
    <TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="8">
      <TR><TD ALIGN="LEFT">
        <FONT POINT-SIZE="18" COLOR="#c9d1d9"><B>{_esc(device_name)}</B></FONT>
      </TD></TR>
      <TR><TD ALIGN="LEFT">
        <FONT POINT-SIZE="9" COLOR="#484f58">PORT ASSIGNMENT  &#183;  {n_ports} port{"s" if n_ports != 1 else ""}</FONT>
      </TD></TR>
    </TABLE>
  >]

  grid [label=<
    <TABLE BORDER="0" CELLBORDER="1" CELLSPACING="2" CELLPADDING="0"
           BGCOLOR="#0d1117" COLOR="#21262d">
{grid_rows}
    </TABLE>
  >]

  title -> grid
}}
"""
    return dot
