"""
Create the database schema for the RDS database.
Run this once to set up all tables.
"""
import psycopg2
import os

DB_CONFIG = {
    'host': '52.206.226.18',
    'port': 5432,
    'database': 'postgres',
    'user': 'postgres',
    'password': 'akilan_123'
}

def create_schema():
    """Create all database tables."""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    try:
        # USERS
        print("Creating users table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS public.users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL
            )
        """)
        
        # ACCOUNT
        print("Creating account table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS public.account (
                id SERIAL PRIMARY KEY,
                user_id INT REFERENCES public.users(id) ON DELETE CASCADE,
                token VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # BUILD
        print("Creating build table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS public.build (
                id SERIAL PRIMARY KEY,
                owner_id INT REFERENCES public.users(id) ON DELETE SET NULL,
                canvas JSONB,
                cf_template JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # BUILD ACCESS
        print("Creating build_access table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS public.build_access (
                id SERIAL PRIMARY KEY,
                build_id INT REFERENCES public.build(id) ON DELETE CASCADE,
                user_id INT REFERENCES public.users(id) ON DELETE CASCADE,
                role VARCHAR(50) NOT NULL
            )
        """)
        
        # ACTIVITY LOG
        print("Creating activity_log table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS public.activity_log (
                id SERIAL PRIMARY KEY,
                build_id INT REFERENCES public.build(id) ON DELETE CASCADE,
                user_id INT REFERENCES public.users(id) ON DELETE SET NULL,
                change TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # DEPLOYMENTS (for CloudFormation stack tracking)
        print("Creating deployments table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS public.deployments (
                id SERIAL PRIMARY KEY,
                build_id INT REFERENCES public.build(id) ON DELETE CASCADE,
                stack_name VARCHAR(255) UNIQUE NOT NULL,
                region VARCHAR(50) NOT NULL,
                status VARCHAR(50) NOT NULL,
                stack_id VARCHAR(255),
                deployed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        print("\n✓ All tables created successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Error creating tables: {str(e)}")
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    print("Creating database schema...")
    print("=" * 50)
    create_schema()
