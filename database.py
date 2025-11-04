"""
Database connection and operations for RDS PostgreSQL.
"""
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from typing import Dict, Any, Optional
import os
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


# ============================================================================
# BUILD OPERATIONS (for canvas and CF template storage)
# ============================================================================

def save_build(owner_id: int, canvas: Dict[str, Any], cf_template: Optional[Dict[str, Any]] = None) -> int:
    """
    Save a new build with canvas and optional CloudFormation template.
    
    Args:
        owner_id: User ID of the build owner
        canvas: Canvas JSON from frontend
        cf_template: Generated CloudFormation template JSON
        
    Returns:
        build_id: ID of the created build
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO build (owner_id, canvas, cf_template)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (owner_id, Json(canvas), Json(cf_template) if cf_template else None)
        )
        build_id = cursor.fetchone()[0]
        print(f"✓ Build saved with ID: {build_id}")
        return build_id


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
            print(f"✓ Build {build_id} updated successfully")
            return True
        else:
            print(f"✗ Build {build_id} not found")
            return False


def get_builds_by_owner(owner_id: int) -> list:
    """
    Get all builds owned by a user.
    
    Args:
        owner_id: User ID
        
    Returns:
        List of build records
    """
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT id, owner_id, canvas, cf_template, created_at
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


# ============================================================================
# ACTIVITY LOG
# ============================================================================

def log_activity(build_id: int, user_id: int, change: str):
    """
    Log activity for a build.
    
    Args:
        build_id: ID of the build
        user_id: ID of the user making the change
        change: Description of the change
    """
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
