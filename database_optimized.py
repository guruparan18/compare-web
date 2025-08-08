import sqlite3
import json
import threading
from contextlib import contextmanager
from typing import Optional, List, Dict, Any
import logging
from concurrent.futures import ThreadPoolExecutor
import functools

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseConnectionPool:
    """Thread-safe SQLite connection pool for better performance."""

    def __init__(self, database_path: str = "comparisons.db", max_connections: int = 5):
        self.database_path = database_path
        self.max_connections = max_connections
        self._connections = []
        self._lock = threading.Lock()
        self._local = threading.local()

    def get_connection(self) -> sqlite3.Connection:
        """Get a thread-local database connection."""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            conn = sqlite3.connect(
                self.database_path,
                timeout=30.0,  # 30 second timeout
                isolation_level=None,  # Autocommit mode for better performance
                check_same_thread=False,
            )

            # Optimize SQLite settings for performance
            conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
            conn.execute("PRAGMA synchronous=NORMAL")  # Faster than FULL
            conn.execute("PRAGMA cache_size=10000")  # 10MB cache
            conn.execute("PRAGMA temp_store=MEMORY")  # Store temp tables in memory
            conn.execute("PRAGMA mmap_size=268435456")  # 256MB memory map

            # Enable foreign keys and row factory
            conn.execute("PRAGMA foreign_keys=ON")
            conn.row_factory = sqlite3.Row  # Enable dict-like access

            self._local.connection = conn

        return self._local.connection

    @contextmanager
    def get_cursor(self):
        """Context manager for getting a cursor with automatic cleanup."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            yield cursor, conn
        finally:
            cursor.close()

    def close_all_connections(self):
        """Close all connections in the pool."""
        with self._lock:
            for conn in self._connections:
                conn.close()
            self._connections.clear()

            # Close thread-local connection if it exists
            if hasattr(self._local, "connection") and self._local.connection:
                self._local.connection.close()
                self._local.connection = None


# Global connection pool
_db_pool = DatabaseConnectionPool()


def get_db_pool() -> DatabaseConnectionPool:
    """Get the global database connection pool."""
    return _db_pool


def init_db_optimized():
    """Initialize the database with optimized schema and indexes."""
    with _db_pool.get_cursor() as (cursor, conn):
        # Check if the table already exists
        cursor.execute("""
            SELECT count(name) 
            FROM sqlite_master 
            WHERE type='table' AND name='comparisons'
        """)

        table_exists = cursor.fetchone()[0] > 0

        if not table_exists:
            # Create optimized table structure
            cursor.execute("""
                CREATE TABLE comparisons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url1 TEXT NOT NULL,
                    url2 TEXT NOT NULL,
                    content1 TEXT,
                    content2 TEXT,
                    css1 TEXT,
                    css2 TEXT,
                    comparison TEXT,
                    error1 TEXT,
                    error2 TEXT,
                    broken_links1 TEXT,
                    broken_links2 TEXT,
                    images1 TEXT,
                    images2 TEXT,
                    results1 TEXT,
                    results2 TEXT,
                    links1 TEXT,
                    links2 TEXT,
                    links_comparison TEXT,
                    text_comparison TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    -- Add metadata columns for better querying
                    comparison_hash TEXT,  -- For deduplication
                    content_size INTEGER DEFAULT 0,  -- For monitoring storage
                    status TEXT DEFAULT 'completed'  -- For async processing
                )
            """)

            # Create performance indexes
            cursor.execute(
                "CREATE INDEX idx_comparisons_timestamp ON comparisons(timestamp DESC)"
            )
            cursor.execute(
                "CREATE INDEX idx_comparisons_urls ON comparisons(url1, url2)"
            )
            cursor.execute(
                "CREATE INDEX idx_comparisons_hash ON comparisons(comparison_hash)"
            )
            cursor.execute("CREATE INDEX idx_comparisons_status ON comparisons(status)")

            # Create a summary view for faster listing
            cursor.execute("""
                CREATE VIEW comparison_summary AS
                SELECT 
                    id,
                    url1,
                    url2,
                    timestamp,
                    status,
                    content_size,
                    CASE 
                        WHEN error1 IS NOT NULL OR error2 IS NOT NULL THEN 'error'
                        ELSE 'success'
                    END as result_status
                FROM comparisons
            """)

            conn.commit()
            logger.info(
                "Database table 'comparisons' created successfully with optimizations"
            )
        else:
            # Add missing columns if table exists but doesn't have them
            try:
                # Check if the new columns exist
                cursor.execute("PRAGMA table_info(comparisons)")
                columns = [row[1] for row in cursor.fetchall()]
                
                if 'comparison_hash' not in columns:
                    cursor.execute("ALTER TABLE comparisons ADD COLUMN comparison_hash TEXT")
                    logger.info("Added comparison_hash column")
                    
                if 'content_size' not in columns:
                    cursor.execute("ALTER TABLE comparisons ADD COLUMN content_size INTEGER DEFAULT 0")
                    logger.info("Added content_size column")
                    
                if 'status' not in columns:
                    cursor.execute("ALTER TABLE comparisons ADD COLUMN status TEXT DEFAULT 'completed'")
                    logger.info("Added status column")
                    
                conn.commit()
            except sqlite3.Error as e:
                logger.warning(f"Could not add missing columns: {e}")
            
            # Check and add missing indexes if table exists
            try:
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_comparisons_timestamp ON comparisons(timestamp DESC)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_comparisons_urls ON comparisons(url1, url2)"
                )
                # Only create hash and status indexes if columns exist
                cursor.execute("PRAGMA table_info(comparisons)")
                columns = [row[1] for row in cursor.fetchall()]
                
                if 'comparison_hash' in columns:
                    cursor.execute(
                        "CREATE INDEX IF NOT EXISTS idx_comparisons_hash ON comparisons(comparison_hash)"
                    )
                if 'status' in columns:
                    cursor.execute(
                        "CREATE INDEX IF NOT EXISTS idx_comparisons_status ON comparisons(status)"
                    )
                    
                conn.commit()
                logger.info("Database indexes verified/created successfully")
            except sqlite3.Error as e:
                logger.warning(f"Could not create some indexes: {e}")
                
            # Try to create the summary view
            try:
                cursor.execute("""
                    CREATE VIEW IF NOT EXISTS comparison_summary AS
                    SELECT 
                        id,
                        url1,
                        url2,
                        timestamp,
                        COALESCE(status, 'completed') as status,
                        COALESCE(content_size, 0) as content_size,
                        CASE 
                            WHEN error1 IS NOT NULL OR error2 IS NOT NULL THEN 'error'
                            ELSE 'success'
                        END as result_status
                    FROM comparisons
                """)
                conn.commit()
                logger.info("Database summary view created successfully")
            except sqlite3.Error as e:
                logger.warning(f"Could not create summary view: {e}")


def store_comparison_optimized(
    data: Dict[str, Any], async_mode: bool = True
) -> Optional[int]:
    """
    Store comparison results with optimization and optional async processing.
    Returns the comparison ID.
    """

    def _store_sync():
        with _db_pool.get_cursor() as (cursor, conn):
            # Check if optimized columns exist
            cursor.execute("PRAGMA table_info(comparisons)")
            columns = [row[1] for row in cursor.fetchall()]
            has_hash_column = 'comparison_hash' in columns
            has_size_column = 'content_size' in columns
            has_status_column = 'status' in columns

            # Generate comparison hash for deduplication (if column exists)
            comparison_hash = None
            content_size = 0
            if has_hash_column:
                comparison_key = f"{data['url1']}|{data['url2']}"
                comparison_hash = str(hash(comparison_key))

            # Calculate content size for monitoring (if column exists)
            if has_size_column:
                content_size = len(str(data.get("content1", ""))) + len(
                    str(data.get("content2", ""))
                )

            # Serialize complex data structures
            serialized_data = {
                "url1": data["url1"],
                "url2": data["url2"],
                "content1": data["content1"],
                "content2": data["content2"],
                "css1": json.dumps(data["css1"]) if data.get("css1") else None,
                "css2": json.dumps(data["css2"]) if data.get("css2") else None,
                "comparison": json.dumps(data["comparison"])
                if data.get("comparison")
                else None,
                "error1": data.get("error1"),
                "error2": data.get("error2"),
                "broken_links1": json.dumps(data.get("broken_links1", [])),
                "broken_links2": json.dumps(data.get("broken_links2", [])),
                "images1": json.dumps(data.get("images1", [])),
                "images2": json.dumps(data.get("images2", [])),
                "results1": json.dumps(data.get("results1", {})),
                "results2": json.dumps(data.get("results2", {})),
                "links1": json.dumps(data.get("links1", [])),
                "links2": json.dumps(data.get("links2", [])),
                "links_comparison": json.dumps(data.get("links_comparison", {})),
                "text_comparison": json.dumps(data.get("text_comparison", [])),
            }
            
            # Add optional columns only if they exist
            if has_hash_column:
                serialized_data["comparison_hash"] = comparison_hash
            if has_size_column:
                serialized_data["content_size"] = content_size
            if has_status_column:
                serialized_data["status"] = "completed"

            # Build dynamic INSERT statement based on available columns
            base_columns = [
                "url1", "url2", "content1", "content2", "css1", "css2", "comparison",
                "error1", "error2", "broken_links1", "broken_links2", "images1", "images2",
                "results1", "results2", "links1", "links2", "links_comparison", "text_comparison"
            ]
            
            optional_columns = []
            if has_hash_column:
                optional_columns.append("comparison_hash")
            if has_size_column:
                optional_columns.append("content_size")
            if has_status_column:
                optional_columns.append("status")
                
            all_columns = base_columns + optional_columns
            placeholders = [f":{col}" for col in all_columns]
            
            insert_sql = f"""
                INSERT INTO comparisons ({', '.join(all_columns)}) 
                VALUES ({', '.join(placeholders)})
            """

            # Use prepared statement for better performance
            cursor.execute(insert_sql, serialized_data)

            comparison_id = cursor.lastrowid
            conn.commit()

            logger.info(
                f"Stored comparison {comparison_id} (size: {content_size} bytes)"
            )
            return comparison_id

    if async_mode:
        # Store asynchronously to not block the main thread
        executor = ThreadPoolExecutor(max_workers=2)
        executor.submit(_store_sync)
        # Return immediately, don't wait for completion
        return None
    else:
        return _store_sync()


def get_recent_comparisons_optimized(limit: int = 10) -> List[Dict[str, Any]]:
    """Get the most recent comparisons with optimized query."""
    with _db_pool.get_cursor() as (cursor, conn):
        # Check if comparison_summary view exists, fallback to direct table query
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='view' AND name='comparison_summary'"
        )
        view_exists = cursor.fetchone() is not None
        
        if view_exists:
            # Use the summary view and index for fast results
            cursor.execute(
                """
                SELECT id, url1, url2, timestamp, result_status, content_size
                FROM comparison_summary 
                ORDER BY timestamp DESC 
                LIMIT ?
            """,
                (limit,),
            )
        else:
            # Fallback to direct table query for backward compatibility
            cursor.execute(
                """
                SELECT id, url1, url2, timestamp, 
                       CASE WHEN error1 IS NOT NULL OR error2 IS NOT NULL THEN 'error' ELSE 'success' END as result_status,
                       COALESCE(content_size, 0) as content_size
                FROM comparisons 
                ORDER BY timestamp DESC 
                LIMIT ?
            """,
                (limit,),
            )

        results = cursor.fetchall()

        # Convert to list of dictionaries
        return [dict(row) for row in results]


def get_comparison_optimized(
    comparison_id: int, include_content: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Get a specific comparison by ID with options to exclude large content.
    Args:
        comparison_id: The ID of the comparison
        include_content: Whether to include large content fields (content1, content2)
    """
    with _db_pool.get_cursor() as (cursor, conn):
        if include_content:
            cursor.execute("SELECT * FROM comparisons WHERE id = ?", (comparison_id,))
        else:
            # Exclude large content fields for faster retrieval
            cursor.execute(
                """
                SELECT id, url1, url2, css1, css2, comparison, error1, error2,
                       broken_links1, broken_links2, images1, images2, results1, results2,
                       links1, links2, links_comparison, text_comparison, timestamp,
                       comparison_hash, content_size, status
                FROM comparisons WHERE id = ?
            """,
                (comparison_id,),
            )

        result = cursor.fetchone()

        if result:
            data = dict(result)

            # Deserialize JSON strings back to Python objects
            json_fields = [
                "css1",
                "css2",
                "comparison",
                "broken_links1",
                "broken_links2",
                "images1",
                "images2",
                "results1",
                "results2",
                "links1",
                "links2",
                "links_comparison",
                "text_comparison",
            ]

            for field in json_fields:
                if data.get(field):
                    try:
                        data[field] = json.loads(data[field])
                    except json.JSONDecodeError:
                        logger.warning(
                            f"Failed to parse JSON field {field} for comparison {comparison_id}"
                        )
                        data[field] = None

            return data

        return None


def search_comparisons(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Search comparisons by URL with optimized query."""
    with _db_pool.get_cursor() as (cursor, conn):
        search_term = f"%{query}%"
        cursor.execute(
            """
            SELECT id, url1, url2, timestamp, 
                   CASE WHEN error1 IS NOT NULL OR error2 IS NOT NULL THEN 'error' ELSE 'success' END as status
            FROM comparisons 
            WHERE url1 LIKE ? OR url2 LIKE ?
            ORDER BY timestamp DESC 
            LIMIT ?
        """,
            (search_term, search_term, limit),
        )

        results = cursor.fetchall()
        return [dict(row) for row in results]


def get_database_stats() -> Dict[str, Any]:
    """Get database performance statistics."""
    with _db_pool.get_cursor() as (cursor, conn):
        # Get table stats
        cursor.execute("SELECT COUNT(*) as total_comparisons FROM comparisons")
        total_comparisons = cursor.fetchone()[0]

        cursor.execute(
            "SELECT AVG(content_size) as avg_size, MAX(content_size) as max_size FROM comparisons"
        )
        size_stats = cursor.fetchone()

        cursor.execute("""
            SELECT 
                COUNT(CASE WHEN error1 IS NOT NULL OR error2 IS NOT NULL THEN 1 END) as error_count,
                COUNT(CASE WHEN error1 IS NULL AND error2 IS NULL THEN 1 END) as success_count
            FROM comparisons
        """)
        status_stats = cursor.fetchone()

        # Get database file size
        cursor.execute(
            "SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()"
        )
        db_size = cursor.fetchone()[0]

        return {
            "total_comparisons": total_comparisons,
            "avg_content_size": size_stats[0] or 0,
            "max_content_size": size_stats[1] or 0,
            "error_count": status_stats[0],
            "success_count": status_stats[1],
            "database_size_bytes": db_size,
            "database_size_mb": round(db_size / (1024 * 1024), 2),
        }


def cleanup_old_comparisons(days_old: int = 30) -> int:
    """Clean up comparisons older than specified days."""
    with _db_pool.get_cursor() as (cursor, conn):
        cursor.execute(
            """
            DELETE FROM comparisons 
            WHERE timestamp < datetime('now', '-{} days')
        """.format(days_old)
        )

        deleted_count = cursor.rowcount
        conn.commit()

        # Vacuum to reclaim space
        cursor.execute("VACUUM")

        logger.info(f"Cleaned up {deleted_count} old comparisons")
        return deleted_count


# Performance monitoring decorator
def monitor_db_performance(func):
    """Decorator to monitor database operation performance."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        import time

        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            logger.info(f"DB operation {func.__name__} completed in {duration:.3f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"DB operation {func.__name__} failed after {duration:.3f}s: {e}"
            )
            raise

    return wrapper


# Apply monitoring to key functions
store_comparison_optimized = monitor_db_performance(store_comparison_optimized)
get_comparison_optimized = monitor_db_performance(get_comparison_optimized)

if __name__ == "__main__":
    # Test the optimized database functions
    init_db_optimized()

    # Test data
    test_data = {
        "url1": "https://example.com",
        "url2": "https://test.com",
        "content1": "<html><body>Test 1</body></html>",
        "content2": "<html><body>Test 2</body></html>",
        "css1": ["body { color: red; }"],
        "css2": ["body { color: blue; }"],
        "comparison": {"h1": [("Title", "Title", "both")]},
        "error1": None,
        "error2": None,
        "broken_links1": [],
        "broken_links2": [],
        "images1": ["image1.jpg"],
        "images2": ["image2.jpg"],
        "results1": {"h1": ["Title"]},
        "results2": {"h1": ["Title"]},
        "links1": [("https://example.com/page1", "OK")],
        "links2": [("https://test.com/page1", "OK")],
        "links_comparison": {"page1": "both"},
        "text_comparison": [("both", "Test content", None)],
    }

    # Test storing and retrieving
    comparison_id = store_comparison_optimized(test_data, async_mode=False)
    print(f"Stored comparison with ID: {comparison_id}")

    recent = get_recent_comparisons_optimized(5)
    print(f"Recent comparisons: {len(recent)}")

    retrieved = get_comparison_optimized(comparison_id)
    print(f"Retrieved comparison: {retrieved['url1']} vs {retrieved['url2']}")

    stats = get_database_stats()
    print(f"Database stats: {stats}")

    _db_pool.close_all_connections()
