#!/usr/bin/env python3
"""
SQLite Migration Verification Script

This script verifies that the SQLite migration was successful and all
database operations are working correctly.
"""

import sqlite3
import json
from pathlib import Path

def verify_database_setup():
    """Verify that the SQLite database and tables are set up correctly."""
    db_path = Path("wbb.sqlite")

    if not db_path.exists():
        print("❌ ERROR: wbb.sqlite database file not found!")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check for required tables
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
            AND name IN ('warnings', 'blocklist', 'admin_logs', 'rules', 'restart_stage')
        """)

        existing_tables = {row[0] for row in cursor.fetchall()}
        required_tables = {'warnings', 'blocklist', 'admin_logs', 'rules', 'restart_stage'}

        missing_tables = required_tables - existing_tables
        if missing_tables:
            print(f"❌ ERROR: Missing required tables: {', '.join(missing_tables)}")
            conn.close()
            return False

        print("✅ All required tables exist")

        # Verify table schemas
        schema_checks = [
            ("warnings", ["chat_id", "user_id", "warns"]),
            ("blocklist", ["chat_id", "triggers", "mode"]),
            ("admin_logs", ["chat_id", "enabled"]),
            ("rules", ["chat_id", "rules"]),
            ("restart_stage", ["chat_id", "message_id"])
        ]

        for table_name, expected_columns in schema_checks:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [row[1] for row in cursor.fetchall()]

            missing_cols = set(expected_columns) - set(columns)
            if missing_cols:
                print(f"❌ ERROR: Table '{table_name}' missing columns: {', '.join(missing_cols)}")
                conn.close()
                return False

        print("✅ All table schemas are correct")
        conn.close()
        return True

    except Exception as e:
        print(f"❌ ERROR: Database verification failed: {e}")
        return False

def test_blocklist_functions():
    """Test the blocklist functions to ensure they work correctly."""
    try:
        # Import the functions
        import sys
        sys.path.insert(0, '.')

        from wbb.utils.dbfunctions import get_blocklist, update_blocklist

        # Test empty blocklist
        result = get_blocklist(-1001234567890)  # Non-existent chat
        if result != {"triggers": [], "mode": "warn"}:
            print("❌ ERROR: get_blocklist returned unexpected result for non-existent chat")
            return False

        # Test adding triggers
        test_chat_id = -999999999
        test_triggers = ["test", "badword", "spam"]
        test_mode = "delete"

        update_blocklist(test_chat_id, test_triggers, test_mode)

        # Verify the data was stored correctly
        result = get_blocklist(test_chat_id)
        if result["triggers"] != test_triggers or result["mode"] != test_mode:
            print(f"❌ ERROR: Blocklist data not stored correctly. Expected: {test_triggers}, {test_mode}. Got: {result}")
            return False

        print("✅ Blocklist functions work correctly")

        # Clean up test data
        conn = sqlite3.connect("wbb.sqlite")
        conn.execute("DELETE FROM blocklist WHERE chat_id = ?", (test_chat_id,))
        conn.commit()
        conn.close()

        return True

    except Exception as e:
        print(f"❌ ERROR: Blocklist function test failed: {e}")
        return False

def check_for_mongodb_imports():
    """Check for any remaining MongoDB imports in the codebase."""
    try:
        import subprocess
        import os

        # Check for MongoDB imports
        result = subprocess.run(
            ['grep', '-r', 'from.*motor', 'wbb/'],
            capture_output=True,
            text=True,
            cwd=os.getcwd()
        )

        if result.returncode == 0 and result.stdout.strip():
            print("❌ WARNING: Found MongoDB imports:")
            print(result.stdout)
            return False

        result = subprocess.run(
            ['grep', '-r', 'import.*motor', 'wbb/'],
            capture_output=True,
            text=True,
            cwd=os.getcwd()
        )

        if result.returncode == 0 and result.stdout.strip():
            print("❌ WARNING: Found MongoDB imports:")
            print(result.stdout)
            return False

        print("✅ No MongoDB imports found in codebase")
        return True

    except Exception as e:
        print(f"⚠️ WARNING: Could not check for MongoDB imports: {e}")
        return True

def main():
    """Run all verification tests."""
    print("🔍 Starting SQLite Migration Verification...\n")

    all_passed = True

    print("1. Checking database setup...")
    if not verify_database_setup():
        all_passed = False

    print("\n2. Testing blocklist functions...")
    if not test_blocklist_functions():
        all_passed = False

    print("\n3. Checking for MongoDB imports...")
    if not check_for_mongodb_imports():
        all_passed = False

    print("\n" + "="*50)

    if all_passed:
        print("🎉 SUCCESS: SQLite migration verification completed!")
        print("✅ All tests passed. Your bot should now work with SQLite.")
        print("\nNext steps:")
        print("- Start your bot to ensure all features work correctly")
        print("- Test blocklist commands: /addblocklist, /blocklist, /setblockmode")
        print("- Test warning system: /warn, /rmwarns")
        print("- Test admin logging: admin commands should be logged")
    else:
        print("❌ FAILURE: Some verification tests failed.")
        print("Please check the errors above and fix any issues before running your bot.")

    return all_passed

if __name__ == "__main__":
    main()
