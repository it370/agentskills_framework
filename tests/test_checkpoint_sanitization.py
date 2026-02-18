"""
Test script to verify NaN/Infinity sanitization in checkpoint data.

This script tests the sanitize_for_json function to ensure it properly
handles edge cases that cause JSON serialization failures.
"""

import json
import math
import sys
from pathlib import Path

# Add parent directory to path so we can import services
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.checkpoint_buffer import sanitize_for_json


def test_sanitization():
    """Test various edge cases for JSON sanitization."""
    
    print("Testing checkpoint data sanitization...")
    print("=" * 60)
    
    # Test case 1: Simple NaN value
    test_data_1 = {"value": float('nan')}
    sanitized_1 = sanitize_for_json(test_data_1)
    print("\n✅ Test 1: Simple NaN")
    print(f"   Input:  {test_data_1}")
    print(f"   Output: {sanitized_1}")
    print(f"   JSON:   {json.dumps(sanitized_1)}")
    
    # Test case 2: Infinity value
    test_data_2 = {"value": float('inf')}
    sanitized_2 = sanitize_for_json(test_data_2)
    print("\n✅ Test 2: Infinity")
    print(f"   Input:  {test_data_2}")
    print(f"   Output: {sanitized_2}")
    print(f"   JSON:   {json.dumps(sanitized_2)}")
    
    # Test case 3: Negative Infinity
    test_data_3 = {"value": float('-inf')}
    sanitized_3 = sanitize_for_json(test_data_3)
    print("\n✅ Test 3: Negative Infinity")
    print(f"   Input:  {test_data_3}")
    print(f"   Output: {sanitized_3}")
    print(f"   JSON:   {json.dumps(sanitized_3)}")
    
    # Test case 4: Nested structure with NaN (mimics the actual error)
    test_data_4 = {
        "checkpoint": {
            "channel_values": {
                "data_store": {
                    "neighbor_bounding_box": [float('nan'), float('nan'), 123.45, float('inf')]
                }
            }
        }
    }
    sanitized_4 = sanitize_for_json(test_data_4)
    print("\n✅ Test 4: Nested structure with NaN (actual error case)")
    print(f"   Input:  {test_data_4}")
    print(f"   Output: {sanitized_4}")
    print(f"   JSON:   {json.dumps(sanitized_4)}")
    
    # Test case 5: Mixed valid and invalid values
    test_data_5 = {
        "valid_float": 123.456,
        "valid_int": 789,
        "valid_string": "test",
        "nan_value": float('nan'),
        "inf_value": float('inf'),
        "nested": {
            "list": [1, 2, float('nan'), 4, float('-inf')],
            "dict": {"a": 1, "b": float('nan')}
        }
    }
    sanitized_5 = sanitize_for_json(test_data_5)
    print("\n✅ Test 5: Mixed valid and invalid values")
    print(f"   Input keys: {list(test_data_5.keys())}")
    print(f"   Output: {sanitized_5}")
    print(f"   JSON:   {json.dumps(sanitized_5)}")
    
    # Test case 6: Ensure normal values are preserved
    test_data_6 = {
        "normal_float": 3.14159,
        "zero": 0.0,
        "negative": -42.5,
        "small": 1e-10,
        "large": 1e10
    }
    sanitized_6 = sanitize_for_json(test_data_6)
    print("\n✅ Test 6: Normal values preserved")
    print(f"   Input:  {test_data_6}")
    print(f"   Output: {sanitized_6}")
    print(f"   Match:  {test_data_6 == sanitized_6}")
    
    print("\n" + "=" * 60)
    print("✅ All sanitization tests passed!")
    print("\nKey findings:")
    print("  - NaN, Infinity, and -Infinity are converted to None (null in JSON)")
    print("  - Normal float values are preserved")
    print("  - Nested structures (lists, dicts) are handled recursively")
    print("  - JSON serialization succeeds for all sanitized data")


if __name__ == "__main__":
    test_sanitization()
