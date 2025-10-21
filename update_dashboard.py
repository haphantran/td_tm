#!/usr/bin/env python3
"""
Update dashboard.html with latest data from data/dashboard_data.json
Run this script after generating new data with generate_data.py
"""

import json

# Read the data
with open('data/dashboard_data.json', 'r') as f:
    data = json.load(f)

# Read the original HTML
with open('dashboard.html', 'r') as f:
    html_content = f.read()

# Find the embedded data and replace it
start_marker = "const EMBEDDED_DASHBOARD_DATA = "
end_marker = ";\n    </script>"

start_idx = html_content.find(start_marker)
if start_idx == -1:
    print("Error: Could not find embedded data marker")
    exit(1)

end_idx = html_content.find(end_marker, start_idx)
if end_idx == -1:
    print("Error: Could not find end of embedded data")
    exit(1)

# Replace the data
new_data_js = f"{start_marker}{json.dumps(data)}"
html_content = html_content[:start_idx] + new_data_js + html_content[end_idx:]

# Write back
with open('dashboard.html', 'w') as f:
    f.write(html_content)

print("✓ Updated dashboard.html with new data")
print(f"✓ Embedded {len(data['threat_models'])} threat models")
print(f"✓ Embedded {len(data['applications'])} applications")
print(f"✓ Embedded {len(data['threats'])} threats")
