"""
Comprehensive test suite for skill output parsing across all executor types.

Tests output mapping, produces validation, optional_produces handling, and edge cases
for REST, ACTION (all sub-types), and LLM executors.

Run with:
    python -m pytest tests/test_output_parsing.py -v
    or
    python tests/test_output_parsing.py
"""

import sys
import asyncio
from pathlib import Path
from typing import Dict, Any, Set, Optional
from unittest.mock import AsyncMock, Mock, patch, MagicMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import (
    _execute_skill_core,
    Skill,
    ActionConfig,
    ActionType,
    RestConfig,
)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_skill(
    name: str,
    executor: str,
    produces: Set[str],
    optional_produces: Set[str] = None,
    action: Optional[ActionConfig] = None,
    rest: Optional[RestConfig] = None,
) -> Skill:
    """Helper to create a Skill with specified config"""
    return Skill(
        name=name,
        description=f"Test skill {name}",
        requires=set(),
        produces=produces,
        optional_produces=optional_produces or set(),
        executor=executor,
        action=action,
        rest=rest,
    )


def create_action_config(action_type: ActionType, **kwargs) -> ActionConfig:
    """Helper to create ActionConfig"""
    config = {
        "type": action_type,
    }
    config.update(kwargs)
    return ActionConfig(**config)


# ============================================================================
# MOCK EXECUTORS
# ============================================================================

async def mock_execute_rest_skill(skill_meta, state, input_ctx):
    """Mock REST executor - returns state with data_store"""
    mock_result = state.get("_mock_result", {})
    return {"data_store": mock_result}


async def mock_execute_data_query(cfg, inputs):
    """Mock data query executor"""
    # Return mock data stored in cfg
    return getattr(cfg, "_mock_result", {"query_result": "data"})


async def mock_execute_data_pipeline(cfg, inputs, workspace_id=None):
    """Mock data pipeline executor"""
    return getattr(cfg, "_mock_result", {"pipeline_output": "data"})


async def mock_execute_python_function(cfg, inputs, state):
    """Mock Python function executor"""
    return getattr(cfg, "_mock_result", {"function_output": "data"})


async def mock_execute_script(cfg, inputs):
    """Mock script executor"""
    return getattr(cfg, "_mock_result", {"script_output": "data"})


async def mock_execute_http_call(cfg, inputs):
    """Mock HTTP call executor"""
    return getattr(cfg, "_mock_result", {"http_response": "data"})


def mock_structured_llm(dynamic_model):
    """Mock LLM with structured output"""
    llm_mock = AsyncMock()
    
    async def mock_ainvoke(messages):
        # Create an instance of the dynamic model with mock data
        result_data = getattr(dynamic_model, "_mock_result", {})
        return dynamic_model(**result_data)
    
    llm_mock.ainvoke = mock_ainvoke
    return llm_mock


# ============================================================================
# TEST CLASS
# ============================================================================

class TestOutputParsing:
    """Comprehensive tests for output parsing across all executor types"""
    
    # ========================================================================
    # REST EXECUTOR TESTS
    # ========================================================================
    
    @patch("engine._execute_rest_skill", side_effect=mock_execute_rest_skill)
    async def test_rest_single_produces(self, mock_rest):
        """REST executor with single produces key"""
        skill = create_skill(
            name="TestREST",
            executor="rest",
            produces={"output1"},
        )
        
        state = {
            "_mock_result": {"output1": "value1"},
            "data_store": {},
        }
        
        result = await _execute_skill_core(skill, {}, state)
        assert result == {"output1": "value1"}
    
    @patch("engine._execute_rest_skill", side_effect=mock_execute_rest_skill)
    async def test_rest_multiple_produces(self, mock_rest):
        """REST executor with multiple produces keys"""
        skill = create_skill(
            name="TestREST",
            executor="rest",
            produces={"output1", "output2"},
        )
        
        state = {
            "_mock_result": {"output1": "value1", "output2": "value2"},
            "data_store": {},
        }
        
        result = await _execute_skill_core(skill, {}, state)
        assert result == {"output1": "value1", "output2": "value2"}
    
    @patch("engine._execute_rest_skill", side_effect=mock_execute_rest_skill)
    async def test_rest_with_optional_produces(self, mock_rest):
        """REST executor with optional_produces present"""
        skill = create_skill(
            name="TestREST",
            executor="rest",
            produces={"output1"},
            optional_produces={"optional1", "optional2"},
        )
        
        state = {
            "_mock_result": {
                "output1": "value1",
                "optional1": "opt_value1",
                "optional2": "opt_value2",
            },
            "data_store": {},
        }
        
        result = await _execute_skill_core(skill, {}, state)
        assert result == {
            "output1": "value1",
            "optional1": "opt_value1",
            "optional2": "opt_value2",
        }
    
    @patch("engine._execute_rest_skill", side_effect=mock_execute_rest_skill)
    async def test_rest_optional_produces_missing(self, mock_rest):
        """REST executor with optional_produces missing (should not error)"""
        skill = create_skill(
            name="TestREST",
            executor="rest",
            produces={"output1"},
            optional_produces={"optional1"},
        )
        
        state = {
            "_mock_result": {"output1": "value1"},
            "data_store": {},
        }
        
        result = await _execute_skill_core(skill, {}, state)
        assert result == {"output1": "value1"}
    
    @patch("engine._execute_rest_skill", side_effect=mock_execute_rest_skill)
    async def test_rest_extra_keys_ignored(self, mock_rest):
        """REST executor ignores keys not in produces or optional_produces"""
        skill = create_skill(
            name="TestREST",
            executor="rest",
            produces={"output1"},
        )
        
        state = {
            "_mock_result": {
                "output1": "value1",
                "extra_key": "should_be_ignored",
            },
            "data_store": {},
        }
        
        result = await _execute_skill_core(skill, {}, state)
        assert result == {"output1": "value1"}
        assert "extra_key" not in result
    
    @patch("engine._execute_rest_skill", side_effect=mock_execute_rest_skill)
    async def test_rest_no_data_store(self, mock_rest):
        """REST executor returns empty dict when data_store missing"""
        skill = create_skill(
            name="TestREST",
            executor="rest",
            produces={"output1"},
        )
        
        async def mock_no_datastore(skill_meta, state, input_ctx):
            return {}  # No data_store key
        
        with patch("engine._execute_rest_skill", side_effect=mock_no_datastore):
            result = await _execute_skill_core(skill, {}, {})
            assert result == {}
    
    # ========================================================================
    # ACTION EXECUTOR - DATA_QUERY TESTS
    # ========================================================================
    
    @patch("engine._execute_data_query", side_effect=mock_execute_data_query)
    @patch("engine.publish_log", new_callable=AsyncMock)
    async def test_data_query_single_produces(self, mock_log, mock_query):
        """DATA_QUERY with single produces key - entire result wrapped under key"""
        action_cfg = create_action_config(ActionType.DATA_QUERY, query="SELECT *")
        action_cfg._mock_result = {"result": [1, 2, 3]}
        
        skill = create_skill(
            name="TestQuery",
            executor="action",
            produces={"output"},  # Different key than result
            action=action_cfg,
        )
        
        result = await _execute_skill_core(skill, {}, {})
        # For single produces, entire result dict is wrapped
        assert result == {"output": {"result": [1, 2, 3]}}
    
    @patch("engine._execute_data_query", side_effect=mock_execute_data_query)
    @patch("engine.publish_log", new_callable=AsyncMock)
    async def test_data_query_multiple_produces(self, mock_log, mock_query):
        """DATA_QUERY with multiple produces keys"""
        action_cfg = create_action_config(ActionType.DATA_QUERY, query="SELECT *")
        action_cfg._mock_result = {"users": [], "count": 10}
        
        skill = create_skill(
            name="TestQuery",
            executor="action",
            produces={"users", "count"},
            action=action_cfg,
        )
        
        result = await _execute_skill_core(skill, {}, {})
        assert result == {"users": [], "count": 10}
    
    @patch("engine._execute_data_query", side_effect=mock_execute_data_query)
    @patch("engine.publish_log", new_callable=AsyncMock)
    async def test_data_query_with_optional_produces(self, mock_log, mock_query):
        """DATA_QUERY with optional_produces present"""
        action_cfg = create_action_config(ActionType.DATA_QUERY, query="SELECT *")
        action_cfg._mock_result = {
            "users": [],
            "count": 10,
            "metadata": {"page": 1},
        }
        
        skill = create_skill(
            name="TestQuery",
            executor="action",
            produces={"users", "count"},
            optional_produces={"metadata"},
            action=action_cfg,
        )
        
        result = await _execute_skill_core(skill, {}, {})
        assert result == {"users": [], "count": 10, "metadata": {"page": 1}}
    
    @patch("engine._execute_data_query", side_effect=mock_execute_data_query)
    @patch("engine.publish_log", new_callable=AsyncMock)
    async def test_data_query_optional_missing(self, mock_log, mock_query):
        """DATA_QUERY with optional_produces missing (no error)"""
        action_cfg = create_action_config(ActionType.DATA_QUERY, query="SELECT *")
        action_cfg._mock_result = {"users": [], "count": 10}
        
        skill = create_skill(
            name="TestQuery",
            executor="action",
            produces={"users", "count"},
            optional_produces={"metadata", "extras"},
            action=action_cfg,
        )
        
        result = await _execute_skill_core(skill, {}, {})
        assert result == {"users": [], "count": 10}
        assert "metadata" not in result
        assert "extras" not in result
    
    @patch("engine._execute_data_query", side_effect=mock_execute_data_query)
    @patch("engine.publish_log", new_callable=AsyncMock)
    async def test_data_query_missing_required_produces_error(self, mock_log, mock_query):
        """DATA_QUERY missing required produces key should error"""
        action_cfg = create_action_config(ActionType.DATA_QUERY, query="SELECT *")
        action_cfg._mock_result = {"users": []}  # Missing 'count'
        
        skill = create_skill(
            name="TestQuery",
            executor="action",
            produces={"users", "count"},
            action=action_cfg,
        )
        
        try:
            await _execute_skill_core(skill, {}, {})
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Missing expected keys" in str(e)
    
    # ========================================================================
    # ACTION EXECUTOR - DATA_PIPELINE TESTS (SPECIAL CASES)
    # ========================================================================
    
    @patch("engine._execute_data_pipeline", side_effect=mock_execute_data_pipeline)
    @patch("engine.publish_log", new_callable=AsyncMock)
    async def test_data_pipeline_single_produces_match(self, mock_log, mock_pipeline):
        """DATA_PIPELINE with single produces - key matches pipeline output"""
        action_cfg = create_action_config(ActionType.DATA_PIPELINE, steps=[])
        action_cfg._mock_result = {"game_name": "chess"}
        
        skill = create_skill(
            name="TestPipeline",
            executor="action",
            produces={"game_name"},
            action=action_cfg,
        )
        
        result = await _execute_skill_core(skill, {}, {})
        assert result == {"game_name": "chess"}
    
    @patch("engine._execute_data_pipeline", side_effect=mock_execute_data_pipeline)
    @patch("engine.publish_log", new_callable=AsyncMock)
    async def test_data_pipeline_single_produces_with_optional(self, mock_log, mock_pipeline):
        """DATA_PIPELINE with single produces + optional_produces"""
        action_cfg = create_action_config(ActionType.DATA_PIPELINE, steps=[])
        action_cfg._mock_result = {
            "game_name": "chess",
            "player_stats": {"wins": 10},
            "extra_data": "ignored",
        }
        
        skill = create_skill(
            name="TestPipeline",
            executor="action",
            produces={"game_name"},
            optional_produces={"player_stats"},
            action=action_cfg,
        )
        
        result = await _execute_skill_core(skill, {}, {})
        assert result == {
            "game_name": "chess",
            "player_stats": {"wins": 10},
        }
        assert "extra_data" not in result
    
    @patch("engine._execute_data_pipeline", side_effect=mock_execute_data_pipeline)
    @patch("engine.publish_log", new_callable=AsyncMock)
    async def test_data_pipeline_single_produces_mismatch_error(self, mock_log, mock_pipeline):
        """DATA_PIPELINE single produces - required key missing should error"""
        action_cfg = create_action_config(ActionType.DATA_PIPELINE, steps=[])
        action_cfg._mock_result = {"wrong_key": "value"}
        
        skill = create_skill(
            name="TestPipeline",
            executor="action",
            produces={"game_name"},
            action=action_cfg,
        )
        
        try:
            await _execute_skill_core(skill, {}, {})
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Missing expected key" in str(e)
    
    @patch("engine._execute_data_pipeline", side_effect=mock_execute_data_pipeline)
    @patch("engine.publish_log", new_callable=AsyncMock)
    async def test_data_pipeline_multiple_step_outputs(self, mock_log, mock_pipeline):
        """DATA_PIPELINE with multiple step outputs"""
        action_cfg = create_action_config(ActionType.DATA_PIPELINE, steps=[])
        action_cfg._mock_result = {
            "step1_output": "value1",
            "step2_output": "value2",
            "step3_output": "value3",
        }
        
        skill = create_skill(
            name="TestPipeline",
            executor="action",
            produces={"step1_output", "step3_output"},
            optional_produces={"step2_output"},
            action=action_cfg,
        )
        
        result = await _execute_skill_core(skill, {}, {})
        assert result == {
            "step1_output": "value1",
            "step2_output": "value2",
            "step3_output": "value3",
        }
    
    @patch("engine._execute_data_pipeline", side_effect=mock_execute_data_pipeline)
    @patch("engine.publish_log", new_callable=AsyncMock)
    async def test_data_pipeline_array_outputs(self, mock_log, mock_pipeline):
        """DATA_PIPELINE with array outputs"""
        action_cfg = create_action_config(ActionType.DATA_PIPELINE, steps=[])
        action_cfg._mock_result = {
            "items": [1, 2, 3, 4, 5],
            "filtered_items": [2, 4],
        }
        
        skill = create_skill(
            name="TestPipeline",
            executor="action",
            produces={"items"},
            optional_produces={"filtered_items"},
            action=action_cfg,
        )
        
        result = await _execute_skill_core(skill, {}, {})
        assert result == {
            "items": [1, 2, 3, 4, 5],
            "filtered_items": [2, 4],
        }
    
    @patch("engine._execute_data_pipeline", side_effect=mock_execute_data_pipeline)
    @patch("engine.publish_log", new_callable=AsyncMock)
    async def test_data_pipeline_none_values(self, mock_log, mock_pipeline):
        """DATA_PIPELINE with None values in outputs"""
        action_cfg = create_action_config(ActionType.DATA_PIPELINE, steps=[])
        action_cfg._mock_result = {
            "result": None,
            "optional_result": None,
        }
        
        skill = create_skill(
            name="TestPipeline",
            executor="action",
            produces={"result"},
            optional_produces={"optional_result"},
            action=action_cfg,
        )
        
        result = await _execute_skill_core(skill, {}, {})
        assert result == {
            "result": None,
            "optional_result": None,
        }
    
    @patch("engine._execute_data_pipeline", side_effect=mock_execute_data_pipeline)
    @patch("engine.publish_log", new_callable=AsyncMock)
    async def test_data_pipeline_empty_result(self, mock_log, mock_pipeline):
        """DATA_PIPELINE with empty result dict"""
        action_cfg = create_action_config(ActionType.DATA_PIPELINE, steps=[])
        action_cfg._mock_result = {}
        
        skill = create_skill(
            name="TestPipeline",
            executor="action",
            produces={"output"},
            action=action_cfg,
        )
        
        try:
            await _execute_skill_core(skill, {}, {})
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Missing expected key" in str(e)
    
    @patch("engine._execute_data_pipeline", side_effect=mock_execute_data_pipeline)
    @patch("engine.publish_log", new_callable=AsyncMock)
    async def test_data_pipeline_complex_nested_data(self, mock_log, mock_pipeline):
        """DATA_PIPELINE with complex nested data structures"""
        action_cfg = create_action_config(ActionType.DATA_PIPELINE, steps=[])
        action_cfg._mock_result = {
            "user_data": {
                "id": 123,
                "profile": {
                    "name": "John",
                    "scores": [10, 20, 30],
                },
            },
            "metadata": {
                "timestamp": "2026-01-16",
                "version": "1.0",
            },
        }
        
        skill = create_skill(
            name="TestPipeline",
            executor="action",
            produces={"user_data"},
            optional_produces={"metadata"},
            action=action_cfg,
        )
        
        result = await _execute_skill_core(skill, {}, {})
        assert result["user_data"]["id"] == 123
        assert result["user_data"]["profile"]["scores"] == [10, 20, 30]
        assert result["metadata"]["version"] == "1.0"
    
    # ========================================================================
    # ACTION EXECUTOR - OTHER ACTION TYPES
    # ========================================================================
    
    @patch("engine._execute_python_function", side_effect=mock_execute_python_function)
    @patch("engine.publish_log", new_callable=AsyncMock)
    async def test_python_function_with_optional(self, mock_log, mock_func):
        """PYTHON_FUNCTION with optional_produces - single produces wraps entire result"""
        action_cfg = create_action_config(
            ActionType.PYTHON_FUNCTION,
            module_path="test",
            function_name="test",
        )
        action_cfg._mock_result = {
            "output": "result",
            "debug_info": "extra",
        }
        
        skill = create_skill(
            name="TestFunction",
            executor="action",
            produces={"wrapped_output"},  # Single produces wraps entire result
            action=action_cfg,
        )
        
        result = await _execute_skill_core(skill, {}, {})
        # Single produces: entire result dict wrapped under the key
        assert result == {"wrapped_output": {"output": "result", "debug_info": "extra"}}
    
    @patch("engine._execute_script", side_effect=mock_execute_script)
    @patch("engine.publish_log", new_callable=AsyncMock)
    async def test_script_with_optional_missing(self, mock_log, mock_script):
        """SCRIPT with single produces wraps entire result"""
        action_cfg = create_action_config(
            ActionType.SCRIPT,
            script_path="test.sh",
        )
        action_cfg._mock_result = {"output": "result"}
        
        skill = create_skill(
            name="TestScript",
            executor="action",
            produces={"script_result"},  # Single produces wraps
            action=action_cfg,
        )
        
        result = await _execute_skill_core(skill, {}, {})
        assert result == {"script_result": {"output": "result"}}
    
    @patch("engine._execute_http_call", side_effect=mock_execute_http_call)
    @patch("engine.publish_log", new_callable=AsyncMock)
    async def test_http_call_with_multiple_optional(self, mock_log, mock_http):
        """HTTP_CALL with multiple optional_produces - single produces wraps entire result"""
        action_cfg = create_action_config(
            ActionType.HTTP_CALL,
            url="http://test.com",
            method="GET",
        )
        action_cfg._mock_result = {
            "response_body": {"data": "test"},
            "status_code": 200,
            "headers": {"content-type": "application/json"},
        }
        
        skill = create_skill(
            name="TestHTTP",
            executor="action",
            produces={"http_response"},  # Single produces wraps all
            action=action_cfg,
        )
        
        result = await _execute_skill_core(skill, {}, {})
        # Single produces wraps entire result
        assert result["http_response"]["response_body"] == {"data": "test"}
        assert result["http_response"]["status_code"] == 200
    
    @patch("engine._execute_http_call", side_effect=mock_execute_http_call)
    @patch("engine.publish_log", new_callable=AsyncMock)
    async def test_http_call_multiple_produces_with_optional(self, mock_log, mock_http):
        """HTTP_CALL with MULTIPLE produces + optional_produces (key-based mapping)"""
        action_cfg = create_action_config(
            ActionType.HTTP_CALL,
            url="http://test.com",
            method="GET",
        )
        action_cfg._mock_result = {
            "response_body": {"data": "test"},
            "status_code": 200,
            "headers": {"content-type": "application/json"},
            "timing": 123,
        }
        
        skill = create_skill(
            name="TestHTTP",
            executor="action",
            produces={"response_body", "status_code"},  # Multiple produces
            optional_produces={"headers", "timing"},    # Optional
            action=action_cfg,
        )
        
        result = await _execute_skill_core(skill, {}, {})
        # Multiple produces: key-based extraction (no wrapping)
        assert result == {
            "response_body": {"data": "test"},
            "status_code": 200,
            "headers": {"content-type": "application/json"},
            "timing": 123,
        }
    
    @patch("engine._execute_python_function", side_effect=mock_execute_python_function)
    @patch("engine.publish_log", new_callable=AsyncMock)
    async def test_python_function_multiple_produces_with_optional(self, mock_log, mock_func):
        """PYTHON_FUNCTION with multiple produces + optional"""
        action_cfg = create_action_config(
            ActionType.PYTHON_FUNCTION,
            module_path="test",
            function_name="test",
        )
        action_cfg._mock_result = {
            "result": "value1",
            "count": 42,
            "debug_info": "extra",
        }
        
        skill = create_skill(
            name="TestFunction",
            executor="action",
            produces={"result", "count"},
            optional_produces={"debug_info"},
            action=action_cfg,
        )
        
        result = await _execute_skill_core(skill, {}, {})
        assert result == {"result": "value1", "count": 42, "debug_info": "extra"}
    
    @patch("engine._execute_script", side_effect=mock_execute_script)
    @patch("engine.publish_log", new_callable=AsyncMock)
    async def test_script_multiple_produces_optional_missing(self, mock_log, mock_script):
        """SCRIPT with multiple produces and optional missing"""
        action_cfg = create_action_config(
            ActionType.SCRIPT,
            script_path="test.sh",
        )
        action_cfg._mock_result = {
            "stdout": "output",
            "exit_code": 0,
        }
        
        skill = create_skill(
            name="TestScript",
            executor="action",
            produces={"stdout", "exit_code"},
            optional_produces={"stderr", "duration"},
            action=action_cfg,
        )
        
        result = await _execute_skill_core(skill, {}, {})
        assert result == {"stdout": "output", "exit_code": 0}
        assert "stderr" not in result
        assert "duration" not in result
    
    # ========================================================================
    # LLM EXECUTOR TESTS
    # ========================================================================
    
    @patch("engine._structured_llm", side_effect=mock_structured_llm)
    @patch("engine._run_agent_tools", return_value=(None, []))
    @patch("engine.publish_log", new_callable=AsyncMock)
    async def test_llm_single_produces(self, mock_log, mock_tools, mock_llm_func):
        """LLM executor with single produces"""
        skill = create_skill(
            name="TestLLM",
            executor="llm",
            produces={"summary"},
        )
        skill.prompt = "Summarize this"
        
        # Mock the dynamic model result
        with patch("engine.create_model") as mock_create_model:
            mock_model = Mock()
            mock_model._mock_result = {"summary": "test summary"}
            mock_create_model.return_value = mock_model
            
            result = await _execute_skill_core(skill, {"text": "test"}, {})
            # LLM executor extracts from Pydantic model attributes
            # The mock returns the model instance
    
    @patch("engine._structured_llm", side_effect=mock_structured_llm)
    @patch("engine._run_agent_tools", return_value=(None, []))
    @patch("engine.publish_log", new_callable=AsyncMock)
    async def test_llm_with_optional_produces(self, mock_log, mock_tools, mock_llm_func):
        """LLM executor with optional_produces"""
        skill = create_skill(
            name="TestLLM",
            executor="llm",
            produces={"summary"},
            optional_produces={"keywords", "sentiment"},
        )
        skill.prompt = "Analyze this"
        
        with patch("engine.create_model") as mock_create_model:
            # Create a mock model class
            mock_model_class = Mock()
            
            # Create a mock instance that will be returned by ainvoke
            mock_instance = Mock()
            mock_instance.summary = "test summary"
            mock_instance.keywords = ["test", "keywords"]
            mock_instance.sentiment = "positive"
            
            # Make the model class callable and return the instance
            mock_model_class.return_value = mock_instance
            mock_model_class._mock_result = {
                "summary": "test summary",
                "keywords": ["test", "keywords"],
                "sentiment": "positive",
            }
            
            mock_create_model.return_value = mock_model_class
            
            result = await _execute_skill_core(skill, {"text": "test"}, {})
            assert result["summary"] == "test summary"
            assert result["keywords"] == ["test", "keywords"]
            assert result["sentiment"] == "positive"
    
    @patch("engine._structured_llm", side_effect=mock_structured_llm)
    @patch("engine._run_agent_tools", return_value=(None, []))
    @patch("engine.publish_log", new_callable=AsyncMock)
    async def test_llm_optional_produces_none(self, mock_log, mock_tools, mock_llm_func):
        """LLM executor with optional_produces returning None"""
        skill = create_skill(
            name="TestLLM",
            executor="llm",
            produces={"summary"},
            optional_produces={"keywords"},
        )
        skill.prompt = "Summarize this"
        
        with patch("engine.create_model") as mock_create_model:
            mock_model_class = Mock()
            mock_instance = Mock()
            mock_instance.summary = "test summary"
            mock_instance.keywords = None  # Optional is None
            
            mock_model_class.return_value = mock_instance
            mock_model_class._mock_result = {
                "summary": "test summary",
                "keywords": None,
            }
            
            mock_create_model.return_value = mock_model_class
            
            result = await _execute_skill_core(skill, {"text": "test"}, {})
            assert result == {"summary": "test summary"}
            assert "keywords" not in result  # None values not included
    
    # ========================================================================
    # EDGE CASES & ERROR CONDITIONS
    # ========================================================================
    
    @patch("engine._execute_data_query", side_effect=mock_execute_data_query)
    @patch("engine.publish_log", new_callable=AsyncMock)
    async def test_non_dict_result_error(self, mock_log, mock_query):
        """Action executor should error if result is not a dict"""
        action_cfg = create_action_config(ActionType.DATA_QUERY, query="SELECT *")
        
        async def mock_returns_list(cfg, inputs):
            return [1, 2, 3]  # Not a dict!
        
        skill = create_skill(
            name="TestQuery",
            executor="action",
            produces={"result"},
            action=action_cfg,
        )
        
        with patch("engine._execute_data_query", side_effect=mock_returns_list):
            try:
                await _execute_skill_core(skill, {}, {})
                assert False, "Should have raised ValueError"
            except ValueError as e:
                assert "must return a dict" in str(e)
    
    @patch("engine._execute_data_query", side_effect=mock_execute_data_query)
    @patch("engine.publish_log", new_callable=AsyncMock)
    async def test_empty_produces_copies_all(self, mock_log, mock_query):
        """Empty produces should copy all result keys"""
        action_cfg = create_action_config(ActionType.DATA_QUERY, query="SELECT *")
        action_cfg._mock_result = {
            "key1": "value1",
            "key2": "value2",
            "key3": "value3",
        }
        
        skill = create_skill(
            name="TestQuery",
            executor="action",
            produces=set(),  # Empty produces
            action=action_cfg,
        )
        
        result = await _execute_skill_core(skill, {}, {})
        assert result == {
            "key1": "value1",
            "key2": "value2",
            "key3": "value3",
        }
    
    @patch("engine._execute_data_pipeline", side_effect=mock_execute_data_pipeline)
    @patch("engine.publish_log", new_callable=AsyncMock)
    async def test_optional_does_not_overwrite_required(self, mock_log, mock_pipeline):
        """Optional produces should never overwrite required produces"""
        action_cfg = create_action_config(ActionType.DATA_PIPELINE, steps=[])
        action_cfg._mock_result = {
            "output": "from_required",
        }
        
        skill = create_skill(
            name="TestPipeline",
            executor="action",
            produces={"output"},
            optional_produces={"output"},  # Same key in both!
            action=action_cfg,
        )
        
        result = await _execute_skill_core(skill, {}, {})
        # The required produces should be processed first, optional should skip
        assert result == {"output": "from_required"}


# ============================================================================
# TEST RUNNER
# ============================================================================

async def run_all_tests():
    """Run all tests and report results"""
    test_instance = TestOutputParsing()
    
    # Get all test methods
    test_methods = [
        method for method in dir(test_instance)
        if method.startswith("test_") and callable(getattr(test_instance, method))
    ]
    
    print(f"\n{'='*80}")
    print(f"Running {len(test_methods)} output parsing tests...")
    print(f"{'='*80}\n")
    
    passed = 0
    failed = 0
    errors = []
    
    for test_name in test_methods:
        test_method = getattr(test_instance, test_name)
        try:
            await test_method()
            print(f"[PASS] {test_name}")
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {test_name}: {e}")
            failed += 1
            errors.append((test_name, str(e)))
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"[ERROR] {test_name}: {e}")
            failed += 1
            errors.append((test_name, f"ERROR: {error_detail}"))
    
    print(f"\n{'='*80}")
    print(f"Results: {passed} passed, {failed} failed out of {len(test_methods)} tests")
    print(f"{'='*80}\n")
    
    if errors:
        print("Failed tests:")
        for test_name, error in errors:
            print(f"  - {test_name}: {error}")
        print()
    
    return passed, failed


if __name__ == "__main__":
    passed, failed = asyncio.run(run_all_tests())
    sys.exit(0 if failed == 0 else 1)
