"""
Data Processing Functions - Transform and enrich data

This module contains functions for data transformation, enrichment,
and processing tasks.
"""

from actions import action
from typing import Dict, Any, List
from datetime import datetime, timedelta


@action(
    name="parse_date_range",
    requires={"start_date", "end_date"},
    produces={"days_between", "business_days", "is_valid_range"},
    description="Parse and validate date range, calculate business days"
)
def parse_date_range(start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Parse date strings and calculate date range metrics.
    
    Args:
        start_date: Start date (ISO format)
        end_date: End date (ISO format)
    
    Returns:
        dict with days_between, business_days, is_valid_range
    """
    try:
        start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        is_valid = end >= start
        delta = (end - start).days if is_valid else 0
        
        # Calculate business days (excluding weekends)
        business_days = 0
        if is_valid:
            current = start
            while current <= end:
                if current.weekday() < 5:  # Monday = 0, Sunday = 6
                    business_days += 1
                current += timedelta(days=1)
        
        return {
            "days_between": delta,
            "business_days": business_days,
            "is_valid_range": is_valid
        }
    except ValueError as e:
        return {
            "days_between": 0,
            "business_days": 0,
            "is_valid_range": False,
            "error": str(e)
        }


@action(
    name="aggregate_scores",
    requires={"scores", "weights"},
    produces={"weighted_average", "total_score", "highest_score", "lowest_score"},
    description="Aggregate multiple scores with optional weighting"
)
def aggregate_scores(scores: List[float], weights: List[float] = None) -> Dict[str, Any]:
    """
    Calculate aggregated score metrics.
    
    Args:
        scores: List of score values
        weights: Optional weights for each score (defaults to equal weight)
    
    Returns:
        dict with weighted_average, total_score, highest_score, lowest_score
    """
    if not scores:
        return {
            "weighted_average": 0.0,
            "total_score": 0.0,
            "highest_score": 0.0,
            "lowest_score": 0.0
        }
    
    if weights is None:
        weights = [1.0] * len(scores)
    
    if len(scores) != len(weights):
        raise ValueError(f"scores ({len(scores)}) and weights ({len(weights)}) must have same length")
    
    weighted_sum = sum(s * w for s, w in zip(scores, weights))
    weight_sum = sum(weights)
    weighted_avg = weighted_sum / weight_sum if weight_sum > 0 else 0.0
    
    return {
        "weighted_average": round(weighted_avg, 2),
        "total_score": round(sum(scores), 2),
        "highest_score": round(max(scores), 2),
        "lowest_score": round(min(scores), 2)
    }


@action(
    name="normalize_address",
    requires={"address_line1", "city", "state", "postal_code"},
    produces={"normalized_address", "formatted_address", "is_valid"},
    description="Normalize and validate address information"
)
def normalize_address(
    address_line1: str,
    city: str,
    state: str,
    postal_code: str,
    address_line2: str = ""
) -> Dict[str, Any]:
    """
    Normalize address components into standard format.
    
    Args:
        address_line1: Primary address line
        city: City name
        state: State/province
        postal_code: ZIP/postal code
        address_line2: Optional secondary address line
    
    Returns:
        dict with normalized_address, formatted_address, is_valid
    """
    # Clean and normalize
    addr1 = address_line1.strip().title()
    addr2 = address_line2.strip().title() if address_line2 else ""
    city_norm = city.strip().title()
    state_norm = state.strip().upper()
    postal_norm = postal_code.strip().replace(" ", "")
    
    # Basic validation
    is_valid = bool(addr1 and city_norm and state_norm and postal_norm)
    
    # Build normalized structure
    normalized = {
        "line1": addr1,
        "line2": addr2,
        "city": city_norm,
        "state": state_norm,
        "postal_code": postal_norm
    }
    
    # Build formatted string
    parts = [addr1]
    if addr2:
        parts.append(addr2)
    parts.append(f"{city_norm}, {state_norm} {postal_norm}")
    formatted = "\n".join(parts)
    
    return {
        "normalized_address": normalized,
        "formatted_address": formatted,
        "is_valid": is_valid
    }


@action(
    name="extract_keywords",
    requires={"text"},
    produces={"keywords", "word_count", "unique_words"},
    description="Extract keywords and statistics from text"
)
def extract_keywords(text: str, min_length: int = 4) -> Dict[str, Any]:
    """
    Extract keywords from text and calculate statistics.
    
    Args:
        text: Input text
        min_length: Minimum word length to consider (default: 4)
    
    Returns:
        dict with keywords, word_count, unique_words
    """
    import re
    
    # Clean and tokenize
    words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
    
    # Filter by length and common stop words
    stop_words = {'that', 'this', 'with', 'from', 'have', 'been', 'will', 'would', 'could', 'should'}
    keywords = [w for w in words if len(w) >= min_length and w not in stop_words]
    
    # Count frequencies
    word_freq = {}
    for word in keywords:
        word_freq[word] = word_freq.get(word, 0) + 1
    
    # Get top keywords by frequency
    top_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return {
        "keywords": [word for word, count in top_keywords],
        "word_count": len(words),
        "unique_words": len(set(words))
    }


@action(
    name="calculate_percentage_change",
    requires={"old_value", "new_value"},
    produces={"percentage_change", "absolute_change", "direction"},
    description="Calculate percentage change between two values"
)
def calculate_percentage_change(old_value: float, new_value: float) -> Dict[str, Any]:
    """
    Calculate percentage and absolute change between values.
    
    Args:
        old_value: Original value
        new_value: New value
    
    Returns:
        dict with percentage_change, absolute_change, direction
    """
    absolute_change = new_value - old_value
    
    if old_value == 0:
        percentage_change = float('inf') if new_value > 0 else float('-inf')
        direction = "increase" if new_value > 0 else "decrease"
    else:
        percentage_change = (absolute_change / abs(old_value)) * 100
        direction = "increase" if absolute_change > 0 else "decrease" if absolute_change < 0 else "no_change"
    
    return {
        "percentage_change": round(percentage_change, 2) if percentage_change not in [float('inf'), float('-inf')] else str(percentage_change),
        "absolute_change": round(absolute_change, 2),
        "direction": direction
    }
