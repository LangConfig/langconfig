# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Test PostgreSQL connection"""
from db.database import engine
from sqlalchemy import text
import pytest

def test_connection():
    try:
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
            print('PostgreSQL connection successful')
    except Exception as e:
        pytest.skip(f'PostgreSQL connection unavailable: {e}')

if __name__ == '__main__':
    test_connection()
