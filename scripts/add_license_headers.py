#!/usr/bin/env python3
"""
Automated License Header Injection Script
Adds MIT license headers to all source files in the project.
"""

import os
import sys
from pathlib import Path

# CONFIGURATION
PROJECT_ROOT = Path(__file__).parent.parent
COPYRIGHT_HOLDER = "Cade Russell"
COPYRIGHT_YEAR = "2025"

# License headers for different file types
HEADERS = {
    "python": f"""# Copyright (c) {COPYRIGHT_YEAR} {COPYRIGHT_HOLDER}
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

""",
    "typescript": f"""/**
 * Copyright (c) {COPYRIGHT_YEAR} {COPYRIGHT_HOLDER}
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

""",
    "javascript": f"""/**
 * Copyright (c) {COPYRIGHT_YEAR} {COPYRIGHT_HOLDER}
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

""",
}

# File extensions to process
FILE_TYPES = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
}

# Directories to skip
SKIP_DIRS = {
    "node_modules",
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    ".next",
    "coverage",
    ".gemini",
}

# Files to skip
SKIP_FILES = {
    "vite-env.d.ts",  # Generated file
    "setupTests.ts",  # Generated file
}


def has_license_header(content: str, file_type: str) -> bool:
    """Check if file already has a license header."""
    header_snippet = "This source code is licensed under the MIT license"
    return header_snippet in content[:500]  # Check first 500 chars


def add_header_to_file(file_path: Path, file_type: str) -> bool:
    """Add license header to a file if it doesn't already have one."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"❌ Error reading {file_path}: {e}")
        return False

    # Skip if already has header
    if has_license_header(content, file_type):
        return False

    # Get appropriate header
    header = HEADERS.get(file_type, "")
    if not header:
        return False

    # Handle shebang for Python files
    if file_type == "python" and content.startswith("#!"):
        lines = content.split("\n", 1)
        shebang = lines[0] + "\n"
        rest = lines[1] if len(lines) > 1 else ""
        new_content = shebang + header + rest
    else:
        new_content = header + content

    # Write updated content
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return True
    except Exception as e:
        print(f"❌ Error writing {file_path}: {e}")
        return False


def should_skip(path: Path) -> bool:
    """Check if path should be skipped."""
    # Skip if any parent directory is in SKIP_DIRS
    for part in path.parts:
        if part in SKIP_DIRS:
            return True

    # Skip specific files
    if path.name in SKIP_FILES:
        return True

    return False


def process_directory(root_dir: Path, dry_run: bool = False):
    """Process all eligible files in directory tree."""
    modified_count = 0
    skipped_count = 0
    total_count = 0

    print(f"🔍 Scanning {root_dir}...")
    print()

    for file_path in root_dir.rglob("*"):
        # Skip directories and non-files
        if not file_path.is_file():
            continue

        # Skip files we don't want to process
        if should_skip(file_path):
            continue

        # Check if file type is eligible
        suffix = file_path.suffix
        if suffix not in FILE_TYPES:
            continue

        total_count += 1
        file_type = FILE_TYPES[suffix]
        relative_path = file_path.relative_to(root_dir)

        if dry_run:
            # Just check if it needs a header
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if has_license_header(content, file_type):
                    skipped_count += 1
                else:
                    print(f"📝 Would add header: {relative_path}")
                    modified_count += 1
            except Exception as e:
                print(f"❌ Error checking {relative_path}: {e}")
        else:
            # Actually add the header
            if add_header_to_file(file_path, file_type):
                print(f"✅ Added header: {relative_path}")
                modified_count += 1
            else:
                skipped_count += 1

    print()
    print("=" * 60)
    print(f"📊 Summary:")
    print(f"   Total files scanned: {total_count}")
    print(f"   Headers added: {modified_count}")
    print(f"   Skipped (already had header): {skipped_count}")
    print("=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Add MIT license headers to source files"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=str(PROJECT_ROOT),
        help="Directory to process (default: project root)",
    )

    args = parser.parse_args()

    target_dir = Path(args.dir)
    if not target_dir.exists():
        print(f"❌ Directory not found: {target_dir}")
        sys.exit(1)

    if args.dry_run:
        print("🔍 DRY RUN MODE - No files will be modified")
        print()

    process_directory(target_dir, dry_run=args.dry_run)

    if args.dry_run:
        print()
        print("ℹ️  Run without --dry-run to apply changes")
