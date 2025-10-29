"""
Check database connection and look for the build table specifically
"""
from database import get_db_connection
import psycopg2

try:
    print("Checking database connection and searching for tables...")
    print("=" * 60)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Check current database
        cursor.execute("SELECT current_database()")
        db_name = cursor.fetchone()[0]
        print(f"Connected to database: {db_name}")
        
        # Check current schema
        cursor.execute("SELECT current_schema()")
        schema = cursor.fetchone()[0]
        print(f"Current schema: {schema}")
        
        # Search for build table in all schemas
        print("\nSearching for 'build' table in all schemas:")
        cursor.execute("""
            SELECT table_schema, table_name 
            FROM information_schema.tables 
            WHERE table_name = 'build'
        """)
        
        build_tables = cursor.fetchall()
        if build_tables:
            for schema, table in build_tables:
                print(f"  Found: {schema}.{table}")
        else:
            print("  'build' table not found in any schema")
        
        # List all tables in public schema
        print("\nAll tables in 'public' schema:")
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        tables = cursor.fetchall()
        if tables:
            for table in tables:
                print(f"  - {table[0]}")
        else:
            print("  No tables found")
            
        # Try to describe build table if it exists
        print("\nTrying to query build table directly...")
        try:
            cursor.execute("SELECT COUNT(*) FROM build")
            count = cursor.fetchone()[0]
            print(f"  ✓ build table exists! Row count: {count}")
            
            # Get columns
            cursor.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'build' AND table_schema = 'public'
                ORDER BY ordinal_position
            """)
            columns = cursor.fetchall()
            print("  Columns:")
            for col_name, col_type in columns:
                print(f"    - {col_name}: {col_type}")
                
        except psycopg2.Error as e:
            print(f"  ✗ Error querying build table: {e}")
            
except Exception as e:
    print(f"Error: {str(e)}")
    import traceback
    traceback.print_exc()
