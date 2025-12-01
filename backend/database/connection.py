"""Database connection manager for DuckDB/SQLite.

Provides connection pooling, transaction management, and query utilities.
"""
import os
from pathlib import Path
from typing import Optional, Any, List, Dict
from contextlib import contextmanager
import logging

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False
    import sqlite3

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Manages database connections with support for DuckDB and SQLite."""
    
    def __init__(
        self,
        db_path: Optional[str] = None,
        use_duckdb: bool = True,
        memory_limit: str = '4GB',
        threads: int = 4,
        read_only: bool = False
    ):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to database file. Defaults to data/ncaa_predictions.{duckdb|db}
            use_duckdb: Use DuckDB if available, otherwise SQLite
            memory_limit: Memory limit for DuckDB (e.g., '4GB')
            threads: Number of threads for DuckDB
            read_only: Open database in read-only mode
        """
        self.use_duckdb = use_duckdb and DUCKDB_AVAILABLE
        
        if db_path is None:
            data_dir = Path(__file__).parent.parent.parent / 'data'
            data_dir.mkdir(exist_ok=True)
            ext = 'duckdb' if self.use_duckdb else 'db'
            db_path = str(data_dir / f'ncaa_predictions.{ext}')
        
        self.db_path = db_path
        self.memory_limit = memory_limit
        self.threads = threads
        self.read_only = read_only
        self._connection = None
        
        logger.info(
            f"Initialized {'DuckDB' if self.use_duckdb else 'SQLite'} "
            f"connection to {self.db_path}"
        )
    
    def connect(self):
        """Establish database connection."""
        if self._connection is not None:
            return self._connection
        
        if self.use_duckdb:
            self._connection = duckdb.connect(
                database=self.db_path,
                read_only=self.read_only
            )
            # Configure DuckDB for optimal performance
            self._connection.execute(f"PRAGMA memory_limit='{self.memory_limit}'")
            self._connection.execute(f"PRAGMA threads={self.threads}")
            logger.info(f"DuckDB connection established (memory: {self.memory_limit}, threads: {self.threads})")
        else:
            self._connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False
            )
            self._connection.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrency
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA synchronous=NORMAL")
            logger.info("SQLite connection established (WAL mode enabled)")
        
        return self._connection
    
    def close(self):
        """Close database connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            logger.info("Database connection closed")
    
    @contextmanager
    def transaction(self):
        """Context manager for database transactions."""
        conn = self.connect()
        try:
            if self.use_duckdb:
                conn.execute("BEGIN TRANSACTION")
            yield conn
            if self.use_duckdb:
                conn.execute("COMMIT")
            else:
                conn.commit()
        except Exception as e:
            if self.use_duckdb:
                conn.execute("ROLLBACK")
            else:
                conn.rollback()
            logger.error(f"Transaction failed: {e}")
            raise
    
    def execute(self, query: str, params: Optional[tuple] = None) -> Any:
        """
        Execute a query and return the result.
        
        Args:
            query: SQL query string
            params: Query parameters (tuple or list)
        
        Returns:
            Query result (DuckDB relation or SQLite cursor)
        """
        conn = self.connect()
        
        try:
            if params:
                result = conn.execute(query, params)
            else:
                result = conn.execute(query)
            
            return result
        except Exception as e:
            logger.error(f"Query execution failed: {e}\nQuery: {query[:200]}...")
            raise
    
    def fetch_one(self, query: str, params: Optional[tuple] = None) -> Optional[Dict]:
        """Execute query and fetch one row as dictionary."""
        result = self.execute(query, params)
        
        if self.use_duckdb:
            row = result.fetchone()
            if row:
                columns = [desc[0] for desc in result.description]
                return dict(zip(columns, row))
        else:
            row = result.fetchone()
            if row:
                return dict(row)
        
        return None
    
    def fetch_all(self, query: str, params: Optional[tuple] = None) -> List[Dict]:
        """Execute query and fetch all rows as list of dictionaries."""
        result = self.execute(query, params)
        
        if self.use_duckdb:
            rows = result.fetchall()
            if rows:
                columns = [desc[0] for desc in result.description]
                return [dict(zip(columns, row)) for row in rows]
        else:
            rows = result.fetchall()
            if rows:
                return [dict(row) for row in rows]
        
        return []
    
    def fetch_df(self, query: str, params: Optional[tuple] = None):
        """
        Execute query and return pandas DataFrame.
        
        Note: Requires pandas to be installed.
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required for fetch_df()")
        
        if self.use_duckdb:
            result = self.execute(query, params)
            return result.df()
        else:
            result = self.execute(query, params)
            rows = result.fetchall()
            if rows:
                columns = [desc[0] for desc in result.description]
                return pd.DataFrame(rows, columns=columns)
            return pd.DataFrame()
    
    def execute_many(self, query: str, params_list: List[tuple]):
        """Execute query with multiple parameter sets."""
        conn = self.connect()
        
        try:
            if self.use_duckdb:
                # DuckDB doesn't have executemany, use multiple execute calls
                conn.execute("BEGIN TRANSACTION")
                for params in params_list:
                    conn.execute(query, params)
                conn.execute("COMMIT")
            else:
                conn.executemany(query, params_list)
                conn.commit()
        except Exception as e:
            if not self.use_duckdb:
                conn.rollback()
            logger.error(f"Batch execution failed: {e}")
            raise
    
    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        if self.use_duckdb:
            query = """
                SELECT COUNT(*) as count 
                FROM information_schema.tables 
                WHERE table_name = ?
            """
        else:
            query = """
                SELECT COUNT(*) as count 
                FROM sqlite_master 
                WHERE type='table' AND name=?
            """
        
        result = self.fetch_one(query, (table_name,))
        return result['count'] > 0 if result else False
    
    def get_table_row_count(self, table_name: str) -> int:
        """Get the number of rows in a table."""
        query = f"SELECT COUNT(*) as count FROM {table_name}"
        result = self.fetch_one(query)
        return result['count'] if result else 0
    
    def vacuum(self):
        """Run VACUUM to reclaim space (maintenance operation)."""
        try:
            self.execute("VACUUM")
            logger.info("Database vacuumed successfully")
        except Exception as e:
            logger.warning(f"Vacuum operation failed: {e}")
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def __repr__(self):
        return f"DatabaseConnection(db_path='{self.db_path}', use_duckdb={self.use_duckdb})"


# Global connection instance (lazy-initialized)
_global_connection: Optional[DatabaseConnection] = None


def get_db_connection(
    db_path: Optional[str] = None,
    use_duckdb: bool = True,
    force_new: bool = False
) -> DatabaseConnection:
    """
    Get the global database connection instance.
    
    Args:
        db_path: Path to database file
        use_duckdb: Use DuckDB if available
        force_new: Force creation of new connection
    
    Returns:
        DatabaseConnection instance
    """
    global _global_connection
    
    if _global_connection is None or force_new:
        _global_connection = DatabaseConnection(
            db_path=db_path,
            use_duckdb=use_duckdb
        )
    
    return _global_connection


def close_global_connection():
    """Close the global database connection."""
    global _global_connection
    if _global_connection is not None:
        _global_connection.close()
        _global_connection = None
