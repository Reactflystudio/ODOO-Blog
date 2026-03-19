import traceback
import sys
try:
    import web.server
    with open("c:/Users/ReactFlow/Documents/ALEXANDRE/NEUBER/EMPURRAO DIGITAL/ODOO/test_out.txt", "w") as f:
        f.write("OK: web.server loaded")
except Exception as e:
    with open("c:/Users/ReactFlow/Documents/ALEXANDRE/NEUBER/EMPURRAO DIGITAL/ODOO/test_out.txt", "w") as f:
        f.write("Error: " + str(e) + "\n" + traceback.format_exc())
