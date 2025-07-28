# Pioreactor MCP Server Plugin

This Pioreactor plugin implements an MCP (Model Context Protocol) server that enables LLM clients to interact with Pioreactor hardware through a REST API bridge. The plugin allows AI assistants to control bioreactor experiments, monitor system status, and manage hardware operations.

⚠️ **Safety Warning**: This plugin provides direct AI control over physical hardware. Use with caution and appropriate safety measures.

## Features

- **Full Experiment Control**: Start, stop, and manage bioreactor experiments
- **Hardware Control**: LED intensity, stirring speed, temperature automation, and more
- **Real-time Monitoring**: Access to system status, sensor readings, and job states
- **Job Management**: Control any Pioreactor background job with parameter updates
- **Web UI Integration**: Monitor and control the MCP server through Pioreactor's web interface
- **Auto-start**: Automatically starts on boot as a Pioreactor background job

## Installation

### From Command Line
```bash
# Install directly on a single Pioreactor
pio install-plugin pioreactor-MCP

# Install on all Pioreactors in a cluster (run from leader)
pios install-plugin pioreactor-MCP
```

### From Web Interface
Install through the Pioreactor web interface (_Plugins_ tab). This will install the plugin on all Pioreactors within the cluster.

### Configuration
The plugin includes default configuration that should work out of the box:

```ini
[pioreactor_mcp.config]
port=8080
logging_level=INFO
auto_start=1
```

To customize settings, edit your Pioreactor's configuration file or use the web interface.

## Usage

### Command Line
```bash
# Start the MCP server
pio run pioreactor_mcp

# Start with custom port
pio run pioreactor_mcp --port 9000

# Check server status
pio logs pioreactor_mcp

# Stop the server
pio kill pioreactor_mcp
```

### Web Interface
Under _Manage_ → _Activities_, you'll find the _MCP Server_ option with settings for:
- Server port configuration
- Logging level control
- Connection monitoring
- Server status display

### MCP Client Connection
The server runs on `streamable-http` transport at `localhost:8080` (or your configured port).

## MCP Tools Available

### Job Control
- `start_job(worker, job_name, experiment, settings)` - Start any Pioreactor job
- `stop_job(worker, job_name, experiment)` - Stop running jobs
- `update_job_settings(worker, job_name, experiment, settings)` - Update job parameters

### Hardware Shortcuts
- `set_led_intensity(worker, experiment, channel, intensity)` - Control LED channels (A-D, 0-100%)
- `set_stirring_speed(worker, experiment, rpm)` - Control stirring (0-2000 RPM)

## MCP Resources Available

- `experiments` - List all experiments with status and metadata
- `workers` - List all Pioreactor units and their current state
- `job_schemas` - Job definitions with parameter types and descriptions

## Example Usage

```python
# Example MCP tool calls from an LLM client:
start_job("pioreactor01", "stirring", "my_experiment", {"target_rpm": 500})
set_led_intensity("pioreactor01", "my_experiment", "A", 75.0)
update_job_settings("pioreactor01", "temperature_automation", "my_experiment", {"target_temperature": 32.0})
```

## Requirements

- Pioreactor software ≥ 23.6.0
- Python packages: `mcp[cli]`, `requests`
- Network access for Tailscale/tailnet (recommended for security)

## Development

For development and customization, see the [developer documentation](https://docs.pioreactor.com/developer-guide/intro-plugins) and the project's `CLAUDE.md` file for implementation details.

## Safety Considerations

This plugin enables direct AI control of physical hardware. Consider implementing:
- Proper prompt engineering for AI safety
- Network security through Tailscale/VPN
- Monitoring and logging of all AI actions
- Hardware safety interlocks where appropriate
- Testing in safe environments before production use