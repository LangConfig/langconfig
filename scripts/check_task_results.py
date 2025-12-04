# Copyright (c) 2025 Cade Russell
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Quick script to check latest task results from database
"""
import sys
import asyncio
import os

# Add backend to path relative to this script
backend_path = os.path.join(os.path.dirname(__file__), 'backend')
sys.path.insert(0, backend_path)

from sqlalchemy import select, text
from db.database import SessionLocal
from models.task import Task
import json

def main():
    with SessionLocal() as db:
        # Get latest 3 tasks
        result = db.execute(
            text("""
                SELECT id, workflow_id, status, created_at,
                       LENGTH(result::text) as result_length,
                       jsonb_array_length(result->'agent_messages') as message_count
                FROM tasks
                WHERE result IS NOT NULL
                ORDER BY id DESC
                LIMIT 3
            """)
        ).fetchall()

        print("\n=== Latest 3 Tasks ===")
        for row in result:
            print(f"\nTask #{row[0]} (Workflow {row[1]})")
            print(f"  Status: {row[2]}")
            print(f"  Created: {row[3]}")
            print(f"  Result length: {row[4]} chars")
            print(f"  Messages: {row[5]}")

        # Get full result for latest task
        latest = db.execute(
            text("SELECT id, result FROM tasks WHERE result IS NOT NULL ORDER BY id DESC LIMIT 1")
        ).fetchone()

        if latest:
            task_id, result_json = latest
            print(f"\n\n=== Full Result for Task #{task_id} ===")

            if 'agent_messages' in result_json:
                messages = result_json['agent_messages']
                print(f"\nFound {len(messages)} messages:")

                for i, msg in enumerate(messages):
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')
                    content_preview = content[:500] if isinstance(content, str) else str(content)[:500]

                    print(f"\n--- Message {i} ({role}) ---")
                    print(content_preview)
                    if len(str(content)) > 500:
                        print(f"... ({len(str(content)) - 500} more chars)")

            if 'formatted_content' in result_json:
                formatted = result_json['formatted_content']
                print(f"\n\n=== Formatted Content ===")
                print(formatted[:1000])
                if len(formatted) > 1000:
                    print(f"... ({len(formatted) - 1000} more chars)")

if __name__ == "__main__":
    main()
