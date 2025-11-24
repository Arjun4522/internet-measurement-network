#!/usr/bin/env python3
"""
Test script to verify DBOS integration with SQLite
"""

import sys
import os

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_dbos_import():
    """Test if we can import DBOS"""
    try:
        import dbos
        print("✓ DBOS imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Failed to import DBOS: {e}")
        return False

def test_sqlalchemy_import():
    """Test if we can import SQLAlchemy"""
    try:
        import sqlalchemy
        print("✓ SQLAlchemy imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Failed to import SQLAlchemy: {e}")
        return False

def test_database_models():
    """Test if we can import our database models"""
    try:
        from server.db_models import Base, Agent, ModuleResult, ModuleState
        print("✓ Database models imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Failed to import database models: {e}")
        return False

def test_database_setup():
    """Test database setup"""
    try:
        from server.database import DATABASE_URL
        print(f"✓ Database URL: {DATABASE_URL}")
        
        # Try to create engine
        from sqlalchemy import create_engine
        engine = create_engine(DATABASE_URL)
        print("✓ SQLAlchemy engine created successfully")
        
        # Try to create tables
        from server.db_models import Base
        Base.metadata.create_all(engine)
        print("✓ Database tables created successfully")
        
        return True
    except Exception as e:
        print(f"✗ Database setup failed: {e}")
        return False

def main():
    """Run all tests"""
    print("Testing DBOS integration...\n")
    
    tests = [
        test_dbos_import,
        test_sqlalchemy_import,
        test_database_models,
        test_database_setup
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"Tests passed: {passed}/{len(tests)}")
    
    if passed == len(tests):
        print("🎉 All tests passed! DBOS integration is ready.")
        return 0
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())