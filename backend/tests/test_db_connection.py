# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Test PostgreSQL connection"""
from db.database import engine
from sqlalchemy import text

def test_connection():
    try:
        with engine.connect() as conn:
            result = conn.execute(text('SELECT 1'))
            print('PostgreSQL connection successful')
            return True
    except Exception as e:
        print(f'PostgreSQL connection failed: {e}')
        return False

if __name__ == '__main__':
    test_connection()
