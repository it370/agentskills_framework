"""
Actions Module - Decorator and utilities for action-based skills

This module provides decorators and utilities to register Python functions
as actions that can be executed deterministically by the framework.

Actions are different from LLM tools:
- Actions are executed by the framework (planner decides when)
- Tools are executed by the LLM (LLM decides when)
- Actions are deterministic and guaranteed to run
- Tools are optional and context-dependent

Usage:
    from actions import action

    @action(
        name="calculate_risk_score",
        requires={"credit_score", "income", "debt"},
        produces={"risk_score", "risk_tier"}
    )
    def calculate_risk(credit_score, income, debt):
        # Your business logic here
        return {
            "risk_score": 85.5,
            "risk_tier": "low_risk"
        }
"""

from typing import Set, Callable, Optional, Dict, Any
from functools import wraps
import inspect


# Global registry for action functions (used by inline database skills)
ACTION_REGISTRY: Dict[str, Callable] = {}


def action(
    name: Optional[str] = None,
    requires: Optional[Set[str]] = None,
    produces: Optional[Set[str]] = None,
    description: Optional[str] = None,
    auto_register: bool = True
):
    """
    Decorator to mark functions as actions.
    
    Args:
        name: Action name (defaults to function name)
        requires: Set of required input field names
        produces: Set of output field names this action produces
        description: Human-readable description
        auto_register: Whether to auto-register with the framework
    
    Example:
        @action(
            name="validate_credit",
            requires={"credit_score", "income"},
            produces={"is_approved", "approval_tier"}
        )
        def validate_credit_application(credit_score, income):
            if credit_score >= 750 and income >= 50000:
                return {"is_approved": True, "approval_tier": "prime"}
            return {"is_approved": False, "approval_tier": None}
    """
    def decorator(func: Callable) -> Callable:
        # Store metadata on the function
        func._is_action = True
        func._action_name = name or func.__name__
        func._requires = requires or set()
        func._produces = produces or set()
        func._description = description or func.__doc__ or ""
        
        # Validate function signature matches requires
        sig = inspect.signature(func)
        params = set(sig.parameters.keys())
        
        if requires and not requires.issubset(params):
            missing = requires - params
            raise ValueError(
                f"Action '{func._action_name}' requires inputs {missing} "
                f"but function signature has {params}"
            )
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        # Copy metadata to wrapper
        wrapper._is_action = True
        wrapper._action_name = func._action_name
        wrapper._requires = func._requires
        wrapper._produces = func._produces
        wrapper._description = func._description
        
        # Auto-register if requested
        if auto_register:
            try:
                from engine import register_action_function
                # Get module name for full qualified name
                module = inspect.getmodule(func)
                module_name = module.__name__ if module else "unknown"
                full_name = f"{module_name}.{func._action_name}"
                register_action_function(full_name, wrapper)
            except ImportError:
                # Engine not yet loaded, will be registered via auto_discover_actions
                pass
        
        return wrapper
    
    return decorator


def validate_action_result(result: Any, expected_keys: Set[str], action_name: str) -> None:
    """
    Validate that an action result contains expected keys.
    
    Args:
        result: The result dict from the action
        expected_keys: Set of expected output keys
        action_name: Name of the action (for error messages)
    
    Raises:
        ValueError: If result is invalid
    """
    if not isinstance(result, dict):
        raise ValueError(
            f"Action '{action_name}' must return a dict, got {type(result)}"
        )
    
    result_keys = set(result.keys())
    missing = expected_keys - result_keys
    
    if missing:
        raise ValueError(
            f"Action '{action_name}' missing expected outputs: {missing}. "
            f"Produced: {result_keys}"
        )


def create_skill_from_action(
    func: Callable,
    executor: str = "action",
    hitl_enabled: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """
    Generate skill metadata from an @action decorated function.
    
    This allows you to create a skill YAML programmatically from a function.
    
    Args:
        func: Action-decorated function
        executor: Executor type (default: "action")
        hitl_enabled: Whether to enable human-in-the-loop
        **kwargs: Additional skill metadata
    
    Returns:
        Dict that can be used to create a Skill model
    
    Example:
        @action(requires={"x", "y"}, produces={"sum"})
        def add(x, y):
            return {"sum": x + y}
        
        skill_meta = create_skill_from_action(add)
        # Returns: {
        #     "name": "add",
        #     "requires": {"x", "y"},
        #     "produces": {"sum"},
        #     "executor": "action",
        #     "action": {...}
        # }
    """
    if not hasattr(func, '_is_action') or not func._is_action:
        raise ValueError(f"Function '{func.__name__}' is not decorated with @action")
    
    module = inspect.getmodule(func)
    module_name = module.__name__ if module else "unknown"
    
    return {
        "name": func._action_name,
        "description": func._description,
        "requires": func._requires,
        "produces": func._produces,
        "executor": executor,
        "hitl_enabled": hitl_enabled,
        "action": {
            "type": "python_function",
            "module": module_name,
            "function": func.__name__
        },
        **kwargs
    }


# Utility functions for common action patterns

def sync_action(func: Callable) -> Callable:
    """
    Wrapper to ensure sync action functions work with async executor.
    This is automatically handled by the framework, but can be used explicitly.
    """
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        import asyncio
        return await asyncio.to_thread(func, *args, **kwargs)
    
    # Preserve action metadata
    if hasattr(func, '_is_action'):
        async_wrapper._is_action = func._is_action
        async_wrapper._action_name = func._action_name
        async_wrapper._requires = func._requires
        async_wrapper._produces = func._produces
        async_wrapper._description = func._description
    
    return async_wrapper


def data_action(source: str, collection: Optional[str] = None):
    """
    Decorator for data-fetching actions.
    Automatically configures for data_query action type.
    
    Args:
        source: Data source (postgres, mongodb, redis)
        collection: Collection/table name for NoSQL databases
    
    Example:
        @data_action(source="postgres")
        def get_user_profile(user_id):
            return {
                "query": "SELECT * FROM users WHERE id = {user_id}",
                "source": "postgres"
            }
    """
    def decorator(func: Callable) -> Callable:
        func._is_action = True
        func._is_data_action = True
        func._data_source = source
        func._data_collection = collection
        return func
    return decorator
