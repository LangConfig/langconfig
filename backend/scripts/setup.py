#!/usr/bin/env python3
# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
LangConfig Setup Script
=======================

One-command setup for fresh clones. Handles:
1. Environment file creation (.env from .env.example)
2. Python dependency installation
3. Database initialization (tables + extensions)
4. Playwright browser installation (optional)

Usage:
    python backend/scripts/setup.py           # Full setup (from repository root)
    python backend/scripts/setup.py --db-only # Database only
    python backend/scripts/setup.py --help    # Show help
"""

import os
import sys
import base64
import secrets
import subprocess
import argparse
from pathlib import Path


# Tables created by Docker initialization or LangGraph itself do not prove that
# the LangConfig application schema exists. A fresh Compose database contains
# vector_documents before this script runs.
INFRASTRUCTURE_ONLY_TABLES = {
    "alembic_version",
    "checkpoint_blobs",
    "checkpoint_migrations",
    "checkpoint_writes",
    "checkpoints",
    "store",
    "store_migrations",
    "vector_documents",
}

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_step(msg: str):
    print(f"\n{Colors.BLUE}{Colors.BOLD}==>{Colors.RESET} {msg}")

def print_success(msg: str):
    print(f"  {Colors.GREEN}[OK]{Colors.RESET} {msg}")

def print_warning(msg: str):
    print(f"  {Colors.YELLOW}[WARN]{Colors.RESET} {msg}")

def print_error(msg: str):
    print(f"  {Colors.RED}[ERROR]{Colors.RESET} {msg}")

def get_project_root() -> Path:
    """Get the project root directory."""
    # This script is in backend/scripts/, so go up two levels
    return Path(__file__).parent.parent.parent


def has_application_schema(table_names) -> bool:
    """Return whether the database contains LangConfig-owned application tables."""
    return any(table not in INFRASTRUCTURE_ONLY_TABLES for table in table_names)

def check_python_version(version_info=None):
    """Ensure a supported Python 3.11-3.13 runtime is being used."""
    print_step("Checking Python version...")
    version = version_info or sys.version_info
    if version.major != 3 or not (11 <= version.minor < 14):
        print_error(f"Python 3.11-3.13 required, found {version.major}.{version.minor}")
        print_warning("Install Python 3.12 from https://python.org")
        return False
    print_success(f"Python {version.major}.{version.minor}.{version.micro}")
    return True

def check_docker():
    """Check if Docker is available."""
    print_step("Checking Docker...")
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True, text=True, check=True
        )
        print_success(f"Docker found: {result.stdout.strip()}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print_warning("Docker not found - you'll need to set up PostgreSQL manually")
        return False


def ensure_env_encryption_key(contents: str) -> tuple[str, bool]:
    """Populate a blank or shipped-placeholder APP_ENCRYPTION_KEY."""
    insecure_values = {"", "replace-with-a-generated-fernet-key"}
    lines = contents.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if not line.startswith("APP_ENCRYPTION_KEY="):
            continue
        value = line.split("=", 1)[1].strip()
        if value not in insecure_values:
            return contents, False
        newline = "\r\n" if line.endswith("\r\n") else "\n"
        generated = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")
        lines[index] = f"APP_ENCRYPTION_KEY={generated}{newline}"
        return "".join(lines), True
    return contents, False

def setup_env_file():
    """Create .env from .env.example if it doesn't exist."""
    print_step("Setting up environment file...")
    root = get_project_root()
    env_file = root / ".env"
    env_example = root / ".env.example"
    
    if not env_example.exists():
        print_error(".env.example not found!")
        return False

    if env_file.exists():
        contents = env_file.read_text(encoding="utf-8")
        rendered, generated = ensure_env_encryption_key(contents)
        if generated:
            env_file.write_text(rendered, encoding="utf-8")
            print_success("Generated a unique APP_ENCRYPTION_KEY in existing .env")
        else:
            print_success(".env already exists")
        return True

    contents = env_example.read_text(encoding="utf-8")
    rendered, generated = ensure_env_encryption_key(contents)
    env_file.write_text(rendered, encoding="utf-8")
    print_success("Created .env from .env.example")
    if generated:
        print_success("Generated a unique APP_ENCRYPTION_KEY")
    print_warning("Edit .env to add your API keys (OPENAI_API_KEY, etc.)")
    return True

def install_dependencies():
    """Install Python dependencies."""
    print_step("Installing Python dependencies...")
    root = get_project_root()
    requirements = root / "backend" / "requirements.txt"
    
    if not requirements.exists():
        print_error("requirements.txt not found!")
        return False
    
    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--upgrade",
                "-r",
                str(requirements),
            ],
            check=True
        )
        print_success("Dependencies installed")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to install dependencies: {e}")
        return False

def start_database():
    """Start PostgreSQL via Docker Compose."""
    print_step("Starting PostgreSQL database...")
    root = get_project_root()
    
    try:
        subprocess.run(
            ["docker", "compose", "up", "-d", "postgres"],
            cwd=root, check=True
        )
        print_success("PostgreSQL container started")
        
        # Wait for database to be ready
        print("  Waiting for database to be ready...")
        import time
        for i in range(30):
            try:
                result = subprocess.run(
                    [
                        "docker", "compose", "exec", "-T", "postgres",
                        "sh", "-c",
                        'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"',
                    ],
                    cwd=root, capture_output=True, check=True
                )
                print_success("Database is ready")
                return True
            except subprocess.CalledProcessError:
                time.sleep(1)
        
        print_warning("Database may not be fully ready yet")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to start database: {e}")
        return False
    except FileNotFoundError:
        print_warning("Docker not available - skipping container start")
        return True

def init_database(reset_db: bool = False):
    """Initialize database tables from SQLAlchemy models."""
    print_step("Initializing database tables...")
    
    # Add backend to path
    root = get_project_root()
    backend_path = root / "backend"
    sys.path.insert(0, str(backend_path))
    
    try:
        # Import all models to register them with Base
        from models import core, workflow, deep_agent, audit_log, settings
        from models import custom_tool, execution_event, local_model, background_task
        from models import skill
        
        # Import and run init_db
        from db.database import Base, engine
        from sqlalchemy import text, inspect
        
        # Create extensions first
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\""))
        print_success("PostgreSQL extensions enabled (pgvector, uuid-ossp)")
        
        # Check if this looks like a fresh install or existing data
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        if has_application_schema(existing_tables) and not reset_db:
            print_success("Existing database detected - preserving tables and data")
            try:
                subprocess.run(
                    [sys.executable, "-m", "alembic", "upgrade", "head"],
                    cwd=backend_path,
                    check=True,
                )
                print_success("Database migrations applied")
            except subprocess.CalledProcessError as e:
                print_error(f"Alembic migration failed: {e}")
                return False
            return True

        if existing_tables and reset_db:
            print_warning("Existing tables found - reset requested, dropping schema...")
            with engine.begin() as conn:
                conn.execute(text("DROP SCHEMA public CASCADE"))
                conn.execute(text("CREATE SCHEMA public"))
                conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\""))
            print_success("Old tables dropped")
        
        # Create all tables fresh
        Base.metadata.create_all(bind=engine)
        print_success("Database tables created")
        
        # This repository's baseline migration describes an older, pre-Alembic
        # schema and cannot create a blank database. For a verified fresh install,
        # current SQLAlchemy metadata is the schema authority; stamp the discovered
        # Alembic head so future upgrades start from the correct revision.
        try:
            subprocess.run(
                [sys.executable, "-m", "alembic", "stamp", "head"],
                cwd=backend_path,
                check=True,
            )
            print_success("Alembic version stamped at current head")
        except subprocess.CalledProcessError as e:
            print_error(f"Could not stamp Alembic head: {e}")
            return False
        
        return True
        
    except Exception as e:
        print_error(f"Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def install_playwright():
    """Install Playwright browsers (optional)."""
    print_step("Installing Playwright browsers (for browser automation tools)...")
    
    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True
        )
        print_success("Playwright Chromium installed")
        return True
    except subprocess.CalledProcessError as e:
        print_warning(f"Playwright install failed (optional): {e}")
        return True  # Non-fatal
    except FileNotFoundError:
        print_warning("Playwright not found - browser tools will be unavailable")
        return True  # Non-fatal

def seed_agent_templates():
    """Seed default agent templates."""
    print_step("Seeding agent templates...")

    root = get_project_root()
    backend_path = root / "backend"
    init_script = backend_path / "db" / "init_deepagents.py"

    if not init_script.exists():
        print_warning("Agent template seed script not found - skipping")
        return True

    try:
        subprocess.run(
            [sys.executable, str(init_script)],
            cwd=backend_path, check=True
        )
        print_success("Agent templates seeded")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Template seeding failed: {e}")
        return False

def seed_custom_tools():
    """Seed default custom tools (Nano Banana, etc.)."""
    print_step("Seeding custom tools...")

    root = get_project_root()
    backend_path = root / "backend"
    init_script = backend_path / "db" / "init_custom_tools.py"

    if not init_script.exists():
        print_warning("Custom tool seed script not found - skipping")
        return True

    try:
        subprocess.run(
            [sys.executable, str(init_script)],
            cwd=backend_path, check=True
        )
        print_success("Custom tools seeded (Nano Banana Pro, etc.)")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Custom tool seeding failed: {e}")
        return False

def seed_langconfig_dev_data():
    """Seed generic LangConfig project/workflow demo data."""
    print_step("Seeding generic LangConfig demo data...")

    root = get_project_root()
    backend_path = root / "backend"
    init_script = backend_path / "db" / "seed_langconfig_dev.py"

    if not init_script.exists():
        print_warning("LangConfig demo data seed script not found - skipping")
        return True

    try:
        subprocess.run(
            [sys.executable, str(init_script)],
            cwd=backend_path, check=True
        )
        print_success("Generic LangConfig demo data seeded")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"LangConfig demo data seeding failed: {e}")
        return False

def print_next_steps():
    """Print instructions for what to do next."""
    print(f"\n{Colors.GREEN}{Colors.BOLD}Setup Complete!{Colors.RESET}\n")
    print("Next steps:")
    print(f"  1. Edit {Colors.BOLD}.env{Colors.RESET} to add your API keys:")
    print("     - OPENAI_API_KEY=sk-...")
    print("     - ANTHROPIC_API_KEY=sk-ant-...")
    print("     - GOOGLE_API_KEY=AIza...")
    print()
    print(f"  2. Start the backend:")
    print(f"     {Colors.BOLD}cd backend && python main.py{Colors.RESET}")
    print()
    print(f"  3. Start the frontend (in another terminal):")
    print(f"     {Colors.BOLD}npm ci && npm run dev{Colors.RESET}")
    print()
    print(f"  4. Open {Colors.BOLD}http://localhost:1425{Colors.RESET} in your browser")
    print(f"     Backend health: {Colors.BOLD}http://127.0.0.1:8780/health/{Colors.RESET}")
    print()

def main():
    parser = argparse.ArgumentParser(
        description="LangConfig setup script for fresh installations"
    )
    parser.add_argument(
        "--db-only", action="store_true",
        help="Only initialize the database (skip deps install)"
    )
    parser.add_argument(
        "--skip-docker", action="store_true",
        help="Skip Docker container startup (use existing database)"
    )
    parser.add_argument(
        "--skip-playwright", action="store_true",
        help="Skip Playwright browser installation"
    )
    parser.add_argument(
        "--reset-db", action="store_true",
        help="DANGER: drop existing database tables before creating a fresh schema"
    )
    args = parser.parse_args()
    
    print(f"\n{Colors.BOLD}LangConfig Setup{Colors.RESET}")
    print("=" * 40)
    
    # Change to backend directory
    root = get_project_root()
    os.chdir(root / "backend")
    
    success = True
    
    # Python version check
    if not check_python_version():
        sys.exit(1)
    
    if not args.db_only:
        # Environment file
        if not setup_env_file():
            success = False
        
        # Dependencies
        if not install_dependencies():
            success = False
    
    # Docker check
    has_docker = check_docker()
    
    # Start database
    if has_docker and not args.skip_docker:
        if not start_database():
            success = False
    
    # Initialize database
    if not init_database(reset_db=args.reset_db):
        success = False
    
    # Seed templates
    if not seed_agent_templates():
        success = False

    # Seed custom tools
    if not seed_custom_tools():
        success = False

    # Seed generic project/workflow demo data
    if not seed_langconfig_dev_data():
        success = False

    # Playwright (optional)
    if not args.db_only and not args.skip_playwright:
        install_playwright()
    
    if success:
        print_next_steps()
    else:
        print(f"\n{Colors.RED}Setup completed with errors. Check the output above.{Colors.RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()
