import sys
import os
from pathlib import Path

# Add module roots used by the modularized layout.
ROOT = Path(__file__).resolve().parent
MODULE_DIRS = [
    ROOT / "crawlernest-core",
    ROOT / "crawlernest-db-writer",
]

for mod_dir in MODULE_DIRS:
    if mod_dir.is_dir():
        sys.path.insert(0, str(mod_dir))

try:
    from db_writer import DBWriter
    print("✅ Successfully imported DBWriter")
except ImportError as e:
    print(f"❌ Error importing DBWriter: {e}")
    sys.exit(1)

def test_postgresql_connection():
    config = {
        "db_type": "postgres",
        "host": "localhost",
        "database": "clawer",
        "user": "test",
        "password": ""
    }
    
    print(f"--- Testing PostgreSQL Initialization ---")
    try:
        writer = DBWriter(**config)
        print("✅ Connection established!")
        
        run_id = writer.start_crawl_run("Verification Source", notes="Test run from verification script")
        print(f"✅ Created crawl run with ID: {run_id}")
        
        writer.commit()
        writer.close()
        print("✅ Connection closed safely.")
    except Exception as e:
        print(f"❌ Connection failed (as expected if no DB is running): {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--run":
        test_postgresql_connection()
    else:
        print("This is a verification script for the DB writer logic.")
        print("To attempt a real connection, run: python verify_db.py --run")
