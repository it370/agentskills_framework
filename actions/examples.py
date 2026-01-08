"""
Examples: Using the Action Executor System

This module demonstrates how to use the various action types in the framework.
Run this file directly to see examples of:
- Action function registration
- Auto-discovery
- Testing actions
- Performance comparisons
- Data pipelines
"""

import asyncio
from pathlib import Path
from engine import (
    auto_discover_actions,
    register_action_function,
    SKILL_REGISTRY
)


# Example 1: Simple action function registration
def add_numbers(x: float, y: float) -> dict:
    """Simple addition function."""
    return {"sum": x + y}


# Example 2: Register custom action
register_action_function("actions.examples.add_numbers", add_numbers)


# Example 3: Auto-discover actions from modules
def setup_actions():
    """Setup and discover all action functions."""
    print("[SETUP] Discovering actions from functions modules...")
    
    auto_discover_actions([
        "functions",
        "functions.data_processing"
    ])
    
    print("[SETUP] Actions registered successfully!")


# Example 4: List all action-based skills
def list_action_skills():
    """List all skills using action executor."""
    print("\n[SKILLS] Action-based skills:")
    
    action_skills = [s for s in SKILL_REGISTRY if s.executor == "action"]
    
    for skill in action_skills:
        action_type = skill.action.type.value if skill.action else "unknown"
        print(f"  - {skill.name} ({action_type})")
        print(f"    Requires: {skill.requires}")
        print(f"    Produces: {skill.produces}")
    
    return action_skills


# Example 5: Test an action function directly
async def test_action_function():
    """Test a function directly."""
    from functions import calculate_risk_score
    
    print("\n[TEST] Testing risk calculation...")
    
    result = calculate_risk_score(
        credit_score=750,
        income=75000.0,
        debt=15000.0,
        employment_years=5
    )
    
    print(f"  Risk Score: {result['risk_score']}")
    print(f"  Risk Tier: {result['risk_tier']}")
    print(f"  Recommendation: {result['recommendation']}")
    
    return result


# Example 6: Run a complete workflow with action skills
async def run_action_workflow():
    """Run a sample workflow using action skills."""
    from engine import app
    
    print("\n[WORKFLOW] Starting action-based workflow...")
    
    initial_state = {
        "layman_sop": "Calculate risk and loan terms for applicant",
        "data_store": {
            "credit_score": 720,
            "income": 60000.0,
            "debt": 10000.0,
            "employment_years": 3,
            "loan_amount": 25000.0
        },
        "history": ["Process Started"],
        "thread_id": "action_test_001"
    }
    
    config = {"configurable": {"thread_id": "action_test_001"}}
    
    # Run the workflow
    result = await app.ainvoke(initial_state, config)
    
    print("\n[WORKFLOW] Completed!")
    print(f"  Final data keys: {list(result['data_store'].keys())}")
    
    # Show action skills that were executed
    history = result.get('history', [])
    action_executions = [h for h in history if '(action)' in h]
    print(f"  Actions executed: {len(action_executions)}")
    for execution in action_executions:
        print(f"    - {execution}")
    
    return result


# Example 7: Compare LLM vs Action performance
async def compare_performance():
    """Compare execution time: LLM vs Action."""
    import time
    from functions import generate_invoice
    
    print("\n[PERFORMANCE] Comparing LLM vs Action execution...")
    
    test_data = {
        "order_items": [
            {"name": "Product A", "price": 100.0, "quantity": 2},
            {"name": "Product B", "price": 50.0, "quantity": 1}
        ],
        "tax_rate": 0.08,
        "customer_tier": "premium"
    }
    
    # Time action execution
    start = time.time()
    result = generate_invoice(**test_data)
    action_time = time.time() - start
    
    print(f"  Action executor: {action_time*1000:.2f}ms")
    print(f"  Invoice total: ${result['invoice_total']}")
    print(f"  Discount: ${result['discount_applied']}")
    
    print(f"\n  Estimated LLM time: ~2-3 seconds")
    print(f"  Speedup: ~{(2.5/action_time):.0f}x faster")
    print(f"  Cost savings: ~99.9% cheaper")


# Example 8: Data pipeline simulation
def simulate_data_pipeline():
    """Simulate what a data pipeline does."""
    print("\n[PIPELINE] Simulating multi-source data pipeline...")
    
    # Step 1: Query from PostgreSQL (simulated)
    candidate_base = {
        "id": 123,
        "name": "John Doe",
        "email": "john@example.com"
    }
    print(f"  Step 1: Fetched candidate base data from PostgreSQL")
    
    # Step 2: Query from MongoDB (simulated)
    documents = [
        {"type": "resume", "status": "verified"},
        {"type": "certificate", "status": "verified"}
    ]
    print(f"  Step 2: Fetched {len(documents)} documents from MongoDB")
    
    # Step 3: Query verifications (simulated)
    verifications = {
        "identity": "verified",
        "employment": "verified",
        "education": "pending"
    }
    print(f"  Step 3: Fetched verification results from MongoDB")
    
    # Step 4: Merge
    enriched = {
        **candidate_base,
        "documents": documents,
        "verifications": verifications
    }
    print(f"  Step 4: Merged data from all sources")
    print(f"\n  Enriched profile keys: {list(enriched.keys())}")
    
    return enriched


def main():
    """Main entry point for examples."""
    print("=" * 60)
    print("Action Executor System - Examples")
    print("=" * 60)
    
    # Setup
    setup_actions()
    
    # List skills
    list_action_skills()
    
    # Run examples
    asyncio.run(test_action_function())
    asyncio.run(compare_performance())
    simulate_data_pipeline()
    
    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Review documentation in documentations/ folder")
    print("  2. Check skills/ directory for example skills")
    print("  3. Create your own functions in functions/")
    print("  4. Run workflows with: python main.py")


if __name__ == "__main__":
    main()
