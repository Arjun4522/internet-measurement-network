import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

try:
    from dbos import DBOS
    DBOS_AVAILABLE = True
except ImportError:
    DBOS_AVAILABLE = False
    # Mock DBOS for development
    class DBOS:
        @staticmethod
        def launch():
            print("DBOS launched (mock)")

# Use SQLite for simplicity
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///imn.db")

# Create engine and session maker
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_dbos():
    """Initialize DBOS - call without arguments"""
    if DBOS_AVAILABLE:
        try:
            DBOS.launch()  # Remove database_url argument
            print("[DBOS] Initialized successfully")
        except Exception as e:
            print(f"[DBOS] Initialization error: {e}")
    else:
        print("[DBOS] Running in mock mode (dbos package not installed)")

@contextmanager
def get_db_session():
    """Provide a database session"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()