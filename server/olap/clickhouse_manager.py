"""
ClickHouse manager for handling connections and data operations
"""
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, List

# Try to import clickhouse-connect, but handle if not available
try:
    from clickhouse_connect import get_client
    from clickhouse_connect.driver.client import Client
    CLICKHOUSE_AVAILABLE = True
except ImportError:
    # Create mock classes for type hints when clickhouse-connect is not available
    class Client:
        def command(self, sql):
            pass
        def insert(self, table, data):
            pass
        def close(self):
            pass
    def get_client(*args, **kwargs):
        return Client()
    CLICKHOUSE_AVAILABLE = False

class ClickHouseManager:
    """Manages ClickHouse connections and data operations for IMN"""
    
    def __init__(self, host: str = None, port: Optional[int] = None, database: str = None, 
                 username: str = None, password: str = None):
        """
        Initialize ClickHouse manager with connection parameters
        
        Args:
            host: ClickHouse server host
            port: ClickHouse server port
            database: Database name
            username: Username for authentication
            password: Password for authentication
        """
        self.host = host or str(os.environ.get('CLICKHOUSE_HOST', 'localhost'))
        self.port = port or int(os.environ.get('CLICKHOUSE_PORT', 8123))
        self.database = database or str(os.environ.get('CLICKHOUSE_DATABASE', 'imn'))
        self.username = username or str(os.environ.get('CLICKHOUSE_USERNAME', 'admin'))
        self.password = password or str(os.environ.get('CLICKHOUSE_PASSWORD', ''))
        
        self.client: Optional[Client] = None
        self.connected = False
        
    def connect(self) -> bool:
        """
        Establish connection to ClickHouse server
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        if not CLICKHOUSE_AVAILABLE:
            print("[ClickHouse] clickhouse-connect not available")
            return False
            
        try:
            self.client = get_client(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                database=self.database
            )
            self.connected = True
            print(f"[ClickHouse] Connected to {self.host}:{self.port}/{self.database}")
            return True
        except Exception as e:
            print(f"[ClickHouse] Connection failed: {e}")
            self.connected = False
            return False
    
    def initialize_tables(self) -> bool:
        """
        Initialize all required tables in ClickHouse
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        if not self.connected or not self.client:
            print("[ClickHouse] Not connected to database")
            return False
            
        try:
            # Import schema definitions
            from .clickhouse_schema import CREATE_TABLE_STATEMENTS
            
            # Execute each table creation statement separately
            for i, statement in enumerate(CREATE_TABLE_STATEMENTS):
                try:
                    # Strip any leading/trailing whitespace
                    clean_statement = statement.strip()
                    if clean_statement:
                        print(f"[ClickHouse] Executing table creation {i+1}/{len(CREATE_TABLE_STATEMENTS)}")
                        self.client.command(clean_statement)
                        print(f"[ClickHouse] Table {i+1} created successfully")
                except Exception as e:
                    print(f"[ClickHouse] Failed to create table {i+1}: {e}")
                    print(f"[ClickHouse] Statement was: {clean_statement[:100]}...")
                    return False
            
            print("[ClickHouse] All tables initialized successfully")
            return True
        except Exception as e:
            print(f"[ClickHouse] Table initialization failed: {e}")
            return False
    
    def insert_measurement(self, data: Dict[str, Any]) -> bool:
        """
        Insert measurement result into ClickHouse
        
        Args:
            data: Dictionary containing measurement data
            
        Returns:
            bool: True if insertion successful, False otherwise
        """
        if not self.connected or not self.client:
            print("[ClickHouse] Not connected to database")
            return False
            
        try:
            # Prepare data for insertion
            insert_data = [{
                'workflow_id': data.get('workflow_id', ''),
                'agent_id': data.get('agent_id', ''),
                'module_name': data.get('module_name', ''),
                'created_at': data.get('created_at', datetime.utcnow()),
                'completed_at': data.get('completed_at', datetime.utcnow()),
                'measurement_data': json.dumps(data.get('measurement_data', {})),
                'agent_hostname': data.get('agent_hostname', ''),
                'agent_name': data.get('agent_name', ''),
                'agent_pid': data.get('agent_pid', 0),
                'system_machine': data.get('system_machine', ''),
                'system_node_name': data.get('system_node_name', ''),
                'system_platform': data.get('system_platform', ''),
                'system_processor': data.get('system_processor', ''),
                'system_release': data.get('system_release', ''),
                'system_version': data.get('system_version', ''),
                'network_interfaces': json.dumps(data.get('network_interfaces', {})),
                'user_name': data.get('user_name', ''),
                'user_uid': data.get('user_uid', 0),
                'user_gid': data.get('user_gid', 0),
                'user_home_dir': data.get('user_home_dir', ''),
                'user_shell': data.get('user_shell', ''),
                'request_data': json.dumps(data.get('request_data', {})),
                'success': data.get('success', True)
            }]
            
            # Insert data
            self.client.insert('measurements', insert_data)
            print(f"[ClickHouse] Measurement inserted for workflow {data.get('workflow_id', 'unknown')}")
            return True
        except Exception as e:
            print(f"[ClickHouse] Measurement insertion failed: {e}")
            return False
    
    def insert_heartbeat(self, data: Dict[str, Any]) -> bool:
        """
        Insert agent heartbeat into ClickHouse
        
        Args:
            data: Dictionary containing heartbeat data
            
        Returns:
            bool: True if insertion successful, False otherwise
        """
        if not self.connected or not self.client:
            print("[ClickHouse] Not connected to database")
            return False
            
        try:
            # Prepare data for insertion
            insert_data = [{
                'agent_id': data.get('agent_id', ''),
                'agent_name': data.get('agent_name', ''),
                'hostname': data.get('hostname', ''),
                'timestamp': data.get('timestamp', datetime.utcnow()),
                'alive': data.get('alive', True),
                'total_heartbeats': data.get('total_heartbeats', 0),
                'load_avg_1m': data.get('load_avg_1m', 0.0),
                'load_avg_5m': data.get('load_avg_5m', 0.0),
                'load_avg_15m': data.get('load_avg_15m', 0.0),
                'config': json.dumps(data.get('config', {}))
            }]
            
            # Insert data
            self.client.insert('agent_heartbeats', insert_data)
            print(f"[ClickHouse] Heartbeat inserted for agent {data.get('agent_id', 'unknown')}")
            return True
        except Exception as e:
            print(f"[ClickHouse] Heartbeat insertion failed: {e}")
            return False
    
    def insert_module_state(self, data: Dict[str, Any]) -> bool:
        """
        Insert module state transition into ClickHouse
        
        Args:
            data: Dictionary containing state transition data
            
        Returns:
            bool: True if insertion successful, False otherwise
        """
        if not self.connected or not self.client:
            print("[ClickHouse] Not connected to database")
            return False
            
        try:
            # Prepare data for insertion
            insert_data = [{
                'workflow_id': data.get('workflow_id', ''),
                'agent_id': data.get('agent_id', ''),
                'module_name': data.get('module_name', ''),
                'state': data.get('state', ''),
                'timestamp': data.get('timestamp', datetime.utcnow()),
                'error_message': data.get('error_message', None),
                'details': json.dumps(data.get('details', {}))
            }]
            
            # Insert data
            self.client.insert('module_states', insert_data)
            print(f"[ClickHouse] Module state inserted for workflow {data.get('workflow_id', 'unknown')}")
            return True
        except Exception as e:
            print(f"[ClickHouse] Module state insertion failed: {e}")
            return False
    
    def close(self):
        """Close ClickHouse connection"""
        if self.client:
            try:
                self.client.close()
                self.connected = False
                print("[ClickHouse] Connection closed")
            except Exception as e:
                print(f"[ClickHouse] Error closing connection: {e}")