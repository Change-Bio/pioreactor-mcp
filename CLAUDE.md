# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Pioreactor plugin that implements an MCP (Model Context Protocol) server, allowing LLM clients to interact with Pioreactor hardware through a REST API bridge. The plugin enables remote control and monitoring of bioreactor experiments via AI assistants.

## Development Commands

### Installation and Setup
```bash
# Install the plugin directly on a Pioreactor
pio install-plugin pioreactor-MCP

# Install on all Pioreactors in a cluster (run from leader)
pios install-plugin pioreactor-MCP
```

### Running the Plugin
```bash
# Run the MCP server (job name is pioreactor_mcp, not pioreactor_MCP)
pio run pioreactor_mcp

# Check if MCP server is running
pio logs pioreactor_mcp

# Stop the MCP server
pio kill pioreactor_mcp

# Run with custom port
pio run pioreactor_mcp --port 9000
```

### Testing and Development
```bash
# Install in development mode
pip install -e .

# Build and test package
python -m build --wheel
pip install dist/pioreactor_MCP-*.whl
```

## Architecture

### Core Components

1. **MCP Server Background Job** (`pioreactor_MCP/pioreactor_MCP.py`):
   - `MCPServer` class inheriting from `pioreactor.background_jobs.base.BackgroundJob`
   - FastMCP-based server providing tools and resources for LLM interaction
   - Auto-starts on boot through Pioreactor's background job system
   - Runs MCP server in separate thread to avoid blocking the background job
   - Default port 8080, configurable via command line or config

2. **MCP Tools Implemented**:
   - `start_job(worker, job_name, experiment, settings)` - Start Pioreactor jobs
   - `stop_job(worker, job_name, experiment)` - Stop running jobs  
   - `update_job_settings(worker, job_name, experiment, settings)` - Update job parameters
   - `set_led_intensity(worker, experiment, channel, intensity)` - LED control shortcut
   - `set_stirring_speed(worker, experiment, rpm)` - Stirring control shortcut

3. **MCP Resources Implemented**:
   - `experiments` - Lists all experiments with status and metadata
   - `workers` - Lists all Pioreactor units and their current state
   - `job_schemas` - Available job types with parameter definitions for LLM guidance

4. **Configuration Integration**:
   - `additional_config.ini`: MCP server settings (port=8080, logging_level=INFO, auto_start=1)
   - Merged with main Pioreactor config during installation

5. **Web UI Integration**:
   - `ui/contrib/jobs/pioreactor_mcp.yaml`: Web interface for server control
   - Displays server status, port, logging level, active connections
   - Allows start/stop/restart operations and configuration changes

### Plugin Structure
- Entry point defined in setup.py: `"pioreactor.plugins": "pioreactor_MCP = pioreactor_MCP"`
- Click command: `click_pioreactor_mcp()` for CLI execution
- Job name: `pioreactor_mcp` (used in pio commands)
- Dependencies: mcp[cli], pioreactor>=23.6.0, requests

### Key Integrations
- **Background Job System**: Inherits from BackgroundJob for automatic lifecycle management
- **REST API**: Communicates with Pioreactor API at localhost:80/api/ endpoints
- **MQTT**: Can subscribe to real-time updates and publish status information
- **Configuration**: Dynamic config merging through additional_config.ini
- **Web UI**: Job control and monitoring through YAML definitions

## Pioreactor Platform Technical Details

### Background Job System
- **Base Class**: All background jobs inherit from `pioreactor.background_jobs.base.BackgroundJob`
- **Job States**: init → ready → sleeping → disconnected → lost
- **Auto-start**: Jobs can be configured to start automatically on boot
- **Lifecycle Methods**: `on_init_to_ready()`, `on_ready_to_sleeping()`, `on_disconnected()`
- **CLI Integration**: Use `@click.command()` with function names starting with `click_`

### REST API Structure
- **Base URL**: `http://leader.local/api/` or `http://localhost:80/api/`
- **Endpoints Pattern**: `/api/workers/{worker}/jobs/{action}/{job_name}/experiments/{experiment}`
- **Common Actions**: start, stop, pause, update_settings
- **Content-Type**: application/json for all requests
- **Methods**: PATCH for updates, GET for status, POST for creation

### Key API Endpoints
**IMPORTANT: Always check https://docs.pioreactor.com/developer-guide/web-ui-api for correct endpoints**

```
# Job Control (note: uses /units/ not /workers/)
PATCH /api/units/{unit}/jobs/run/job_name/{job}/experiments/{experiment}
PATCH /api/units/{unit}/jobs/stop/job_name/{job}/experiments/{experiment}
PATCH /api/units/{unit}/jobs/update/job_name/{job}/experiments/{experiment}

# Running Jobs Status
GET /api/units/{unit}/jobs/running
GET /api/units/{unit}/jobs/running/experiments/{experiment}

# Worker Management
GET /api/workers - List all workers
POST /api/workers - Add worker  
DELETE /api/workers/{unit} - Remove worker

# Examples:
# Start stirring: /api/units/pioreactor01/jobs/run/job_name/stirring/experiments/my_exp
# Update LED: /api/units/pioreactor01/jobs/update/job_name/led_intensity/experiments/my_exp
# Check running jobs: /api/units/pioreactor01/jobs/running
```

### Configuration System
- **Main Config**: `/home/pioreactor/.pioreactor/config.ini`
- **Plugin Config**: `additional_config.ini` merged during installation
- **Sections**: [job_name], [job_name.subconfig], etc.
- **Published Settings**: Expose configurable attributes via `published_settings`

### MQTT Integration
- **Broker**: Local MQTT broker on each Pioreactor
- **Topics**: `pioreactor/{unit}/{experiment}/{job_name}/{attribute}`
- **Real-time**: Subscribe to live data streams and state changes
- **Publishing**: Use `publish()` method to expose job attributes

### Hardware Abstraction
- **PWM Channels**: Mapped via `pioreactor.hardware.PWM_TO_PIN`
- **GPIO Control**: Through Pioreactor's hardware abstraction layer
- **Safety**: Optical density measurement dodging for critical operations

### Plugin Distribution
- **Package Name**: lowercase-with-dashes (pioreactor-mcp-server)
- **Module Name**: lowercase_with_underscores (pioreactor_MCP)
- **Entry Point**: `"pioreactor.plugins": "pioreactor_MCP = pioreactor_MCP"`
- **Installation**: `pio install-plugin` (single) or `pios install-plugin` (cluster)

### Web UI Integration
- **Jobs YAML**: Define UI controls, settings forms, and status displays
- **Job Control**: Start/stop/restart buttons and status indicators
- **Settings**: Form fields for configuration parameters
- **Monitoring**: Real-time status and metrics display

## MCP Interface Details

### Available Tools
The MCP server exposes these tools for LLM interaction:

- **start_job(worker, job_name, experiment, settings)** - Start any Pioreactor job
  - Examples: `stirring`, `led_intensity`, `temperature_automation`, `od_reading`
  - Settings parameter contains job-specific configuration
  
- **stop_job(worker, job_name, experiment)** - Stop running jobs
  
- **update_job_settings(worker, job_name, experiment, settings)** - Change parameters for active jobs
  
- **set_led_intensity(worker, experiment, channel, intensity)** - LED control shortcut
  - Channels: A, B, C, D
  - Intensity: 0-100%
  
- **set_stirring_speed(worker, experiment, rpm)** - Stirring control shortcut
  - RPM range: 0-2000

### Available Resources
The MCP server provides these resources for LLM context:

- **experiments** - JSON list of all experiments with status and metadata
- **workers** - JSON list of all Pioreactor units and their current state  
- **job_schemas** - Job definitions with parameter types, ranges, and descriptions

### Usage Examples
```bash
# Connect MCP client to server
# Default: localhost:8080 with streamable-http transport

# Example tool calls:
start_job("pioreactor01", "stirring", "my_experiment", {"target_rpm": 500})
set_led_intensity("pioreactor01", "my_experiment", "A", 75.0)
update_job_settings("pioreactor01", "temperature_automation", "my_experiment", {"target_temperature": 32.0})
```

## Important Notes

- The MCP server provides a potentially dangerous bridge between AI and hardware control
- Implements as a BackgroundJob for proper lifecycle management and auto-start
- REST API communication enables full experiment and hardware control
- Configuration changes affect entire Pioreactor cluster when installed via pios
- Web UI integration provides manual oversight and control capabilities
- All tool calls are synchronous and return success/error status with messages

## API Development Guidelines

**CRITICAL: Before implementing any API-related tools or making API calls, ALWAYS:**

1. **Check the official API documentation**: https://docs.pioreactor.com/developer-guide/web-ui-api
2. **Verify endpoint patterns**: Use `/api/units/` for job control, not `/api/workers/`
3. **Test API calls manually** using curl or the browser before implementing in code
4. **Follow the exact URL structure** shown in the docs (e.g., `/job_name/{job}` not `/{job}`)

**Common API Mistakes to Avoid:**
- Using `/api/workers/` instead of `/api/units/` for job control
- Missing `/job_name/` segment in job control URLs
- Assuming endpoint patterns without checking documentation
- Not handling HTTP status codes properly

**When in doubt, refer to the official docs first, not assumptions or examples from other projects.**

## Development Workflow

**Git Commit Guidelines:**
- After completing significant features or bug fixes, suggest creating git commits
- Use clear, descriptive commit messages following conventional commit format
- Break large changes into logical, focused commits
- Always test functionality before committing
- Suggest committing when:
  - A feature is complete and working
  - A bug has been fixed and verified
  - Documentation has been updated
  - Major refactoring is finished
  - Before switching to work on different functionality