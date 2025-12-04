# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import sys
sys.path.insert(0, '.')
from database import SessionLocal
from models.core import Task
import json

db = SessionLocal()
# Get the most recent completed task
task = db.query(Task).filter(Task.status == 'COMPLETED').order_by(Task.id.desc()).first()
if task and task.result:
    print('Task ID:', task.id)
    print('Result keys:', list(task.result.keys()))
    print('\n=== FORMATTED CONTENT ===')
    print(task.result.get('formatted_content', '')[:500])
    print('\n=== AGENT MESSAGES ===')
    messages = task.result.get('agent_messages', [])
    print(f'Number of messages: {len(messages)}')
    if messages:
        for i, msg in enumerate(messages[:5]):  # Show first 5
            print(f'\nMessage {i+1}:')
            print(f'  Keys: {list(msg.keys())}')
            print(f'  Role: {msg.get("role")}')
            content = str(msg.get("content", ""))
            print(f'  Content length: {len(content)}')
            print(f'  Content preview: {content[:300]}')
else:
    print('No completed task found')
db.close()
