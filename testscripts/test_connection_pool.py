"""
Quick test script to verify connection pool implementation.

Run this to check if the connection pool module is properly installed.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    
    try:
        from services.connection_pool import (
            get_postgres_pool,
            get_mongo_client, 
            postgres_connection,
            get_pool_stats,
            health_check,
            initialize_pools,
            close_pools
        )
        print("✓ Connection pool module imports successfully")
    except ImportError as e:
        print(f"✗ Failed to import connection pool: {e}")
        return False
    
    try:
        import engine
        print("✓ Engine module imports successfully")
    except ImportError as e:
        print(f"✗ Failed to import engine: {e}")
        return False
    
    try:
        from data import mongo
        print("✓ Mongo module imports successfully")
    except ImportError as e:
        print(f"✗ Failed to import mongo: {e}")
        return False
    
    return True


def test_module_structure():
    """Test that the module has expected structure."""
    print("\nTesting module structure...")
    
    from services import connection_pool
    
    # Check for expected functions
    expected_functions = [
        'initialize_pools',
        'close_pools',
        'get_postgres_pool',
        'get_mongo_client',
        'postgres_connection',
        'get_pool_stats',
        'health_check',
    ]
    
    for func_name in expected_functions:
        if hasattr(connection_pool, func_name):
            print(f"✓ {func_name} exists")
        else:
            print(f"✗ {func_name} missing")
            return False
    
    return True


def test_configuration():
    """Test that configuration can be loaded."""
    print("\nTesting configuration...")
    
    from services.connection_pool import _get_postgres_config, _get_mongo_config
    
    try:
        pg_config = _get_postgres_config()
        print(f"✓ Postgres config loaded: max_size={pg_config['max_size']}")
    except Exception as e:
        print(f"✗ Failed to load Postgres config: {e}")
        return False
    
    try:
        mongo_config = _get_mongo_config()
        print(f"✓ MongoDB config loaded: maxPoolSize={mongo_config['maxPoolSize']}")
    except Exception as e:
        print(f"✗ Failed to load MongoDB config: {e}")
        return False
    
    return True


def main():
    """Run all tests."""
    print("="*60)
    print("Connection Pool Implementation Test")
    print("="*60)
    
    tests = [
        ("Imports", test_imports),
        ("Module Structure", test_module_structure),
        ("Configuration", test_configuration),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        symbol = "✓" if result else "✗"
        print(f"{symbol} {test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    print("\n" + "="*60)
    if all_passed:
        print("✓ All tests passed!")
        print("Connection pool is properly installed.")
        print("\nNext steps:")
        print("1. Set environment variables (see config/connection_pool.env.template)")
        print("2. Start your services")
        print("3. Monitor via GET /health and GET /admin/pool-stats")
    else:
        print("✗ Some tests failed.")
        print("Please check the errors above.")
    print("="*60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
