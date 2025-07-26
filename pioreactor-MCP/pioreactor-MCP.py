from mcp import MCPServer, tool

app = MCPServer(name="pi-mcp", description="Control tools on my Raspberry Pi")

@tool()
def read_temperature():
    return {"temperature": 21.5}

@tool()
def toggle_gpio(pin: int, state: bool):
    # Placeholder for GPIO control
    return {"pin": pin, "state": state, "status": "OK"}

app.run(host="0.0.0.0", port=9000)