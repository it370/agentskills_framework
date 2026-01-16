#!/usr/bin/env python3
"""
Skill-local transformation script for DataTransformer

This script is self-contained within the skill folder.
It demonstrates how skills can package their own scripts.
"""

import sys
import json
from typing import Dict, Any, List


def normalize_data(data: List[float]) -> List[float]:
    """Normalize data to 0-1 range."""
    if not data:
        return []
    
    min_val = min(data)
    max_val = max(data)
    
    if max_val == min_val:
        return [0.5] * len(data)
    
    return [(x - min_val) / (max_val - min_val) for x in data]


def standardize_data(data: List[float]) -> List[float]:
    """Standardize data using z-score."""
    if not data:
        return []
    
    mean = sum(data) / len(data)
    variance = sum((x - mean) ** 2 for x in data) / len(data)
    std_dev = variance ** 0.5
    
    if std_dev == 0:
        return [0.0] * len(data)
    
    return [(x - mean) / std_dev for x in data]


def aggregate_data(data: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    """Aggregate data by key."""
    aggregated = {}
    for item in data:
        if key in item:
            value = str(item[key])
            aggregated[value] = aggregated.get(value, 0) + 1
    return aggregated


def filter_data(data: List[Dict[str, Any]], criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Filter data by criteria."""
    filtered = []
    for item in data:
        match = True
        for key, value in criteria.items():
            if key not in item or item[key] != value:
                match = False
                break
        if match:
            filtered.append(item)
    return filtered


def transform_data(input_data: Any, transform_type: str) -> Dict[str, Any]:
    """
    Main transformation function.
    
    Args:
        input_data: Data to transform
        transform_type: Type of transformation to apply
    
    Returns:
        dict with transformed_data and transform_stats
    """
    
    if transform_type == "normalize":
        if not isinstance(input_data, list):
            raise ValueError("normalize requires a list of numbers")
        
        transformed = normalize_data(input_data)
        return {
            "transformed_data": transformed,
            "transform_stats": {
                "type": "normalize",
                "input_count": len(input_data),
                "output_count": len(transformed)
            }
        }
    
    elif transform_type == "standardize":
        if not isinstance(input_data, list):
            raise ValueError("standardize requires a list of numbers")
        
        transformed = standardize_data(input_data)
        return {
            "transformed_data": transformed,
            "transform_stats": {
                "type": "standardize",
                "input_count": len(input_data),
                "output_count": len(transformed),
                "mean": sum(input_data) / len(input_data) if input_data else 0
            }
        }
    
    elif transform_type == "aggregate":
        if not isinstance(input_data, dict) or "data" not in input_data or "key" not in input_data:
            raise ValueError("aggregate requires {data: [...], key: 'field_name'}")
        
        aggregated = aggregate_data(input_data["data"], input_data["key"])
        return {
            "transformed_data": aggregated,
            "transform_stats": {
                "type": "aggregate",
                "input_count": len(input_data["data"]),
                "unique_values": len(aggregated)
            }
        }
    
    elif transform_type == "filter":
        if not isinstance(input_data, dict) or "data" not in input_data or "criteria" not in input_data:
            raise ValueError("filter requires {data: [...], criteria: {...}}")
        
        filtered = filter_data(input_data["data"], input_data["criteria"])
        return {
            "transformed_data": filtered,
            "transform_stats": {
                "type": "filter",
                "input_count": len(input_data["data"]),
                "output_count": len(filtered)
            }
        }
    
    else:
        raise ValueError(f"Unknown transform_type: {transform_type}")


def main():
    """Main entry point for the script."""
    try:
        # Read input from stdin
        inputs = json.load(sys.stdin)
        
        # Extract parameters
        input_data = inputs.get('input_data')
        transform_type = inputs.get('transform_type', 'normalize')
        
        if input_data is None:
            raise ValueError("Missing required parameter: input_data")
        
        # Transform the data
        result = transform_data(input_data, transform_type)
        
        # Output result to stdout
        json.dump(result, sys.stdout, indent=2)
        
        # Exit successfully
        sys.exit(0)
        
    except Exception as e:
        # Output error information
        error_result = {
            "error": str(e),
            "error_type": type(e).__name__
        }
        json.dump(error_result, sys.stderr, indent=2)
        
        # Exit with error code
        sys.exit(1)


if __name__ == "__main__":
    main()
