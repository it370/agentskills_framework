#!/usr/bin/env python3
"""
Test rerun naming to ensure no duplicate suffixes.
"""
import re

def strip_rerun_suffix(run_name: str) -> str:
    """Strip any existing (Rerun #N) suffix from run name."""
    return re.sub(r'\s*\(Rerun #\d+\)\s*$', '', run_name).strip()

def generate_rerun_name(original_name: str, rerun_count: int) -> str:
    """Generate rerun name, ensuring no duplicate suffixes."""
    base_name = strip_rerun_suffix(original_name)
    return f"{base_name} (Rerun #{rerun_count})"

# Test cases
test_cases = [
    # (input_name, rerun_count, expected_output)
    ("Profiler Retriever", 1, "Profiler Retriever (Rerun #1)"),
    ("Profiler Retriever (Rerun #1)", 2, "Profiler Retriever (Rerun #2)"),
    ("Profiler Retriever (Rerun #2)", 3, "Profiler Retriever (Rerun #3)"),
    ("Morning Order Batch", 1, "Morning Order Batch (Rerun #1)"),
    ("Morning Order Batch (Rerun #1)", 2, "Morning Order Batch (Rerun #2)"),
    ("Customer Onboarding - Jan 8", 1, "Customer Onboarding - Jan 8 (Rerun #1)"),
    ("Customer Onboarding - Jan 8 (Rerun #1)", 2, "Customer Onboarding - Jan 8 (Rerun #2)"),
    ("thread_abc123", 1, "thread_abc123 (Rerun #1)"),
    ("thread_abc123 (Rerun #1)", 2, "thread_abc123 (Rerun #2)"),
]

print("\n" + "="*80)
print("Testing Rerun Name Generation")
print("="*80)

all_passed = True
for input_name, rerun_count, expected in test_cases:
    result = generate_rerun_name(input_name, rerun_count)
    passed = result == expected
    all_passed = all_passed and passed
    
    status = "✓" if passed else "✗"
    print(f"\n{status} Test: '{input_name}' -> rerun #{rerun_count}")
    print(f"  Expected: '{expected}'")
    print(f"  Got:      '{result}'")
    if not passed:
        print(f"  FAILED!")

print("\n" + "="*80)
if all_passed:
    print("✓ All tests passed!")
else:
    print("✗ Some tests failed")
print("="*80)
