import sys
import os

# Add the project root to sys.path so we can import the models and writer
sys.path.append(os.getcwd())

try:
    from crawlernest_db_writer.db_writer import DBWriter
    print("✅ Successfully imported DBWriter")
except ImportError as e:
    print(f"❌ Error importing DBWriter: {e}")
    sys.exit(1)

def test_postgresql_connection():
    # Credentials should be replaced with actual ones
    config = {
        "db_type": "postgres",
        "host": "localhost",
        "database": "clawer",
        "user": "postgres",
        "password": "your_password"
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
