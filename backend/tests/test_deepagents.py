# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from models.deep_agent import DeepAgentTemplate
from db.database import SessionLocal

session = SessionLocal()
try:
    count = session.query(DeepAgentTemplate).count()
    print(f'Total deep agents: {count}')

    # Try to fetch one
    agent = session.query(DeepAgentTemplate).first()
    if agent:
        print(f'Sample agent: {agent.name}')
    print('OK: DeepAgentTemplate query successful')
except Exception as e:
    print(f'ERROR: {e}')
    import traceback
    traceback.print_exc()
finally:
    session.close()
