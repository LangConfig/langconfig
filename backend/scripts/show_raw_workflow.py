# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Show raw workflow configuration JSON"""
from db.database import SessionLocal
from models.workflow import WorkflowProfile
import json
import sys

db = SessionLocal()

workflow_id = int(sys.argv[1]) if len(sys.argv) > 1 else 24

workflow = db.query(WorkflowProfile).filter(WorkflowProfile.id == workflow_id).first()

if workflow:
    print(f"=== WORKFLOW #{workflow_id}: {workflow.name} ===\n")
    print(json.dumps(workflow.configuration, indent=2))
else:
    print(f"Workflow {workflow_id} not found")

db.close()

