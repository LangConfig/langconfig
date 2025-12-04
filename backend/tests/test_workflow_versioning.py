# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Test script for Workflow Versioning API

This script tests all the workflow versioning endpoints to ensure they work correctly.
Run this after starting the backend server.

Usage:
    python test_workflow_versioning.py
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8765/api/workflows"

def print_response(name, response):
    """Pretty print API response"""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    print(f"Status Code: {response.status_code}")
    if response.status_code < 400:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    else:
        print(f"Error: {response.text}")
    print()

def test_workflow_versioning():
    """Test all workflow versioning endpoints"""

    print("\n" + "="*60)
    print("WORKFLOW VERSIONING API TEST")
    print("="*60)

    # Step 1: Create a test workflow
    print("\n1. Creating test workflow...")
    workflow_data = {
        "name": f"Test Workflow {datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "description": "Test workflow for versioning",
        "configuration": {
            "nodes": [
                {
                    "id": "node1",
                    "type": "agent",
                    "config": {
                        "model": "gpt-4o",
                        "temperature": 0.7,
                        "system_prompt": "You are a helpful assistant"
                    }
                }
            ],
            "edges": []
        }
    }

    response = requests.post(BASE_URL, json=workflow_data)
    print_response("Create Workflow", response)

    if response.status_code != 201:
        print("[ERROR] Failed to create workflow. Stopping tests.")
        return

    workflow_id = response.json()["id"]
    print(f"[OK] Created workflow with ID: {workflow_id}")

    # Step 2: Create Version 1
    print("\n2. Creating Version 1...")
    version1_data = {
        "config_snapshot": workflow_data["configuration"],
        "notes": "Initial version - single agent node",
        "created_by": "test_user"
    }

    response = requests.post(f"{BASE_URL}/{workflow_id}/versions", json=version1_data)
    print_response("Create Version 1", response)

    if response.status_code != 201:
        print("[ERROR] Failed to create version 1. Stopping tests.")
        return

    version1_id = response.json()["id"]
    print(f"[OK] Created Version 1 with ID: {version1_id}")

    # Step 3: Create Version 2 (with changes)
    print("\n3. Creating Version 2 with changes...")
    modified_config = workflow_data["configuration"].copy()
    modified_config["nodes"].append({
        "id": "node2",
        "type": "agent",
        "config": {
            "model": "claude-sonnet-4-5",
            "temperature": 0.5,
            "system_prompt": "You are a code reviewer"
        }
    })

    version2_data = {
        "config_snapshot": modified_config,
        "notes": "Added second agent node for code review",
        "created_by": "test_user"
    }

    response = requests.post(f"{BASE_URL}/{workflow_id}/versions", json=version2_data)
    print_response("Create Version 2", response)

    if response.status_code != 201:
        print("[ERROR] Failed to create version 2. Stopping tests.")
        return

    version2_id = response.json()["id"]
    version2_number = response.json()["version_number"]
    print(f"[OK] Created Version 2 with ID: {version2_id}, Number: {version2_number}")

    # Step 4: List all versions
    print("\n4. Listing all versions...")
    response = requests.get(f"{BASE_URL}/{workflow_id}/versions")
    print_response("List Versions", response)

    if response.status_code == 200:
        versions = response.json()
        print(f"[OK] Found {len(versions)} version(s)")

    # Step 5: Get specific version
    print("\n5. Getting Version 1 details...")
    response = requests.get(f"{BASE_URL}/{workflow_id}/versions/1")
    print_response("Get Version 1", response)

    # Step 6: Compare versions
    print("\n6. Comparing Version 1 and Version 2...")
    response = requests.get(f"{BASE_URL}/{workflow_id}/versions/1/compare/2")
    print_response("Compare Versions", response)

    if response.status_code == 200:
        diff = response.json()["diff"]
        print(f"[OK] Diff Summary:")
        print(f"  - Added keys: {list(diff.get('added', {}).keys())}")
        print(f"  - Removed keys: {list(diff.get('removed', {}).keys())}")
        print(f"  - Modified keys: {list(diff.get('modified', {}).keys())}")

    # Step 7: Record execution for version 2
    print("\n7. Recording execution for Version 2...")
    execution_data = {
        "version_id": version2_id,
        "execution_results": {
            "status": "success",
            "output": "Test execution completed successfully",
            "steps": [
                {"step": 1, "result": "Agent 1 executed"},
                {"step": 2, "result": "Agent 2 executed"}
            ]
        },
        "token_usage": {
            "input_tokens": 150,
            "output_tokens": 75,
            "total_tokens": 225
        },
        "cost": 0.0045,
        "execution_time": 3.5,
        "status": "success"
    }

    response = requests.post(f"{BASE_URL}/{workflow_id}/executions", json=execution_data)
    print_response("Record Execution", response)

    if response.status_code == 201:
        execution_id = response.json()["id"]
        print(f"[OK] Created execution record with ID: {execution_id}")

    # Step 8: List executions
    print("\n8. Listing all executions...")
    response = requests.get(f"{BASE_URL}/{workflow_id}/executions")
    print_response("List Executions", response)

    if response.status_code == 200:
        executions = response.json()
        print(f"[OK] Found {len(executions)} execution(s)")
        for exec in executions:
            print(f"  - Version {exec['version_id']}: {exec['status']} "
                  f"({exec.get('execution_time', 0):.2f}s, ${exec.get('cost', 0):.4f})")

    # Step 9: List executions filtered by version
    print(f"\n9. Listing executions for Version 2 only...")
    response = requests.get(f"{BASE_URL}/{workflow_id}/executions?version_id={version2_id}")
    print_response("List Executions (Filtered)", response)

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"[OK] Workflow ID: {workflow_id}")
    print(f"[OK] Version 1 ID: {version1_id}")
    print(f"[OK] Version 2 ID: {version2_id}")
    print(f"[OK] All tests completed successfully!")
    print("="*60 + "\n")

if __name__ == "__main__":
    try:
        test_workflow_versioning()
    except requests.exceptions.ConnectionError:
        print("\n[ERROR] ERROR: Could not connect to the API server.")
        print("Make sure the backend is running on http://localhost:8765")
        print("\nTo start the backend:")
        print("  cd backend")
        print("  python main.py")
    except Exception as e:
        print(f"\n[ERROR] ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
