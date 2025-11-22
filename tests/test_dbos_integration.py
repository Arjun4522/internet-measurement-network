#!/usr/bin/env python3
"""
Test script for DBOS integration with the IMN Python server.
"""

import os
import sys
import asyncio
import json
from datetime import datetime

# Add the server directory to the path so we can import the DBOS client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

async def test_dbos_client():
    """Test the DBOS client functionality"""
    print("Testing DBOS client integration...")
    
    try:
        # Import the DBOS client
        from server.dbos_client import DBOSClient, initialize_dbos_client, shutdown_dbos_client
        
        # Initialize the DBOS client
        print("Initializing DBOS client...")
        dbos_client = DBOSClient("localhost:50051")
        await dbos_client.connect()
        print("DBOS client connected successfully!")
        
        # Test registering an agent
        print("\nTesting agent registration...")
        from server.models import AgentInfo
        test_agent = AgentInfo(
            agent_id="test-agent-123",
            hostname="test-host",
            alive=True,
            last_seen=datetime.now(),
            first_seen=datetime.now(),
            config={"test": "config"},
            total_heartbeats=1
        )
        
        success = await dbos_client.register_agent(test_agent)
        if success:
            print("✓ Agent registered successfully!")
        else:
            print("✗ Failed to register agent")
            
        # Test getting the agent back
        print("\nTesting agent retrieval...")
        retrieved_agent = await dbos_client.get_agent("test-agent-123")
        if retrieved_agent:
            print("✓ Agent retrieved successfully!")
            print(f"  Agent ID: {retrieved_agent['agent_id']}")
            print(f"  Hostname: {retrieved_agent['hostname']}")
            print(f"  Alive: {retrieved_agent['alive']}")
        else:
            print("✗ Failed to retrieve agent")
            
        # Test storing a result
        print("\nTesting result storage...")
        test_result_data = json.dumps({
            "target": "8.8.8.8",
            "latency_ms": 25,
            "timestamp": "2023-01-01T00:00:00Z"
        }).encode('utf-8')
        
        success = await dbos_client.store_result("test-agent-123", "test-result-123", "ping_module", test_result_data)
        if success:
            print("✓ Result stored successfully!")
        else:
            print("✗ Failed to store result")
            
        # Test getting the result back
        print("\nTesting result retrieval...")
        retrieved_result = await dbos_client.get_result("test-agent-123", "test-result-123")
        if retrieved_result:
            print("✓ Result retrieved successfully!")
            try:
                result_json = json.loads(retrieved_result.decode('utf-8'))
                print(f"  Result data: {result_json}")
            except Exception as e:
                print(f"  Raw result data: {retrieved_result}")
        else:
            print("✗ Failed to retrieve result")
            
        # Close the connection
        print("\nClosing DBOS client connection...")
        await dbos_client.disconnect()
        print("DBOS client disconnected successfully!")
        
    except Exception as e:
        print(f"Error during DBOS client test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_dbos_client())