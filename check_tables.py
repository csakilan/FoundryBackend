"""
Check what tables exist in the database
"""
from database import get_db_connection

try:
    print("Checking existing tables in database...")
    print("=" * 60)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Query to list all tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        tables = cursor.fetchall()
        
        if tables:
            print(f"\nFound {len(tables)} table(s):")
            for table in tables:
                print(f"  - {table[0]}")
                
                # Get column details for each table
                cursor.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = %s
                    ORDER BY ordinal_position
                """, (table[0],))
                
                columns = cursor.fetchall()
                for col in columns:
                    nullable = "NULL" if col[2] == 'YES' else "NOT NULL"
                    print(f"      {col[0]}: {col[1]} {nullable}")
                print()
        else:
            print("\nNo tables found in database")
            
except Exception as e:
    print(f"Error: {str(e)}")
    import traceback
    traceback.print_exc()
