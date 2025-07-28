import threading
import time
import requests
import click
from mcp.server.fastmcp import FastMCP
from pioreactor.background_jobs.base import BackgroundJob
from pioreactor.config import config
from pioreactor.logging import create_logger
from typing import Optional, Dict, Any, List


class MCPServer(BackgroundJob):
    """
    MCP Server for Pioreactor - provides Model Context Protocol interface
    for LLM interaction with Pioreactor hardware and experiments.
    """
    
    job_name = "pioreactor_mcp"
    
    def __init__(self, unit: str, experiment: str, port: int = 8080, **kwargs):
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
            description="Pioreactor MCP Server - Control bioreactor experiments via LLM"
        )
        
        # Register tools and resources
        self._register_tools()
        self._register_resources()
        
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
        
        @self.mcp_server.resource("experiments")
        def get_experiments() -> str:
            """List all experiments with their status and metadata."""
            try:
                response = requests.get(f"{self.api_base_url}/experiments")
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                return f"Error fetching experiments: {str(e)}"
                
        @self.mcp_server.resource("workers")
        def get_workers() -> str:
            """List all Pioreactor workers and their current state."""
            try:
                response = requests.get(f"{self.api_base_url}/workers")
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                return f"Error fetching workers: {str(e)}"
                
        @self.mcp_server.resource("job_schemas")
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
            self.mcp_server.run(transport="streamable-http", port=self.port)
        except Exception as e:
            self.logger.error(f"MCP server error: {e}")
            
    def _stop_mcp_server(self):
        """Stop the MCP server."""
        # FastMCP doesn't have a clean shutdown method, so we rely on daemon thread
        pass


@click.command(name="pioreactor-mcp")
@click.option("--port", default=8080, help="Port for MCP server")
def click_pioreactor_mcp(port):
    """
    Start the Pioreactor MCP server.
    """
    job = MCPServer(
        unit=config.get("experiment", "unit", fallback="pioreactor"),
        experiment=config.get("experiment", "experiment", fallback="_testing_experiment"),
        port=port
    )
    job.block_until_disconnected()


if __name__ == "__main__":
    click_pioreactor_mcp()