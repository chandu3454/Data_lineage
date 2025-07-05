import streamlit as st
import pandas as pd
from collections import defaultdict
import streamlit.components.v1 as components

# Load Excel
input_xlsx = "Input_tables.xlsx"
output_xlsx = "Output_tables.xlsx"
input_sheets = pd.read_excel(input_xlsx, sheet_name=None)
output_sheets = pd.read_excel(output_xlsx, sheet_name=None)

# Build input table columns
input_table_columns = {
    name.lower(): df["Input_columns"].dropna().tolist()
    for name, df in input_sheets.items()
}

# Build lineage, rules, examples
lineage_data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
transformation_rules = defaultdict(lambda: defaultdict(dict))
sample_examples = defaultdict(lambda: defaultdict(dict))

for sheet, df in output_sheets.items():
    for _, row in df.iterrows():
        out_col = str(row["Output_columns"]).strip()
        sor_id = str(row["Sor_id"]).strip()
        input_refs = str(row["Input_table_col_name"]).split("\n")
        rule = str(row.get("Tranformation_rule", "")).strip()
        example = str(row.get("Sample_examples", "")).strip()
        for ref in input_refs:
            if '.' in ref:
                table, col = ref.strip().lower().split('.', 1)
                if table in input_table_columns:
                    lineage_data[sheet][sor_id][out_col].append((table, col))
        transformation_rules[sheet][sor_id][out_col] = rule
        sample_examples[sheet][sor_id][out_col] = example

# UI
st.set_page_config(layout="wide")
st.title("🧬 Data Lineage Viewer")

output_tables = list(lineage_data.keys())
col1, col2 = st.columns([1, 1])
with col2:
    selected_output = st.selectbox("Select Output Table", output_tables)
with col1:
    sor_ids = list(lineage_data[selected_output].keys())
    selected_sor_id = st.selectbox("Select Sor_id", sor_ids)

lineage_map = lineage_data[selected_output][selected_sor_id]
rules = transformation_rules[selected_output][selected_sor_id]
examples = sample_examples[selected_output][selected_sor_id]
output_columns = list(lineage_map.keys())

# Layout constants
start_y, row_height, box_width = 60, 35, 250
input_x, output_x = 50, 700
svg_width = 1700

input_tables = {tbl for refs in lineage_map.values() for tbl, _ in refs}
input_columns = {tbl: input_table_columns[tbl] for tbl in input_tables}
input_positions, input_svg_blocks, input_rects, paths = {}, [], [], []
current_y = start_y

# Draw input tables
for tbl, cols in input_columns.items():
    y_offset, col_elems = 0, []
    for col in cols:
        col_id = f"{tbl}_{col}"
        y = current_y + y_offset * row_height
        input_positions[col_id] = (input_x + 120, y)
        input_rects.append(f'<rect x="{input_x + 10}" y="{y - 15}" width="230" height="20" id="bg_{col_id}" style="fill:none;"></rect>')
        col_elems.append(f'<text x="{input_x + 20}" y="{y}" class="col-text" id="{col_id}">{col}</text>'
                         f'<tspan x="{input_x + 220}" y="{y - 10}" class="copy-btn" onclick="navigator.clipboard.writeText(\"{col}\")">📋</tspan>')
        y_offset += 1
    height = len(cols) * row_height + 40
    input_svg_blocks.append(f'''<rect x="{input_x}" y="{current_y - 30}" width="{box_width}" height="{height}" class="box" rx="10" ry="10"/>
        <text x="{input_x + box_width // 2}" y="{current_y - 40}" text-anchor="middle" font-size="16" fill="#fff">{tbl.title()}</text>
        {''.join(col_elems)}''')
    current_y += height + 60

svg_height = max(current_y, start_y + len(output_columns) * row_height + 300) + 300

# Output columns + paths
output_elems, output_positions = [], {}
for j, out_col in enumerate(output_columns):
    y = start_y + j * row_height
    output_positions[out_col] = y
    rule = rules.get(out_col, "")
    example = examples.get(out_col, "")
    output_elems.append(
        f'<text x="{output_x + 20}" y="{y}" class="col-text" onclick="toggleOutput(\'{out_col}\')" id="{out_col}" '
        f'data-rule="{rule}" data-example="{example}">{out_col}</text>'
        f'<tspan x="{output_x + 220}" y="{y - 10}" class="copy-btn" onclick="navigator.clipboard.writeText(\"{out_col}\")">📋</tspan>'
    )
    for in_tbl, in_col in lineage_map[out_col]:
        in_id = f"{in_tbl}_{in_col}"
        if in_id in input_positions:
            in_x, in_y = input_positions[in_id]
            cx = (in_x + output_x + 20) // 2
            path = f'M {in_x} {in_y} C {cx} {in_y}, {cx} {y}, {output_x + 20} {y}'
            paths.append(f'<path d="{path}" class="line hidden line-{out_col}" id="line_{in_tbl}_{in_col}_{out_col}" data-input="{in_id}"/>')

# Tooltip box spacing adjusted here
rule_box_top = start_y + len(output_columns) * row_height + 140
example_box_top = rule_box_top + 180

highlight_js = """
let selectedColumns = [];
const highlightColors = ['#66ff66', '#00ccff', '#ff66cc', '#ffcc00', '#cc66ff', '#ff6666'];

function toggleOutput(col) {
  const index = selectedColumns.indexOf(col);
  if (index > -1) {
    selectedColumns.splice(index, 1);
  } else {
    selectedColumns.push(col);
  }
  document.querySelectorAll(".col-text").forEach(el => el.style.fill = "#eee");
  document.querySelectorAll(".line").forEach(el => el.style.stroke = "#999");
  document.querySelectorAll(".line").forEach(el => el.classList.add("hidden"));
  document.querySelectorAll("rect[id^='bg_']").forEach(r => r.setAttribute("fill", "none"));

  let highlightedInputs = new Map();
  selectedColumns.forEach((c, i) => {
    const color = highlightColors[i % highlightColors.length];
    const elem = document.getElementById(c);
    if (elem) {
      elem.style.fill = color;
      document.querySelectorAll(`.line-${c}`).forEach(p => {
        p.classList.remove("hidden");
        p.style.stroke = color;
        const inputId = p.getAttribute("data-input");
        if (inputId) highlightedInputs.set(inputId, color);
      });
    }
  });

  highlightedInputs.forEach((color, id) => {
    const rect = document.getElementById("bg_" + id);
    const text = document.getElementById(id);
    if (rect) rect.setAttribute("fill", color);
    if (text) text.style.fill = color;
  });

  updateTooltipContent();
}

function clearSelection() {
  selectedColumns = [];
  document.querySelectorAll(".col-text").forEach(el => el.style.fill = "#eee");
  document.querySelectorAll(".line").forEach(el => el.classList.add("hidden"));
  document.querySelectorAll(".line").forEach(el => el.style.stroke = "#999");
  document.querySelectorAll("rect[id^='bg_']").forEach(r => r.setAttribute("fill", "none"));
  document.getElementById("ruleBox").style.display = "none";
  document.getElementById("exampleBox").style.display = "none";
}

function updateTooltipContent() {
  const ruleBox = document.getElementById("ruleBox");
  const exampleBox = document.getElementById("exampleBox");
  if (selectedColumns.length === 0) {
    ruleBox.style.display = "none";
    exampleBox.style.display = "none";
    return;
  }
  let ruleContent = "";
  let exampleContent = "";
  selectedColumns.forEach(col => {
    const elem = document.getElementById(col);
    if (!elem) return;
    const rule = elem.getAttribute("data-rule") || "";
    const example = elem.getAttribute("data-example") || "";
    if (rule) ruleContent += `\n🟡 Output Column: ${col}\n- Rule: ${rule}\n`;
    if (example) exampleContent += `\n🟡 Output Column: ${col}\n- Example: ${example}\n`;
  });
  document.getElementById("ruleText").textContent = ruleContent.trim();
  document.getElementById("exampleText").textContent = exampleContent.trim();
  ruleBox.style.display = ruleContent ? "block" : "none";
  exampleBox.style.display = exampleContent ? "block" : "none";
}
"""

# HTML with tooltip and reset button
html = f"""
<html><head>
  <style>
    body {{ background: #111; color: white; font-family: sans-serif; overflow-x: auto; position: relative; }}
    .box {{ fill: #1e1e1e; stroke: #555; stroke-width: 2; }}
    .col-text {{ cursor: pointer; font-size: 14px; fill: #eee; }}
    .line {{ fill: none; stroke: #999; stroke-width: 2; }}
    .line.hidden {{ visibility: hidden; }}
    .tooltip-box {{ position: absolute; left: {output_x}px; width: 350px; background: #222; border: 1px solid #00ffcc; border-radius: 10px; padding: 10px; color: white; overflow-y: auto; }}
    #ruleBox {{ top: {start_y + len(output_columns)*row_height + 100}px; max-height: 130px; display: none; }}
    #exampleBox {{ top: {start_y + len(output_columns)*row_height + 300}px; max-height: 130px; display: none; }}
    .copy-btn {{ cursor: pointer; font-size: 14px; margin-left: 8px; }}
    .top-bar {{ margin: 10px 20px 20px 0; text-align: right; }}
  </style>
</head><body>
  <div class="top-bar">
    <button onclick="clearSelection()" style="background-color:#444; color:white; border:1px solid #00ffcc; border-radius:5px; padding:5px 10px; cursor:pointer;">
      🔄 Reset
    </button>
  </div>
  <svg width="{svg_width}" height="{svg_height}">
    {''.join(input_svg_blocks)}
    {''.join(input_rects)}
    <rect x="{output_x}" y="30" width="250" height="{len(output_columns)*row_height + 40}" class="box" rx="10" ry="10"/>
    <text x="{output_x + 125}" y="20" text-anchor="middle" font-size="16" fill="#fff">{selected_output}</text>
    {''.join(output_elems)}
    {''.join(paths)}
  </svg>
  <div id="ruleBox" class="tooltip-box">
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <strong style="color:#00ffcc;">Transformation Rule</strong>
      <span class="copy-btn" onclick="navigator.clipboard.writeText(document.getElementById('ruleText').textContent)" title="Copy to clipboard">📋</span>
    </div>
    <div id="ruleText" style="white-space:pre-wrap; margin-top:5px;"></div>
  </div>
  <div id="exampleBox" class="tooltip-box">
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <strong style="color:#00ffcc;">Sample Example</strong>
      <span class="copy-btn" onclick="navigator.clipboard.writeText(document.getElementById('exampleText').textContent)" title="Copy to clipboard">📋</span>
    </div>
    <div id="exampleText" style="white-space:pre-wrap; margin-top:5px;"></div>
  </div>
  <script>{highlight_js}</script>
</body></html>
"""

# Display final lineage HTML
components.html(html, height=svg_height + 1000, scrolling=True)
