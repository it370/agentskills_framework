"""
Functions Module - Reusable action function implementations

This module contains Python functions that can be used as actions in skills.
Functions here are reusable across multiple skills.

These are plain Python functions decorated with @action to make them
discoverable and executable by the framework.

Directory structure:
    functions/
        __init__.py          - Core reusable functions
        data_processing.py   - Data transformation functions
        ... (add more as needed)
"""

from actions import action
from typing import Dict, Any, List
from datetime import datetime, timedelta
import random


@action(
    name="calculate_risk_score",
    requires={"credit_score", "income", "debt", "employment_years"},
    produces={"risk_score", "risk_tier", "recommendation"},
    description="Calculate financial risk score based on credit profile"
)
def calculate_risk_score(credit_score: int, income: float, debt: float, employment_years: int) -> Dict[str, Any]:
    """
    Calculate risk score using weighted components.
    
    Returns:
        dict with risk_score (0-100), risk_tier, and recommendation
    """
    # Type conversion (handle string inputs)
    credit_score = int(credit_score)
    income = float(income)
    debt = float(debt)
    employment_years = int(employment_years)
    
    # Weighted scoring
    credit_component = (credit_score / 850) * 40
    income_component = min((income / 100000) * 30, 30)
    
    debt_ratio = debt / income if income > 0 else 1.0
    debt_component = max(0, 20 - (debt_ratio * 100))
    
    employment_component = min(employment_years * 2, 10)
    
    risk_score = credit_component + income_component + debt_component + employment_component
    
    # Determine tier
    if risk_score >= 80:
        tier = "low_risk"
        recommendation = "approve"
    elif risk_score >= 60:
        tier = "medium_risk"
        recommendation = "manual_review"
    else:
        tier = "high_risk"
        recommendation = "deny"
    
    return {
        "risk_score": round(risk_score, 2),
        "risk_tier": tier,
        "recommendation": recommendation
    }


@action(
    name="calculate_loan_terms",
    requires={"loan_amount", "risk_tier", "credit_score"},
    produces={"interest_rate", "monthly_payment", "term_months", "total_interest"},
    description="Calculate loan terms based on amount and risk profile"
)
def calculate_loan_terms(loan_amount: float, risk_tier: str, credit_score: int) -> Dict[str, Any]:
    """
    Calculate loan terms including interest rate and monthly payment.
    
    Args:
        loan_amount: Principal loan amount
        risk_tier: Risk tier (low_risk, medium_risk, high_risk)
        credit_score: Credit score
    
    Returns:
        dict with interest_rate, monthly_payment, term_months, total_interest
    """
    # Type conversion
    loan_amount = float(loan_amount)
    credit_score = int(credit_score)
    risk_tier = str(risk_tier)
    
    # Base interest rate by tier
    base_rates = {
        "low_risk": 3.5,
        "medium_risk": 6.5,
        "high_risk": 12.0
    }
    
    base_rate = base_rates.get(risk_tier, 10.0)
    
    # Adjust by credit score
    if credit_score >= 800:
        rate_adjustment = -0.5
    elif credit_score >= 750:
        rate_adjustment = 0.0
    elif credit_score >= 700:
        rate_adjustment = 0.5
    else:
        rate_adjustment = 1.0
    
    annual_rate = base_rate + rate_adjustment
    monthly_rate = annual_rate / 100 / 12
    
    # Term length by loan amount
    if loan_amount < 10000:
        term_months = 24
    elif loan_amount < 50000:
        term_months = 60
    else:
        term_months = 84
    
    # Calculate monthly payment using amortization formula
    if monthly_rate > 0:
        monthly_payment = loan_amount * (monthly_rate * (1 + monthly_rate)**term_months) / \
                         ((1 + monthly_rate)**term_months - 1)
    else:
        monthly_payment = loan_amount / term_months
    
    total_payment = monthly_payment * term_months
    total_interest = total_payment - loan_amount
    
    return {
        "interest_rate": round(annual_rate, 2),
        "monthly_payment": round(monthly_payment, 2),
        "term_months": term_months,
        "total_interest": round(total_interest, 2)
    }


@action(
    name="validate_document_completeness",
    requires={"documents"},
    produces={"is_complete", "missing_documents", "document_count"},
    description="Validate that all required documents are present"
)
def validate_document_completeness(documents: List[str]) -> Dict[str, Any]:
    """
    Check if all required documents are provided.
    
    Args:
        documents: List of document types provided
    
    Returns:
        dict with is_complete, missing_documents, document_count
    """
    required_documents = {
        "id_proof",
        "income_proof",
        "address_proof",
        "employment_letter"
    }
    
    provided = set(doc.lower().replace(" ", "_") for doc in documents)
    missing = required_documents - provided
    
    return {
        "is_complete": len(missing) == 0,
        "missing_documents": sorted(list(missing)),
        "document_count": len(documents)
    }


@action(
    name="calculate_shipping_cost",
    requires={"weight_kg", "distance_km", "service_level"},
    produces={"shipping_cost", "estimated_days", "service_selected"},
    description="Calculate shipping cost based on weight, distance, and service level"
)
def calculate_shipping_cost(weight_kg: float, distance_km: float, service_level: str) -> Dict[str, Any]:
    """
    Calculate shipping cost using weight and distance.
    
    Args:
        weight_kg: Package weight in kilograms
        distance_km: Shipping distance in kilometers
        service_level: Service level (express, standard, economy)
    
    Returns:
        dict with shipping_cost, estimated_days, service_selected
    """
    # Type conversion
    weight_kg = float(weight_kg)
    distance_km = float(distance_km)
    service_level = str(service_level)
    
    base_rate = 5.0
    weight_charge = weight_kg * 0.5
    distance_charge = distance_km * 0.1
    
    service_multipliers = {
        'express': (2.0, 1),
        'standard': (1.0, 3),
        'economy': (0.7, 7)
    }
    
    service_level_lower = service_level.lower()
    multiplier, days = service_multipliers.get(service_level_lower, (1.0, 3))
    
    cost = (base_rate + weight_charge + distance_charge) * multiplier
    
    return {
        "shipping_cost": round(cost, 2),
        "estimated_days": days,
        "service_selected": service_level_lower
    }


@action(
    name="merge_candidate_data",
    requires={"profile_data", "screening_results", "verification_results"},
    produces={"merged_profile", "data_quality_score"},
    description="Merge candidate data from multiple sources into unified profile"
)
def merge_candidate_data(
    profile_data: Dict[str, Any],
    screening_results: Dict[str, Any],
    verification_results: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Merge candidate information from multiple sources.
    
    Args:
        profile_data: Basic profile information
        screening_results: Background screening results
        verification_results: Document verification results
    
    Returns:
        dict with merged_profile and data_quality_score
    """
    merged = {
        "personal": profile_data,
        "screening": screening_results,
        "verification": verification_results,
        "merged_at": datetime.utcnow().isoformat()
    }
    
    # Calculate data quality score
    total_fields = 0
    filled_fields = 0
    
    for section in [profile_data, screening_results, verification_results]:
        for key, value in section.items():
            total_fields += 1
            if value is not None and value != "":
                filled_fields += 1
    
    quality_score = (filled_fields / total_fields * 100) if total_fields > 0 else 0
    
    return {
        "merged_profile": merged,
        "data_quality_score": round(quality_score, 2)
    }


@action(
    name="calculate_compound_interest",
    requires={"principal", "rate", "years"},
    produces={"final_amount", "interest_earned", "growth_rate"},
    description="Calculate compound interest for investments"
)
def calculate_compound_interest(principal: float, rate: float, years: int) -> Dict[str, Any]:
    """
    Calculate compound interest using the standard formula.
    
    Args:
        principal: Initial investment amount
        rate: Annual interest rate (as decimal, e.g., 0.05 for 5%)
        years: Number of years
    
    Returns:
        dict with final_amount, interest_earned, growth_rate
    """
    # Type conversion
    principal = float(principal)
    rate = float(rate)
    years = int(years)
    
    final_amount = principal * ((1 + rate) ** years)
    interest_earned = final_amount - principal
    growth_rate = ((final_amount / principal) - 1) * 100
    
    return {
        "final_amount": round(final_amount, 2),
        "interest_earned": round(interest_earned, 2),
        "growth_rate": round(growth_rate, 2)
    }


@action(
    name="generate_invoice",
    requires={"order_items", "tax_rate", "customer_tier"},
    produces={"invoice_total", "discount_applied", "line_items", "tax_amount"},
    description="Generate invoice with line items, discounts, and tax"
)
def generate_invoice(
    order_items: List[Dict[str, Any]],
    tax_rate: float,
    customer_tier: str
) -> Dict[str, Any]:
    """
    Generate a complete invoice with discounts and tax.
    
    Args:
        order_items: List of items with 'price' and 'quantity'
        tax_rate: Tax rate as decimal (e.g., 0.08 for 8%)
        customer_tier: Customer tier (premium, standard, basic)
    
    Returns:
        dict with invoice_total, discount_applied, line_items, tax_amount
    """
    # Type conversion
    tax_rate = float(tax_rate)
    customer_tier = str(customer_tier)
    
    # Calculate subtotal
    subtotal = sum(item['price'] * item['quantity'] for item in order_items)
    
    # Apply tier-based discount
    discount_rates = {
        'premium': 0.15,
        'standard': 0.05,
        'basic': 0.0
    }
    discount_rate = discount_rates.get(customer_tier.lower(), 0.0)
    discount_amount = subtotal * discount_rate
    
    # Calculate amounts
    after_discount = subtotal - discount_amount
    tax_amount = after_discount * tax_rate
    total = after_discount + tax_amount
    
    # Build line items
    line_items = [
        {
            **item,
            'subtotal': round(item['price'] * item['quantity'], 2)
        }
        for item in order_items
    ]
    
    return {
        "invoice_total": round(total, 2),
        "discount_applied": round(discount_amount, 2),
        "line_items": line_items,
        "tax_amount": round(tax_amount, 2)
    }


# Example of an async action
@action(
    name="simulate_processing_delay",
    requires={"task_name"},
    produces={"completed", "duration_seconds"},
    description="Simulate a time-consuming process (for testing)"
)
async def simulate_processing_delay(task_name: str) -> Dict[str, Any]:
    """
    Simulate a processing delay (useful for testing async actions).
    
    Args:
        task_name: Name of the task being simulated
    
    Returns:
        dict with completed status and duration
    """
    import asyncio
    
    # Simulate some work
    duration = random.uniform(0.5, 2.0)
    await asyncio.sleep(duration)
    
    return {
        "completed": True,
        "duration_seconds": round(duration, 2)
    }
