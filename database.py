"""
Database connection and operations for RDS PostgreSQL.
"""
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from typing import Dict, Any, Optional
import os
import random
from contextlib import contextmanager
from dotenv import load_dotenv

# Load environment variables from .env file
# Use override=True to ensure .env values take precedence over system environment
load_dotenv(override=True)

# RDS Connection Configuration
DB_CONFIG = {
    'host': os.getenv('RDS_HOST', '52.206.226.18'),
    'port': int(os.getenv('RDS_PORT', 5432)),
    'database': os.getenv('RDS_DATABASE', 'postgres'),
    'user': os.getenv('RDS_USER', 'postgres'),
    'password': os.getenv('RDS_PASSWORD'),
    'sslmode': 'require'  # RDS requires SSL encryption
}


@contextmanager
def get_db_connection():
    """
    Context manager for database connections.
    Automatically handles connection closing.
    
    Usage:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
    """
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()


def test_connection():
    """
    Test database connection.
    Returns True if connection successful, False otherwise.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            print("✓ Database connection successful!")
            return True
    except Exception as e:
        print(f"✗ Database connection failed: {str(e)}")
        return False



def generate_8_digit_id() -> int:
    """
    Generate a random 8-digit integer ID.
    Range: 10000000 to 99999999
    
    Returns:
        8-digit integer
    """
    return random.randint(10000000, 99999999)


def save_build(owner_id: int, canvas: Dict[str, Any], cf_template: Optional[Dict[str, Any]] = None) -> int:
    """
    Save a new build with canvas and optional CloudFormation template.
    Generates an 8-digit unique ID for the build.
    
    Args:
        owner_id: User ID of the build owner
        canvas: Canvas JSON from frontend
        cf_template: Generated CloudFormation template JSON
        
    Returns:
        build_id: 8-digit ID of the created build
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Try up to 10 times to insert with a unique ID
        max_attempts = 10
        for attempt in range(max_attempts):
            build_id = generate_8_digit_id()
            
            try:
                cursor.execute(
                    """
                    INSERT INTO build (id, owner_id, canvas, cf_template)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (build_id, owner_id, Json(canvas), Json(cf_template) if cf_template else None)
                )
                # If successful, retrieve the ID and return
                build_id = cursor.fetchone()[0]
                print(f"✓ Build saved with ID: {build_id}")
                return build_id
                
            except psycopg2.errors.UniqueViolation:
                # ID collision - rollback and try again with a new ID
                conn.rollback()
                if attempt == max_attempts - 1:
                    raise Exception(f"Failed to generate unique build ID after {max_attempts} attempts")
                continue
        
        raise Exception("Failed to save build: exceeded maximum retry attempts")


def get_build(build_id: int) -> Optional[Dict[str, Any]]:
    """
    Get build by ID.
    
    Args:
        build_id: ID of the build
        
    Returns:
        Build record with canvas and cf_template
    """
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT id, owner_id, canvas, cf_template, created_at
            FROM build
            WHERE id = %s
            """,
            (build_id,)
        )
        result = cursor.fetchone()
        return dict(result) if result else None


def update_build_canvas_and_template(build_id: int, canvas: Dict[str, Any], cf_template: Optional[Dict[str, Any]] = None) -> bool:
    """
    Update existing build with new canvas and/or CF template.
    Used when user updates their deployment.
    
    Args:
        build_id: ID of the build to update
        canvas: Updated canvas JSON
        cf_template: Updated CloudFormation template JSON
        
    Returns:
        True if update successful, False otherwise
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE build
            SET canvas = %s,
                cf_template = %s
            WHERE id = %s
            """,
            (Json(canvas), Json(cf_template) if cf_template else None, build_id)
        )
        rows_affected = cursor.rowcount
        if rows_affected > 0:
            print(f"Build {build_id} updated successfully")
            return True
        else:
            print(f"Build {build_id} not found")
            return False


def get_builds_by_owner(owner_id: int) -> list:
  
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT id, owner_id, canvas, cf_template, created_at,project_name,description,status
            FROM build
            WHERE owner_id = %s
            ORDER BY created_at DESC
            """,
            (owner_id,)
        )
        results = cursor.fetchall()
        return [dict(row) for row in results]


def is_build_deployed(build_id: int) -> bool:
    """
    Check if a build has been deployed (has a CF template).
    
    Args:
        build_id: ID of the build
        
    Returns:
        True if build has a CloudFormation template (deployed)
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT cf_template IS NOT NULL as deployed
            FROM build
            WHERE id = %s
            """,
            (build_id,)
        )
        result = cursor.fetchone()
        return result[0] if result else False



def log_activity(build_id: int, user_id: int, change: str):

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO activity_log (build_id, user_id, change)
            VALUES (%s, %s, %s)
            """,
            (build_id, user_id, change)
        )
        print(f"✓ Activity logged for build {build_id}")


if __name__ == "__main__":
    # Test connection when running this file directly
    print("Testing database connection...")
    test_connection()
