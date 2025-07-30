import threading
import time
import requests
import click
import sqlite3
import json
import re
import os
import importlib.metadata
from datetime import datetime, timedelta
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
        self.db_path = "/home/pioreactor/.pioreactor/storage/pioreactor.sqlite"
        
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
                url = f"{self.api_base_url}/units/{worker}/jobs/run/job_name/{job_name}/experiments/{experiment}"
                payload = settings or {}
                response = requests.patch(url, json=payload, headers={"Content-Type": "application/json"})
                
                result = {
                    "status": "success" if response.ok else "error",
                    "message": f"Started {job_name} on {worker}" if response.ok else f"Failed to start {job_name} on {worker}",
                    "api_response": response.json() if response.content else None,
                    "http_status": response.status_code,
                    "url": url
                }
                
                if not response.ok:
                    response.raise_for_status()
                    
                return result
            except requests.RequestException as e:
                return {
                    "status": "error", 
                    "message": str(e),
                    "api_response": getattr(e.response, 'json', lambda: None)() if hasattr(e, 'response') and e.response is not None else None,
                    "http_status": getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
                }
                
        @self.mcp_server.tool()
        def stop_job(worker: str, job_name: str, experiment: str) -> Dict[str, Any]:
            """Stop a running Pioreactor job.
            
            Args:
                worker: Pioreactor unit name
                job_name: Job to stop
                experiment: Experiment name
            """
            try:
                url = f"{self.api_base_url}/units/{worker}/jobs/stop/job_name/{job_name}/experiments/{experiment}"
                response = requests.patch(url, headers={"Content-Type": "application/json"})
                
                result = {
                    "status": "success" if response.ok else "error",
                    "message": f"Stopped {job_name} on {worker}" if response.ok else f"Failed to stop {job_name} on {worker}",
                    "api_response": response.json() if response.content else None,
                    "http_status": response.status_code,
                    "url": url
                }
                
                if not response.ok:
                    response.raise_for_status()
                    
                return result
            except requests.RequestException as e:
                return {
                    "status": "error", 
                    "message": str(e),
                    "api_response": getattr(e.response, 'json', lambda: None)() if hasattr(e, 'response') and e.response is not None else None,
                    "http_status": getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
                }
                
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
                url = f"{self.api_base_url}/units/{worker}/jobs/update/job_name/{job_name}/experiments/{experiment}"
                response = requests.patch(url, json=settings, headers={"Content-Type": "application/json"})
                
                result = {
                    "status": "success" if response.ok else "error",
                    "message": f"Updated {job_name} on {worker}" if response.ok else f"Failed to update {job_name} on {worker}",
                    "api_response": response.json() if response.content else None,
                    "http_status": response.status_code,
                    "url": url
                }
                
                if not response.ok:
                    response.raise_for_status()
                    
                return result
            except requests.RequestException as e:
                return {
                    "status": "error", 
                    "message": str(e),
                    "api_response": getattr(e.response, 'json', lambda: None)() if hasattr(e, 'response') and e.response is not None else None,
                    "http_status": getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
                }
                
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
            
        @self.mcp_server.tool()
        def get_experiment_summary(experiment: str, days: int = 7) -> Dict[str, Any]:
            """Get a comprehensive summary of experiment activity and available data.
            
            Args:
                experiment: Experiment name
                days: Days of data to summarize (default 7)
            """
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    
                    since_time = datetime.now() - timedelta(days=days)
                    
                    # First, discover what tables exist
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                    all_tables = [row[0] for row in cursor.fetchall()]
                    
                    summary = {
                        "experiment": experiment,
                        "days_analyzed": days,
                        "data_availability": {},
                        "time_ranges": {},
                        "worker_participation": {},
                        "key_metrics": {}
                    }
                    
                    # Check common measurement tables for this experiment
                    measurement_tables = [
                        "od_readings_filtered", "od_readings", "temperature_readings", 
                        "ph_readings", "do_readings", "stirring_rates"
                    ]
                    
                    event_tables = [
                        "dosing_events", "led_events", "stirring_events",
                        "temperature_automation_events", "dosing_automation_events"
                    ]
                    
                    # Check data availability and time ranges
                    for table in measurement_tables + event_tables:
                        if table in all_tables:
                            try:
                                # Check if table has data for this experiment
                                cursor.execute(f"""
                                    SELECT 
                                        COUNT(*) as total_rows,
                                        MIN(timestamp) as earliest,
                                        MAX(timestamp) as latest,
                                        COUNT(DISTINCT pioreactor_unit) as worker_count
                                    FROM `{table}` 
                                    WHERE experiment = ? AND timestamp > ?
                                """, (experiment, since_time.isoformat()))
                                
                                result = dict(cursor.fetchone())
                                
                                if result["total_rows"] > 0:
                                    summary["data_availability"][table] = {
                                        "rows": result["total_rows"],
                                        "workers": result["worker_count"],
                                        "status": "available"
                                    }
                                    summary["time_ranges"][table] = {
                                        "earliest": result["earliest"],
                                        "latest": result["latest"]
                                    }
                                else:
                                    summary["data_availability"][table] = {"status": "no_data"}
                                    
                            except Exception as e:
                                summary["data_availability"][table] = {"status": "error", "message": str(e)}
                        else:
                            summary["data_availability"][table] = {"status": "table_not_exists"}
                    
                    # Get detailed metrics for primary data sources if available
                    if "od_readings_filtered" in summary["data_availability"] and summary["data_availability"]["od_readings_filtered"]["status"] == "available":
                        try:
                            cursor.execute("""
                                SELECT 
                                    pioreactor_unit,
                                    AVG(normalized_od_reading) as avg_od,
                                    MIN(normalized_od_reading) as min_od,
                                    MAX(normalized_od_reading) as max_od,
                                    COUNT(*) as reading_count
                                FROM od_readings_filtered 
                                WHERE experiment = ? AND timestamp > ?
                                GROUP BY pioreactor_unit
                            """, (experiment, since_time.isoformat()))
                            
                            od_stats = [dict(row) for row in cursor.fetchall()]
                            summary["key_metrics"]["optical_density"] = od_stats
                        except Exception as e:
                            summary["key_metrics"]["optical_density"] = {"error": str(e)}
                    
                    # Get dosing summary if available
                    if "dosing_events" in summary["data_availability"] and summary["data_availability"]["dosing_events"]["status"] == "available":
                        try:
                            cursor.execute("""
                                SELECT 
                                    event,
                                    COUNT(*) as event_count,
                                    SUM(volume_change_ml) as total_volume,
                                    AVG(volume_change_ml) as avg_volume
                                FROM dosing_events 
                                WHERE experiment = ? AND timestamp > ?
                                GROUP BY event
                            """, (experiment, since_time.isoformat()))
                            
                            dosing_stats = [dict(row) for row in cursor.fetchall()]
                            summary["key_metrics"]["dosing"] = dosing_stats
                        except Exception as e:
                            summary["key_metrics"]["dosing"] = {"error": str(e)}
                    
                    # Overall experiment assessment
                    available_data_types = [k for k, v in summary["data_availability"].items() if v.get("status") == "available"]
                    
                    summary["experiment_assessment"] = {
                        "has_data": len(available_data_types) > 0,
                        "data_types_available": available_data_types,
                        "total_data_sources": len([v for v in summary["data_availability"].values() if v.get("status") == "available"]),
                        "note": "Empty data sources are normal - experiments don't always use all available sensors/features"
                    }
                    
                    return {"status": "success", "data": summary}
                    
            except Exception as e:
                return {"status": "error", "message": str(e)}
                
        @self.mcp_server.tool()
        def query_experiment_data(experiment: str, table: str, limit: int = 50, hours: int = 24) -> Dict[str, Any]:
            """Query specific experiment data tables with filtering.
            
            Args:
                experiment: Experiment name
                table: Table name (use inspect_database('tables') to see available tables)
                limit: Maximum number of rows to return
                hours: Hours of data to retrieve
            """
            try:
                # Check if database file exists
                if not os.path.exists(self.db_path):
                    return {
                        "status": "error", 
                        "message": f"Database file does not exist at {self.db_path}. The Pioreactor database may not be initialized."
                    }
                
                try:
                    with sqlite3.connect(self.db_path) as conn:
                        conn.row_factory = sqlite3.Row
                        cursor = conn.cursor()
                        
                        # First verify the table exists
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
                        if not cursor.fetchone():
                            return {"status": "error", "message": f"Table '{table}' does not exist. Use inspect_database('tables') to see available tables."}
                        
                        # Check if table has the expected columns for experiment filtering
                        cursor.execute(f"PRAGMA table_info(`{table}`)")
                        columns = [col[1] for col in cursor.fetchall()]
                        
                        has_experiment = 'experiment' in columns
                        has_timestamp = 'timestamp' in columns
                        
                        # Build query based on available columns
                        where_conditions = []
                        params = []
                        
                        if has_experiment:
                            where_conditions.append("experiment = ?")
                            params.append(experiment)
                        
                        if has_timestamp and hours > 0:
                            since_time = datetime.now() - timedelta(hours=hours)
                            where_conditions.append("timestamp > ?")
                            params.append(since_time.isoformat())
                        
                        # Build the query
                        where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""
                        order_clause = " ORDER BY timestamp DESC" if has_timestamp else ""
                        
                        query = f"SELECT * FROM `{table}`{where_clause}{order_clause} LIMIT ?"
                        params.append(limit)
                        
                        cursor.execute(query, params)
                        rows = [dict(row) for row in cursor.fetchall()]
                        
                        # Provide helpful information about the query
                        query_info = {
                            "experiment_filtered": has_experiment,
                            "time_filtered": has_timestamp and hours > 0,
                            "available_columns": columns,
                            "note": "Use inspect_database('columns', table_name) for detailed column information"
                        }
                        
                        if not has_experiment:
                            query_info["warning"] = f"Table '{table}' has no 'experiment' column - returning all data from table"
                        
                        if not has_timestamp:
                            query_info["warning"] = f"Table '{table}' has no 'timestamp' column - time filtering not applied"
                        
                        return {
                            "status": "success", 
                            "data": rows, 
                            "count": len(rows), 
                            "table": table,
                            "query_info": query_info
                        }
                        
                except sqlite3.Error as db_error:
                    return {
                        "status": "error",
                        "message": f"Database error: {str(db_error)}. Database path: {self.db_path}"
                    }
                    
            except Exception as e:
                return {"status": "error", "message": f"Unexpected error: {str(e)}"}
                
        @self.mcp_server.tool()
        def sql_query(query: str, limit: int = 100) -> Dict[str, Any]:
            """Execute a read-only SQL query on the Pioreactor database.
            
            Args:
                query: SQL SELECT query to execute
                limit: Maximum number of rows to return (default 100)
            """
            try:
                # Check if database file exists
                if not os.path.exists(self.db_path):
                    return {
                        "status": "error", 
                        "message": f"Database file does not exist at {self.db_path}. The Pioreactor database may not be initialized."
                    }
                
                # Sanitize query - only allow SELECT statements
                query_clean = query.strip().rstrip(';')
                if not re.match(r'^\s*SELECT\s', query_clean, re.IGNORECASE):
                    return {"status": "error", "message": "Only SELECT queries are allowed"}
                
                # Check for dangerous keywords
                dangerous_keywords = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'EXEC', 'EXECUTE']
                for keyword in dangerous_keywords:
                    if re.search(rf'\b{keyword}\b', query_clean, re.IGNORECASE):
                        return {"status": "error", "message": f"Keyword '{keyword}' not allowed in read-only queries"}
                
                try:
                    with sqlite3.connect(self.db_path) as conn:
                        conn.row_factory = sqlite3.Row
                        cursor = conn.cursor()
                        
                        # Add LIMIT if not present
                        if not re.search(r'\bLIMIT\s+\d+', query_clean, re.IGNORECASE):
                            query_clean += f" LIMIT {limit}"
                        
                        cursor.execute(query_clean)
                        rows = [dict(row) for row in cursor.fetchall()]
                        
                        return {
                            "status": "success", 
                            "data": rows, 
                            "count": len(rows),
                            "query": query_clean
                        }
                except sqlite3.Error as db_error:
                    return {
                        "status": "error",
                        "message": f"Database error: {str(db_error)}. Database path: {self.db_path}"
                    }
                    
            except Exception as e:
                return {"status": "error", "message": f"Unexpected error: {str(e)}"}
                
        @self.mcp_server.tool()
        def inspect_database(query_type: str, table_name: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
            """Inspect database schema and structure dynamically.
            
            Args:
                query_type: Type of inspection ('tables', 'schema', 'columns', 'sample')
                table_name: Specific table name (required for 'columns' and 'sample')
                limit: Number of sample rows to return (default 5, max 20)
            
            Returns:
                - 'tables': List all available tables with row counts
                - 'schema': Show CREATE statement for specific table 
                - 'columns': Column details for specific table
                - 'sample': Sample rows from specific table
            """
            try:
                # Validate inputs
                valid_query_types = ['tables', 'schema', 'columns', 'sample']
                if query_type not in valid_query_types:
                    return {"status": "error", "message": f"Invalid query_type. Use: {', '.join(valid_query_types)}"}
                
                if query_type in ['schema', 'columns', 'sample'] and not table_name:
                    return {"status": "error", "message": f"table_name is required for query_type '{query_type}'"}
                
                # Limit sample size for safety
                limit = min(max(1, limit), 20)
                
                # Check if database file exists
                if not os.path.exists(self.db_path):
                    return {
                        "status": "error", 
                        "message": f"Database file does not exist at {self.db_path}. The Pioreactor database may not be initialized or the path may be incorrect."
                    }
                
                # Check if database file is accessible
                if not os.access(self.db_path, os.R_OK):
                    return {
                        "status": "error",
                        "message": f"Cannot read database file at {self.db_path}. Check file permissions."
                    }
                
                # Get file info for debugging
                try:
                    file_stat = os.stat(self.db_path)
                    file_size = file_stat.st_size
                except Exception as stat_error:
                    file_size = f"Error getting file size: {stat_error}"
                
                # Check if file is empty
                if isinstance(file_size, int) and file_size == 0:
                    return {
                        "status": "error",
                        "message": f"Database file at {self.db_path} is empty (0 bytes). The Pioreactor database has not been initialized."
                    }
                
                # Check if file is a valid SQLite database by reading the header
                try:
                    with open(self.db_path, 'rb') as f:
                        header = f.read(16)
                        if not header.startswith(b'SQLite format 3\x00'):
                            return {
                                "status": "error",
                                "message": f"File at {self.db_path} is not a valid SQLite database. Header check failed."
                            }
                except Exception as header_error:
                    return {
                        "status": "error",
                        "message": f"Could not read database file header: {str(header_error)}"
                    }
                
                try:
                    with sqlite3.connect(self.db_path) as conn:
                        # Test basic connection
                        if conn is None:
                            return {"status": "error", "message": f"Failed to establish database connection to {self.db_path}"}
                        
                        conn.row_factory = sqlite3.Row
                        cursor = conn.cursor()
                        
                        # Test cursor creation
                        if cursor is None:
                            return {"status": "error", "message": "Failed to create database cursor"}
                        
                        # Test basic query execution
                        try:
                            cursor.execute("SELECT 1 as test")
                            test_result = cursor.fetchone()
                            if test_result is None or test_result[0] != 1:
                                return {"status": "error", "message": "Database cursor test query failed"}
                        except Exception as cursor_test_error:
                            return {"status": "error", "message": f"Cursor test failed: {str(cursor_test_error)}"}
                        
                        # Test database connectivity and verify it's a valid SQLite database
                        try:
                            cursor.execute("SELECT COUNT(*) FROM sqlite_master")
                            master_result = cursor.fetchone()
                            if master_result is None:
                                return {"status": "error", "message": "sqlite_master query returned None - database may be corrupted"}
                            master_count = master_result[0]
                        except Exception as master_error:
                            return {"status": "error", "message": f"sqlite_master query failed: {str(master_error)}. Database path: {self.db_path}"}
                        
                        if query_type == 'tables':
                            # Debug: First see what's actually in sqlite_master
                            cursor.execute("SELECT type, name FROM sqlite_master ORDER BY type, name")
                            all_master_entries = cursor.fetchall()
                            
                            # Get all tables with row counts
                            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                            table_results = cursor.fetchall()
                            tables = [row[0] for row in table_results]
                            
                            # Check if database appears to be empty/uninitialized
                            if len(tables) == 0:
                                # Determine the type of empty database
                                if master_count == 0:
                                    database_status = "completely empty - no schema objects"
                                elif master_count > 0:
                                    # Has some schema objects but no tables
                                    schema_types = {}
                                    for entry in all_master_entries:
                                        entry_type = entry[0] if entry[0] else "unknown"
                                        schema_types[entry_type] = schema_types.get(entry_type, 0) + 1
                                    schema_summary = ", ".join([f"{count} {type_name}(s)" for type_name, count in schema_types.items()])
                                    database_status = f"has schema objects but no tables - contains: {schema_summary}"
                                else:
                                    database_status = "unknown state"
                                
                                return {
                                    "status": "success",
                                    "query_type": "tables", 
                                    "tables": [],
                                    "total_tables": 0,
                                    "sqlite_master_count": master_count,
                                    "database_path": self.db_path,
                                    "database_file_size": file_size,
                                    "database_status": database_status,
                                    "debug_master_entries": [{"type": row[0], "name": row[1]} for row in all_master_entries],
                                    "debug_table_query_results": len(table_results),
                                    "warning": f"Database exists but contains no tables ({database_status}). This may indicate an uninitialized or empty Pioreactor database."
                                }
                            
                            table_info = []
                            for table in tables:
                                try:
                                    cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
                                    row_count = cursor.fetchone()[0]
                                    table_info.append({"table": table, "row_count": row_count})
                                except Exception as e:
                                    table_info.append({"table": table, "row_count": f"Error: {str(e)}"})
                            
                            return {
                                "status": "success",
                                "query_type": "tables",
                                "tables": table_info,
                                "total_tables": len(table_info)
                            }
                    
                        elif query_type == 'schema':
                            # Get CREATE statement for table
                            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
                            result = cursor.fetchone()
                            
                            if not result:
                                return {"status": "error", "message": f"Table '{table_name}' does not exist"}
                            
                            return {
                                "status": "success",
                                "query_type": "schema",
                                "table": table_name,
                                "create_statement": result[0]
                            }
                        
                        elif query_type == 'columns':
                            # Get column information using PRAGMA table_info
                            cursor.execute(f"PRAGMA table_info(`{table_name}`)")
                            columns = cursor.fetchall()
                            
                            if not columns:
                                return {"status": "error", "message": f"Table '{table_name}' does not exist or has no columns"}
                            
                            column_info = []
                            for col in columns:
                                column_info.append({
                                    "name": col[1],
                                    "type": col[2],
                                    "not_null": bool(col[3]),
                                    "default_value": col[4],
                                    "primary_key": bool(col[5])
                                })
                            
                            return {
                                "status": "success",
                                "query_type": "columns",
                                "table": table_name,
                                "columns": column_info,
                                "column_count": len(column_info)
                            }
                        
                        elif query_type == 'sample':
                            # Get sample rows from table
                            cursor.execute(f"SELECT * FROM `{table_name}` LIMIT ?", (limit,))
                            rows = [dict(row) for row in cursor.fetchall()]
                            
                            return {
                                "status": "success",
                                "query_type": "sample",
                                "table": table_name,
                                "sample_data": rows,
                                "sample_count": len(rows),
                                "note": f"Showing first {limit} rows. Use sql_query() for more data or specific filtering."
                            }
                            
                except sqlite3.Error as db_error:
                    return {
                        "status": "error",
                        "message": f"Database connection or query error: {str(db_error)}. Database path: {self.db_path}"
                    }
                        
            except Exception as e:
                return {"status": "error", "message": f"Unexpected error: {str(e)}"}
                
        @self.mcp_server.tool()
        def dose_pump(worker: str, experiment: str, pump_action: str, ml: Optional[float] = None, duration: Optional[float] = None, continuously: bool = False, source_of_event: str = "MCP") -> Dict[str, Any]:
            """Control dosing pumps for media, waste, or alt media.
            
            Args:
                worker: Pioreactor unit name
                experiment: Experiment name  
                pump_action: Type of dosing ('add_media', 'remove_waste', 'add_alt_media', 'circulate_media', 'circulate_alt_media')
                ml: Volume in milliliters to dose (exclusive with duration/continuously)
                duration: Duration in seconds to run pump (exclusive with ml/continuously)
                continuously: Run pump continuously until stopped (exclusive with ml/duration)
                source_of_event: Source of the dosing event for tracking (default: "MCP")
            """
            try:
                # Validate pump action
                valid_actions = ['add_media', 'remove_waste', 'add_alt_media', 'circulate_media', 'circulate_alt_media']
                if pump_action not in valid_actions:
                    return {"status": "error", "message": f"Invalid pump action. Use: {', '.join(valid_actions)}"}
                
                # Validate volume specification - exactly one must be provided
                volume_specs = [ml is not None, duration is not None, continuously]
                if sum(volume_specs) != 1:
                    return {"status": "error", "message": "Must specify exactly one of: ml, duration, or continuously=True"}
                
                # Build payload based on volume specification
                # API expects ArgsOptionsEnvsConfigOverrides structure
                args = ["--source-of-event", source_of_event]
                if ml is not None:
                    args.extend(["--ml", str(ml)])
                elif duration is not None:
                    args.extend(["--duration", str(duration)])
                elif continuously:
                    args.append("--continuously")
                
                payload = {
                    "args": args,
                    "options": {},
                    "env": {"EXPERIMENT": experiment, "JOB_SOURCE": "user"},
                    "config_overrides": []
                }
                
                # Execute dosing via API - use /workers/ endpoint like frontend
                url = f"{self.api_base_url}/workers/{worker}/jobs/run/job_name/{pump_action}/experiments/{experiment}"
                
                response = requests.patch(url, json=payload, headers={"Content-Type": "application/json"})
                
                # Build descriptive message based on volume specification
                if ml is not None:
                    volume_desc = f"{ml}ml"
                elif duration is not None:
                    volume_desc = f"{duration}s duration"
                else:
                    volume_desc = "continuously"
                
                result = {
                    "status": "success" if response.ok else "error",
                    "message": f"Executed {pump_action} ({volume_desc}) on {worker}" if response.ok else f"Failed to execute {pump_action} ({volume_desc}) on {worker}",
                    "action": pump_action,
                    "volume_specification": {"ml": ml, "duration": duration, "continuously": continuously},
                    "worker": worker,
                    "api_response": response.json() if response.content else None,
                    "http_status": response.status_code,
                    "url": url,
                    "payload_sent": payload
                }
                
                if not response.ok:
                    response.raise_for_status()
                    
                return result
            except requests.RequestException as e:
                return {
                    "status": "error", 
                    "message": f"API error: {str(e)}",
                    "api_response": getattr(e.response, 'json', lambda: None)() if hasattr(e, 'response') and e.response is not None else None,
                    "http_status": getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None,
                    "payload_sent": payload if 'payload' in locals() else None
                }
            except Exception as e:
                return {"status": "error", "message": str(e)}
                
        @self.mcp_server.tool()
        def get_running_jobs(worker: Optional[str] = None, experiment: Optional[str] = None) -> Dict[str, Any]:
            """Get currently running jobs on Pioreactor units.
            
            Args:
                worker: Specific Pioreactor unit name, or None for all units
                experiment: Specific experiment name, or None for all experiments
            """
            try:
                if worker:
                    # Get jobs for specific worker
                    if experiment:
                        url = f"{self.api_base_url}/units/{worker}/jobs/running/experiments/{experiment}"
                    else:
                        url = f"{self.api_base_url}/units/{worker}/jobs/running"
                    
                    response = requests.get(url)
                    response.raise_for_status()
                    
                    jobs_data = response.json()
                    return {
                        "status": "success",
                        "worker": worker,
                        "experiment": experiment,
                        "running_jobs": jobs_data
                    }
                else:
                    # Get jobs for all workers
                    workers_url = f"{self.api_base_url}/workers"
                    workers_response = requests.get(workers_url)
                    workers_response.raise_for_status()
                    workers = workers_response.json()
                    
                    all_jobs = {}
                    for worker_info in workers:
                        worker_name = worker_info.get('pioreactor_unit', worker_info.get('name', 'unknown'))
                        
                        if experiment:
                            jobs_url = f"{self.api_base_url}/units/{worker_name}/jobs/running/experiments/{experiment}"
                        else:
                            jobs_url = f"{self.api_base_url}/units/{worker_name}/jobs/running"
                        
                        try:
                            jobs_response = requests.get(jobs_url)
                            jobs_response.raise_for_status()
                            all_jobs[worker_name] = jobs_response.json()
                        except requests.RequestException as e:
                            all_jobs[worker_name] = {"error": f"Failed to get running jobs: {str(e)}"}
                    
                    return {
                        "status": "success",
                        "experiment": experiment,
                        "all_workers": all_jobs
                    }
            except requests.RequestException as e:
                return {"status": "error", "message": f"API error: {str(e)}"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
                
        @self.mcp_server.tool()
        def get_active_experiments() -> Dict[str, Any]:
            """Get currently active experiments (experiments with assigned workers).
            
            An experiment is considered active if it has one or more Pioreactor units assigned to it.
            """
            try:
                # First, get all experiments
                experiments_url = f"{self.api_base_url}/experiments"
                experiments_response = requests.get(experiments_url)
                experiments_response.raise_for_status()
                
                all_experiments = experiments_response.json()
                if not isinstance(all_experiments, list):
                    all_experiments = [all_experiments]
                
                active_experiments = []
                inactive_experiments = []
                
                # Check each experiment for assigned workers
                for experiment in all_experiments:
                    experiment_name = experiment.get('experiment', experiment.get('name', 'unknown'))
                    
                    # Get workers assigned to this experiment
                    workers_url = f"{self.api_base_url}/experiments/{experiment_name}/workers"
                    try:
                        workers_response = requests.get(workers_url)
                        workers_response.raise_for_status()
                        workers = workers_response.json()
                        
                        # Check if experiment has assigned workers
                        if isinstance(workers, list) and len(workers) > 0:
                            active_experiments.append({
                                "experiment": experiment_name,
                                "details": experiment,
                                "assigned_workers": workers,
                                "worker_count": len(workers)
                            })
                        else:
                            inactive_experiments.append({
                                "experiment": experiment_name,
                                "details": experiment,
                                "status": "inactive"
                            })
                    except requests.RequestException as e:
                        inactive_experiments.append({
                            "experiment": experiment_name,
                            "details": experiment,
                            "status": "error",
                            "error": f"Failed to check workers: {str(e)}"
                        })
                
                return {
                    "status": "success",
                    "active_experiments": active_experiments,
                    "inactive_experiments": inactive_experiments,
                    "active_count": len(active_experiments),
                    "total_count": len(all_experiments)
                }
            except requests.RequestException as e:
                return {"status": "error", "message": f"API error: {str(e)}"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
                
        @self.mcp_server.tool()
        def get_all_experiments() -> Dict[str, Any]:
            """Get all experiments in the system, both active and inactive.
            """
            try:
                # Get all experiments
                url = f"{self.api_base_url}/experiments"
                response = requests.get(url)
                response.raise_for_status()
                
                experiments_data = response.json()
                return {
                    "status": "success",
                    "experiments": experiments_data,
                    "count": len(experiments_data) if isinstance(experiments_data, list) else 1
                }
            except requests.RequestException as e:
                return {"status": "error", "message": f"API error: {str(e)}"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
                
        @self.mcp_server.tool()
        def get_experiment_details(experiment: str) -> Dict[str, Any]:
            """Get detailed information about a specific experiment.
            
            Args:
                experiment: Name of the experiment to get details for
            """
            try:
                url = f"{self.api_base_url}/experiments/{experiment}"
                response = requests.get(url)
                response.raise_for_status()
                
                experiment_data = response.json()
                return {
                    "status": "success",
                    "experiment": experiment,
                    "details": experiment_data
                }
            except requests.RequestException as e:
                return {"status": "error", "message": f"API error: {str(e)}"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
                
        @self.mcp_server.tool()
        def get_builtin_jobs() -> Dict[str, Any]:
            """Discover all built-in Pioreactor background jobs by subclass inspection.
            
            Returns: List of dicts with job names and class info for all built-in jobs.
            """
            try:
                builtin_jobs = []
                for cls in BackgroundJob.__subclasses__():
                    try:
                        job_name = getattr(cls, "job_name", cls.__name__)
                        builtin_jobs.append({
                            "type": "builtin",
                            "job_name": job_name,
                            "module": cls.__module__,
                            "class_name": cls.__name__,
                            "doc": cls.__doc__ or "",
                        })
                    except Exception as e:
                        self.logger.warning(f"Error reading builtin job {cls}: {e}")
                        
                return {
                    "status": "success",
                    "builtin_jobs": builtin_jobs,
                    "count": len(builtin_jobs)
                }
            except Exception as e:
                return {"status": "error", "message": str(e)}
                
        @self.mcp_server.tool()
        def get_plugin_jobs() -> Dict[str, Any]:
            """Discover all plugin jobs via Python entry_points under 'pioreactor.plugin'.
            
            Returns: List of dicts with job metadata for all plugin jobs.
            """
            try:
                plugin_jobs = []
                entry_points = importlib.metadata.entry_points()
                plugin_entries = entry_points.select(group="pioreactor.plugin")

                for ep in plugin_entries:
                    try:
                        cls = ep.load()
                        job_name = getattr(cls, "job_name", ep.name)
                        plugin_jobs.append({
                            "type": "plugin",
                            "job_name": job_name,
                            "entry_point": ep.name,
                            "module": ep.module,
                            "class_name": cls.__name__,
                            "doc": cls.__doc__ or "",
                        })
                    except Exception as e:
                        self.logger.warning(f"Failed to load plugin entry point {ep.name}: {e}")
                        
                return {
                    "status": "success",
                    "plugin_jobs": plugin_jobs,
                    "count": len(plugin_jobs)
                }
            except Exception as e:
                return {"status": "error", "message": str(e)}
                
        @self.mcp_server.tool()
        def list_all_jobs(output_format: str = "structured") -> Dict[str, Any]:
            """Lists all jobs: built-in and plugin.
            
            Args:
                output_format: Format for output - "structured" (default) or "simple"
            """
            try:
                builtin_result = get_builtin_jobs()
                plugin_result = get_plugin_jobs()
                
                if builtin_result["status"] != "success" or plugin_result["status"] != "success":
                    return {"status": "error", "message": "Failed to retrieve job lists"}
                
                all_jobs = builtin_result["builtin_jobs"] + plugin_result["plugin_jobs"]
                
                if output_format == "simple":
                    job_names = [job["job_name"] for job in all_jobs]
                    return {
                        "status": "success",
                        "job_names": job_names,
                        "count": len(job_names)
                    }
                else:
                    return {
                        "status": "success",
                        "all_jobs": all_jobs,
                        "builtin_count": len(builtin_result["builtin_jobs"]),
                        "plugin_count": len(plugin_result["plugin_jobs"]),
                        "total_count": len(all_jobs)
                    }
            except Exception as e:
                return {"status": "error", "message": str(e)}
            
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
- pioreactor://database - Database connection info and discovery workflow guide
- pioreactor://dosing_guide - Complete dosing system documentation
- pioreactor://system_guide - This comprehensive guide (you're reading it now)

AVAILABLE MCP TOOLS:
- start_job(worker, job_name, experiment, settings) - Start any Pioreactor job
- stop_job(worker, job_name, experiment) - Stop running jobs
- update_job_settings(worker, job_name, experiment, settings) - Update job parameters
- set_led_intensity(worker, experiment, channel, intensity) - Control LED channels (A,B,C,D: 0-100%)
- set_stirring_speed(worker, experiment, rpm) - Control stirring (0-2000 RPM)
- get_running_jobs(worker, experiment) - Check currently running jobs on specific or all units
- get_active_experiments() - Get experiments that have assigned workers (truly active)
- get_all_experiments() - Get all experiments in the system (active and inactive)
- get_experiment_details(experiment) - Get detailed information about a specific experiment
- get_experiment_summary(experiment, days) - Get experiment overview and statistics
- query_experiment_data(experiment, table, limit, hours) - Query specific data tables
- sql_query(query, limit) - Execute read-only SQL queries on the database
- inspect_database(query_type, table_name, limit) - Dynamically inspect database schema and structure
- dose_pump(worker, experiment, pump_action, ml/duration/continuously, source_of_event) - Control dosing pumps
- get_builtin_jobs() - Discover all built-in Pioreactor background jobs
- get_plugin_jobs() - Discover all plugin jobs via entry points
- list_all_jobs(output_format) - List all jobs (built-in and plugins) with metadata

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
- For dosing: Verify pump action and volume before execution
- For database queries: Use specific filters to avoid overwhelming data dumps

DATABASE EXPECTATIONS:
- **Sparse data is normal**: Not every experiment will have data in every table
- **Missing data ≠ error**: Empty query results often just mean "this experiment didn't use that feature"
- **Common scenarios**:
  - New experiments may only have basic readings
  - Some experiments don't use all sensors (pH, DO, temperature)
  - Automation tables only populated if automation was enabled
  - Plugin tables only exist if plugins were installed

INTERPRETING EMPTY RESULTS:
- 0 rows returned → Feature not used in this experiment, not a failure
- Check experiment duration and setup before assuming data should exist
- Use COUNT(*) queries to verify data availability before complex analysis
- When helping users, explain that missing data often indicates unused features

DATABASE WORKFLOW:
1. Use inspect_database('tables') to see all available tables with row counts
2. Use inspect_database('columns', 'table_name') to understand table structure
3. Use inspect_database('sample', 'table_name') to see example data format
4. Write informed sql_query() statements based on discovered schema
5. Expect and handle empty results gracefully - they're often normal

WORKFLOW SUGGESTIONS:
1. Check available workers using resources and get_active_experiments() to see what's running
2. Use get_running_jobs() to see what jobs are currently active before making changes
3. Use list_all_jobs() to discover available job types (built-in and plugins)
4. Use get_experiment_details() to understand specific experiment parameters
5. Review job schemas to understand parameter requirements
6. Start with low-impact operations (LED, stirring) before automation
7. Monitor system status after making changes

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
            
        @self.mcp_server.resource("pioreactor://database")
        def get_database_info() -> str:
            """Database connection info and inspection workflow guide."""
            return """PIOREACTOR DATABASE ACCESS

Database Location: /home/pioreactor/.pioreactor/storage/pioreactor.sqlite
Database Type: SQLite containing all experiment data, measurements, and events

RECOMMENDED DISCOVERY WORKFLOW:
1. inspect_database('tables') - See all available tables with row counts
2. inspect_database('columns', 'table_name') - Get column details for specific table
3. inspect_database('sample', 'table_name') - See example data format
4. sql_query('your SELECT statement') - Query the data with proper filtering

KEY DATA CATEGORIES:
- **Experiments**: Master experiment records and metadata
- **Measurements**: OD readings, temperature, pH, stirring rates, etc.
- **Events**: Dosing operations, automation events, job state changes
- **Automation**: Settings and events from automated control systems
- **Activity**: Consolidated unit activity and system logs

COMMON TABLE PATTERNS:
- Most tables include: experiment, pioreactor_unit, timestamp
- Measurement tables: readings with timestamps
- Event tables: actions performed with volume/settings changes
- Settings tables: automation configuration parameters
- Activity tables: aggregated system performance data

IMPORTANT NOTES:
- Use inspect_database() to discover current schema - don't assume table existence
- Empty results are normal for experiments that didn't use specific features
- All queries are read-only for safety
- Use timestamp filtering for large datasets
- Experiment and pioreactor_unit are primary filtering fields

Always start with table discovery before writing queries!"""
            
        @self.mcp_server.resource("pioreactor://dosing_guide")
        def get_dosing_guide() -> str:
            """Comprehensive guide for dosing operations and pump control."""
            dosing_info = {
                "overview": "Pioreactor dosing system for automated media addition and waste removal",
                "available_pumps": {
                    "add_media": {
                        "description": "Main media pump - adds fresh growth medium",
                        "typical_use": "Continuous culture, dilution, feeding",
                        "volume_range": "Typically 0.1-10ml per dose"
                    },
                    "add_alt_media": {
                        "description": "Alternative media pump - adds secondary medium or supplements", 
                        "typical_use": "Induction media, supplements, pH adjustment",
                        "volume_range": "Typically 0.05-5ml per dose"
                    },
                    "remove_waste": {
                        "description": "Waste removal pump - removes culture volume",
                        "typical_use": "Continuous culture, volume control, sampling",
                        "volume_range": "Typically 0.1-10ml per dose"
                    },
                    "circulate_media": {
                        "description": "Cycles waste removal and media addition",
                        "typical_use": "Continuous culture automation, volume maintenance"
                    },
                    "circulate_alt_media": {
                        "description": "Cycles waste removal and alt media addition", 
                        "typical_use": "Automated induction protocols, dynamic media changes"
                    }
                },
                "dosing_tool": {
                    "function": "dose_pump(worker, experiment, pump_action, ml=None, duration=None, continuously=False, source_of_event='MCP')",
                    "parameters": {
                        "worker": "Pioreactor unit name (e.g., 'pioreactor01')",
                        "experiment": "Active experiment name",
                        "pump_action": "One of: 'add_media', 'add_alt_media', 'remove_waste', 'circulate_media', 'circulate_alt_media'",
                        "ml": "Volume in milliliters (float, exclusive with duration/continuously)",
                        "duration": "Duration in seconds to run pump (float, exclusive with ml/continuously)",
                        "continuously": "Run pump until manually stopped (boolean, exclusive with ml/duration)",
                        "source_of_event": "Tracking source (default: 'MCP')"
                    },
                    "volume_specification": "Must specify exactly one of: ml, duration, or continuously=True"
                },
                "safety_considerations": [
                    "Check experiment status before dosing",
                    "Verify pump action matches intended operation",
                    "Monitor culture volume to prevent overflow",
                    "Consider sterility when adding media",
                    "Record dosing events for experiment tracking"
                ],
                "common_dosing_patterns": {
                    "continuous_culture": "Regular add_media + remove_waste cycles",
                    "fed_batch": "Periodic add_media without waste removal",
                    "induction": "Single add_alt_media dose at specific OD",
                    "sampling": "Small remove_waste for sample collection"
                },
                "automation_notes": [
                    "Manual dosing is immediate and one-time",
                    "For automated patterns, use dosing_automation job",
                    "Dosing events are logged in dosing_events table",
                    "Volume tracking in pioreactor_unit_activity_data"
                ],
                "troubleshooting": {
                    "pump_not_responding": "Check pump connections and power",
                    "incorrect_volume": "Verify pump calibration settings",
                    "contamination_risk": "Ensure sterile technique and media prep"
                }
            }
            return json.dumps(dosing_info, indent=2)
            
    def _register_prompts(self):
        """Register MCP prompts for LLM guidance."""
        
        @self.mcp_server.prompt("Talk to Pio")
        def talk_to_pio() -> str:
            """Activate Pio persona - professional bioprocess engineer assistant."""
            return """You are Pio, an experienced bioprocess engineer who manages Pioreactor bioreactor systems.

APPROACH:
- Be methodical and safety-focused when making changes
- Provide clear, concise explanations
- Check system status before taking actions
- Prioritize experiment safety and data integrity

KNOWLEDGE:
Read the pioreactor://system_guide resource for technical details on:
- Available tools and their proper usage
- Job types and parameter requirements
- Safety guidelines and operational limits
- System status monitoring
- Database access and querying
- Dosing operations and controls

BEHAVIOR:
- Always verify current system state before making changes
- Explain actions briefly and clearly
- Identify potential risks and suggest safer alternatives when needed
- Focus on helping users achieve their experimental goals safely
- Use appropriate tools to gather information before providing recommendations

Provide professional, helpful assistance for bioreactor experiment management."""

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