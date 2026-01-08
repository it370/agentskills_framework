"""
Skill-local action for CustomPricingCalculator

This file contains the action logic specific to this skill.
It's automatically discovered and loaded by the framework.
"""


def calculate_custom_pricing(base_price: float, quantity: int, customer_type: str) -> dict:
    """
    Calculate pricing with custom business rules.
    
    This function is skill-local and self-contained.
    No dependencies on global business_logic modules.
    
    Args:
        base_price: Base price per unit
        quantity: Number of units
        customer_type: Customer tier (vip, member, regular)
    
    Returns:
        dict with final_price, discount_percent, bulk_discount
    """
    
    # Type conversion (handle string inputs from various sources)
    base_price = float(base_price)
    quantity = int(quantity)
    customer_type = str(customer_type)
    
    # Base calculation
    subtotal = base_price * quantity
    
    # Customer tier discounts
    tier_discounts = {
        "vip": 0.20,      # 20% off
        "member": 0.10,   # 10% off
        "regular": 0.05   # 5% off
    }
    
    discount_percent = tier_discounts.get(customer_type.lower(), 0.0)
    
    # Bulk discounts (additional)
    bulk_discount = 0.0
    if quantity >= 100:
        bulk_discount = 0.15  # Additional 15% off
    elif quantity >= 50:
        bulk_discount = 0.10  # Additional 10% off
    elif quantity >= 10:
        bulk_discount = 0.05  # Additional 5% off
    
    # Apply discounts
    total_discount = discount_percent + bulk_discount
    total_discount = min(total_discount, 0.50)  # Cap at 50% total discount
    
    discount_amount = subtotal * total_discount
    final_price = subtotal - discount_amount
    
    return {
        "final_price": round(final_price, 2),
        "discount_percent": round(total_discount * 100, 2),
        "bulk_discount": round(bulk_discount * 100, 2)
    }


# Additional helper functions for this skill (if needed)
def validate_pricing_inputs(base_price: float, quantity: int) -> bool:
    """Validate pricing calculation inputs."""
    return base_price > 0 and quantity > 0


# You can have multiple functions in this file
# The framework will load whichever one is specified in skill.md
