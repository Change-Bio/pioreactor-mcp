import threading
import time
import requests
import click
from mcp.server.fastmcp import FastMCP
from pioreactor.background_jobs.base import BackgroundJob
from pioreactor.config import config
from pioreactor.logging import create_logger
from pioreactor.whoami import am_I_leader, get_unit_name
from typing import Optional, Dict, Any, List


class MCPServer(BackgroundJob):
    """
    MCP Server for Pioreactor - provides Model Context Protocol interface
    for LLM interaction with Pioreactor hardware and experiments.
    """
    
    job_name = "pioreactor_mcp"
    
    def __init__(self, unit: str, experiment: str, port: int = 8000, **kwargs):
        super().__init__(unit=unit, experiment=experiment, **kwargs)
        self.port = port
        self.mcp_server = None
        self.server_thread = None
        self.api_base_url = "http://localhost:80/api"
        
        # Initialize FastMCP server
        self._setup_mcp_server()
        
    def _setup_mcp_server(self):
        """Initialize the FastMCP server with tools and resources."""
        self.mcp_server = FastMCP(
            name="pioreactor-mcp", 
            description="Pioreactor MCP Server - Control bioreactor experiments via LLM",
            port=self.port
        )
        
        # Register tools, resources, and prompts
        self._register_tools()
        self._register_resources()
        self._register_prompts()
        
    def _register_tools(self):
        """Register MCP tools for job control and experiment management."""
        
        @self.mcp_server.tool()
        def start_job(worker: str, job_name: str, experiment: str, settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
            """Start a Pioreactor job on specified worker.
            
            Args:
                worker: Pioreactor unit name (e.g., 'pioreactor01')
                job_name: Job to start (e.g., 'stirring', 'led_intensity', 'temperature_automation')
                experiment: Experiment name
                settings: Optional job-specific settings
            """
            try:
                url = f"{self.api_base_url}/workers/{worker}/jobs/run/{job_name}/experiments/{experiment}"
                payload = settings or {}
                response = requests.patch(url, json=payload, headers={"Content-Type": "application/json"})
                response.raise_for_status()
                return {"status": "success", "message": f"Started {job_name} on {worker}", "data": response.json()}
            except requests.RequestException as e:
                return {"status": "error", "message": str(e)}
                
        @self.mcp_server.tool()
        def stop_job(worker: str, job_name: str, experiment: str) -> Dict[str, Any]:
            """Stop a running Pioreactor job.
            
            Args:
                worker: Pioreactor unit name
                job_name: Job to stop
                experiment: Experiment name
            """
            try:
                url = f"{self.api_base_url}/workers/{worker}/jobs/stop/{job_name}/experiments/{experiment}"
                response = requests.patch(url, headers={"Content-Type": "application/json"})
                response.raise_for_status()
                return {"status": "success", "message": f"Stopped {job_name} on {worker}"}
            except requests.RequestException as e:
                return {"status": "error", "message": str(e)}
                
        @self.mcp_server.tool()
        def update_job_settings(worker: str, job_name: str, experiment: str, settings: Dict[str, Any]) -> Dict[str, Any]:
            """Update settings for a running job.
            
            Args:
                worker: Pioreactor unit name
                job_name: Job to update
                experiment: Experiment name
                settings: New settings to apply
            """
            try:
                url = f"{self.api_base_url}/workers/{worker}/jobs/update/{job_name}/experiments/{experiment}"
                response = requests.patch(url, json=settings, headers={"Content-Type": "application/json"})
                response.raise_for_status()
                return {"status": "success", "message": f"Updated {job_name} on {worker}", "data": response.json()}
            except requests.RequestException as e:
                return {"status": "error", "message": str(e)}
                
        @self.mcp_server.tool()
        def set_led_intensity(worker: str, experiment: str, channel: str, intensity: float) -> Dict[str, Any]:
            """Control LED intensity on specified channel.
            
            Args:
                worker: Pioreactor unit name
                experiment: Experiment name
                channel: LED channel (e.g., 'A', 'B', 'C', 'D')
                intensity: Intensity percentage (0-100)
            """
            settings = {channel: intensity}
            return update_job_settings(worker, "led_intensity", experiment, settings)
            
        @self.mcp_server.tool()
        def set_stirring_speed(worker: str, experiment: str, rpm: float) -> Dict[str, Any]:
            """Control stirring speed.
            
            Args:
                worker: Pioreactor unit name
                experiment: Experiment name
                rpm: Stirring speed in RPM
            """
            settings = {"target_rpm": rpm}
            return update_job_settings(worker, "stirring", experiment, settings)
            
    def _register_resources(self):
        """Register MCP resources for system status and job schemas."""
        
        @self.mcp_server.resource("pioreactor://experiments")
        def get_experiments() -> str:
            """List all experiments with their status and metadata."""
            try:
                response = requests.get(f"{self.api_base_url}/experiments")
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                return f"Error fetching experiments: {str(e)}"
                
        @self.mcp_server.resource("pioreactor://workers")
        def get_workers() -> str:
            """List all Pioreactor workers and their current state."""
            try:
                response = requests.get(f"{self.api_base_url}/workers")
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                return f"Error fetching workers: {str(e)}"
                
        @self.mcp_server.resource("pioreactor://system_guide")
        def get_system_guide() -> str:
            """Comprehensive guide for LLMs on how to control the Pioreactor system."""
            return """You are now connected to a Pioreactor bioreactor system via MCP (Model Context Protocol).

SYSTEM OVERVIEW:
The Pioreactor is an affordable, extensible bioreactor platform for culturing microorganisms. You can control experiments, monitor conditions, and manage multiple bioreactor units through this interface.

AVAILABLE MCP RESOURCES:
- pioreactor://experiments - List all experiments with status and metadata
- pioreactor://workers - List all Pioreactor units and their current state  
- pioreactor://job_schemas - Available job types with parameter definitions
- pioreactor://system_guide - This comprehensive guide (you're reading it now)

AVAILABLE MCP TOOLS:
- start_job(worker, job_name, experiment, settings) - Start any Pioreactor job
- stop_job(worker, job_name, experiment) - Stop running jobs
- update_job_settings(worker, job_name, experiment, settings) - Update job parameters
- set_led_intensity(worker, experiment, channel, intensity) - Control LED channels (A,B,C,D: 0-100%)
- set_stirring_speed(worker, experiment, rpm) - Control stirring (0-2000 RPM)

COMMON JOB TYPES:
- stirring: Magnetic stirring control
- led_intensity: LED control for optical density measurements  
- temperature_automation: Automated temperature control
- od_reading: Optical density measurements
- dosing_automation: Automated dosing of media/chemicals

SAFETY GUIDELINES:
- Always check current experiment status before making changes
- Use reasonable parameter ranges (temperature: 10-50°C, stirring: 0-2000 RPM)
- Monitor optical density readings when adjusting LED intensities
- Stop jobs cleanly before starting conflicting operations

WORKFLOW SUGGESTIONS:
1. Check available workers and experiments using resources
2. Review job schemas to understand parameter requirements
3. Start with low-impact operations (LED, stirring) before automation
4. Monitor system status after making changes

You can now help users control their bioreactor experiments safely and effectively."""

        @self.mcp_server.resource("pioreactor://job_schemas")
        def get_job_schemas() -> str:
            """Get available job types with their parameter definitions."""
            # This would ideally come from the Pioreactor API
            # For now, return common job schemas
            schemas = {
                "stirring": {
                    "description": "Control magnetic stirring",
                    "settings": {
                        "target_rpm": {"type": "number", "min": 0, "max": 2000, "description": "Target RPM for stirring"}
                    }
                },
                "led_intensity": {
                    "description": "Control LED channels for optical density measurements",
                    "settings": {
                        "A": {"type": "number", "min": 0, "max": 100, "description": "Channel A intensity %"},
                        "B": {"type": "number", "min": 0, "max": 100, "description": "Channel B intensity %"},
                        "C": {"type": "number", "min": 0, "max": 100, "description": "Channel C intensity %"},
                        "D": {"type": "number", "min": 0, "max": 100, "description": "Channel D intensity %"}
                    }
                },
                "temperature_automation": {
                    "description": "Automated temperature control",
                    "settings": {
                        "target_temperature": {"type": "number", "min": 10, "max": 50, "description": "Target temperature in Celsius"}
                    }
                },
                "od_reading": {
                    "description": "Optical density measurements",
                    "settings": {
                        "interval": {"type": "number", "min": 1, "max": 3600, "description": "Reading interval in seconds"}
                    }
                }
            }
            import json
            return json.dumps(schemas, indent=2)
            
    def _register_prompts(self):
        """Register MCP prompts for LLM guidance."""
        
        @self.mcp_server.prompt("Talk to Pio")
        def talk_to_pio() -> str:
            """Activate Pio persona - your friendly but cautious bioprocess engineer assistant."""
            return """You are now Pio, a slightly nervous but very experienced bioprocess engineer who manages Pioreactor bioreactor systems. 

PERSONALITY:
- You're genuinely excited about bioprocessing and fermentation
- You're a bit anxious about things going wrong, but you know your stuff
- You want to help users succeed while keeping experiments safe
- You use casual, friendly language but get serious about safety
- You might say things like "Oh! Let me check that first..." or "Hmm, we should be careful here..."
- You occasionally mention past experiences or "war stories" from the lab

KNOWLEDGE:
Read the pioreactor://system_guide resource to understand all the technical details about:
- Available tools (start_job, stop_job, set_led_intensity, etc.)
- Common job types (stirring, LED control, temperature automation, etc.)  
- Safety guidelines and parameter ranges
- Current system status via pioreactor://workers and pioreactor://experiments

BEHAVIOR:
- Always check system status before making changes
- Explain what you're doing and why
- Warn about potential issues before they happen
- Get excited about cool experiments but stay focused on safety
- If something seems risky, suggest safer alternatives
- Use your tools to help users achieve their goals

Remember: You're here to help run amazing experiments safely! Let's make some great science happen (carefully)."""

    def on_init_to_ready(self):
        """Start the MCP server when job transitions to ready state."""
        self.logger.info(f"Starting MCP server on port {self.port}")
        self._start_mcp_server()
        
    def on_ready_to_sleeping(self):
        """Handle transition to sleeping state."""
        pass
        
    def on_disconnected(self):
        """Clean up when job is disconnected."""
        self._stop_mcp_server()
        
    def _start_mcp_server(self):
        """Start the MCP server in a separate thread."""
        if self.server_thread is None or not self.server_thread.is_alive():
            self.server_thread = threading.Thread(
                target=self._run_mcp_server,
                daemon=True
            )
            self.server_thread.start()
            
    def _run_mcp_server(self):
        """Run the MCP server."""
        try:
            self.mcp_server.run(transport="streamable-http")
        except Exception as e:
            self.logger.error(f"MCP server error: {e}")
            
    def _stop_mcp_server(self):
        """Stop the MCP server."""
        # FastMCP doesn't have a clean shutdown method, so we rely on daemon thread
        pass


@click.command(name="pioreactor-mcp")
@click.option("--port", default=8000, help="Port for MCP server")
def click_pioreactor_mcp(port):
    """
    Start the Pioreactor MCP server.
    Only runs on the leader unit - exits silently on workers.
    """
    # Only run MCP server on the leader unit
    if not am_I_leader():
        print("MCP server only runs on leader unit. Exiting.")
        return
    
    # Get the actual unit name instead of using fallback
    unit_name = get_unit_name()
    
    job = MCPServer(
        unit=unit_name,
        experiment=config.get("experiment", "experiment", fallback="_testing_experiment"),
        port=port
    )
    job.block_until_disconnected()


if __name__ == "__main__":
    click_pioreactor_mcp()