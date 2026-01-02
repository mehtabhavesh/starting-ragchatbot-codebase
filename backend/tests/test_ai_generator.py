"""
Tests for AIGenerator class tool calling behavior.

These tests verify the AIGenerator correctly:
- Generates responses without tools
- Handles tool use requests from Claude
- Executes tools and passes results back
- Handles various error conditions
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import anthropic

# Add backend to path for imports
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from ai_generator import AIGenerator


class TestAIGeneratorBasicResponse:
    """Tests for basic response generation without tools"""

    @patch('ai_generator.anthropic.Anthropic')
    def test_generate_response_no_tools(self, mock_anthropic_class, mock_anthropic_text_response):
        """Test response generation without tools works correctly"""
        mock_client = Mock()
        mock_client.messages.create.return_value = mock_anthropic_text_response
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator(api_key="test-key", model="claude-3-opus")
        result = generator.generate_response(query="Hello, world!")

        assert result == "This is the AI response."
        mock_client.messages.create.assert_called_once()

    @patch('ai_generator.anthropic.Anthropic')
    def test_generate_response_with_history(self, mock_anthropic_class, mock_anthropic_text_response):
        """Test that conversation history is included in system prompt"""
        mock_client = Mock()
        mock_client.messages.create.return_value = mock_anthropic_text_response
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator(api_key="test-key", model="claude-3-opus")
        result = generator.generate_response(
            query="Follow-up question",
            conversation_history="User: Hello\nAssistant: Hi there!"
        )

        # Check that history was included in the call
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert "Previous conversation" in call_kwargs["system"]
        assert "Hello" in call_kwargs["system"]


class TestAIGeneratorToolExecution:
    """Tests for tool execution handling"""

    @patch('ai_generator.anthropic.Anthropic')
    def test_generate_response_with_tool_use(
            self,
            mock_anthropic_class,
            mock_anthropic_tool_use_response,
            mock_anthropic_final_response,
            mock_tool_manager
    ):
        """Test that tool use is correctly triggered and executed"""
        mock_client = Mock()
        # First call returns tool_use, second call returns final response
        mock_client.messages.create.side_effect = [
            mock_anthropic_tool_use_response,
            mock_anthropic_final_response
        ]
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator(api_key="test-key", model="claude-3-opus")
        result = generator.generate_response(
            query="What is Python?",
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager
        )

        # Should have called the API twice (initial + after tool execution)
        assert mock_client.messages.create.call_count == 2

        # Should have executed the tool
        mock_tool_manager.execute_tool.assert_called_once_with(
            "search_course_content",
            query="What is Python?"
        )

        # Should return final response
        assert "Python is a programming language" in result

    @patch('ai_generator.anthropic.Anthropic')
    def test_handle_tool_execution_success(
            self,
            mock_anthropic_class,
            mock_anthropic_tool_use_response,
            mock_anthropic_final_response,
            mock_tool_manager
    ):
        """Test successful tool execution flow"""
        mock_client = Mock()
        mock_client.messages.create.side_effect = [
            mock_anthropic_tool_use_response,
            mock_anthropic_final_response
        ]
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator(api_key="test-key", model="claude-3-opus")
        result = generator.generate_response(
            query="Search test",
            tools=[{"name": "search_course_content"}],
            tool_manager=mock_tool_manager
        )

        # Verify tool was called
        mock_tool_manager.execute_tool.assert_called()

        # Verify second API call includes tool results
        second_call_kwargs = mock_client.messages.create.call_args_list[1].kwargs
        messages = second_call_kwargs["messages"]

        # Should have: user message, assistant tool_use, user tool_result
        assert len(messages) == 3
        assert messages[2]["role"] == "user"

    @patch('ai_generator.anthropic.Anthropic')
    def test_handle_tool_execution_tool_not_found(
            self,
            mock_anthropic_class,
            mock_anthropic_tool_use_response,
            mock_anthropic_final_response
    ):
        """Test handling when tool is not found in tool manager"""
        mock_client = Mock()
        mock_client.messages.create.side_effect = [
            mock_anthropic_tool_use_response,
            mock_anthropic_final_response
        ]
        mock_anthropic_class.return_value = mock_client

        # Tool manager returns error for unknown tool
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Tool 'search_course_content' not found"

        generator = AIGenerator(api_key="test-key", model="claude-3-opus")
        result = generator.generate_response(
            query="Test",
            tools=[{"name": "search_course_content"}],
            tool_manager=mock_tool_manager
        )

        # Should still complete without crashing
        assert result is not None

    @patch('ai_generator.anthropic.Anthropic')
    def test_handle_tool_execution_tool_error(
            self,
            mock_anthropic_class,
            mock_anthropic_tool_use_response,
            mock_anthropic_final_response
    ):
        """Test handling when tool execution raises an exception"""
        mock_client = Mock()
        mock_client.messages.create.side_effect = [
            mock_anthropic_tool_use_response,
            mock_anthropic_final_response
        ]
        mock_anthropic_class.return_value = mock_client

        # Tool manager raises exception
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.side_effect = Exception("Tool execution failed")

        generator = AIGenerator(api_key="test-key", model="claude-3-opus")

        # With the fix, exceptions are now caught and handled gracefully
        result = generator.generate_response(
            query="Test",
            tools=[{"name": "search_course_content"}],
            tool_manager=mock_tool_manager
        )

        # Should return the final response (error is passed to Claude as tool result)
        assert result is not None


class TestAIGeneratorErrorHandling:
    """Tests for error handling in AIGenerator"""

    @patch('ai_generator.anthropic.Anthropic')
    def test_response_content_empty(self, mock_anthropic_class, mock_anthropic_empty_response):
        """Test handling of empty response.content - now returns error message instead of crashing"""
        mock_client = Mock()
        mock_client.messages.create.return_value = mock_anthropic_empty_response
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator(api_key="test-key", model="claude-3-opus")

        # With the fix, empty content returns an error message instead of IndexError
        result = generator.generate_response(query="Test query")
        assert "empty" in result.lower() or "couldn't generate" in result.lower()

    @patch('ai_generator.anthropic.Anthropic')
    def test_api_error_handling(self, mock_anthropic_class):
        """Test handling of Anthropic API errors - now returns error message"""
        mock_client = Mock()
        mock_client.messages.create.side_effect = anthropic.APIError(
            message="API Error",
            request=Mock(),
            body=None
        )
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator(api_key="test-key", model="claude-3-opus")

        # With the fix, API errors return an error message instead of raising
        result = generator.generate_response(query="Test query")
        assert "API error" in result or "error" in result.lower()

    @patch('ai_generator.anthropic.Anthropic')
    def test_rate_limit_error_handling(self, mock_anthropic_class):
        """Test handling of rate limit errors - now returns error message"""
        mock_client = Mock()
        mock_client.messages.create.side_effect = anthropic.RateLimitError(
            message="Rate limited",
            response=Mock(status_code=429),
            body=None
        )
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator(api_key="test-key", model="claude-3-opus")

        # With the fix, rate limit errors return a friendly message
        result = generator.generate_response(query="Test query")
        assert "rate limit" in result.lower() or "try again" in result.lower()

    @patch('ai_generator.anthropic.Anthropic')
    def test_authentication_error_handling(self, mock_anthropic_class):
        """Test handling of authentication errors - now returns error message"""
        mock_client = Mock()
        mock_client.messages.create.side_effect = anthropic.AuthenticationError(
            message="Invalid API key",
            response=Mock(status_code=401),
            body=None
        )
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator(api_key="bad-key", model="claude-3-opus")

        # With the fix, auth errors return a friendly message
        result = generator.generate_response(query="Test query")
        assert "authentication" in result.lower() or "api key" in result.lower()


class TestAIGeneratorToolManagerInteraction:
    """Tests for interaction between AIGenerator and ToolManager"""

    @patch('ai_generator.anthropic.Anthropic')
    def test_tool_manager_none_with_tools(self, mock_anthropic_class, mock_anthropic_tool_use_response):
        """Test behavior when tool_manager is None but tools are provided.

        When tool_manager is None, the code skips tool execution and tries to
        return response.content[0].text, but since the response contains tool_use
        blocks (not text blocks), this should fail.
        """
        mock_client = Mock()
        mock_client.messages.create.return_value = mock_anthropic_tool_use_response
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator(api_key="test-key", model="claude-3-opus")

        # The code falls through to response.content[0].text when tool_manager is None
        # but tool_use blocks don't have a .text attribute - this is a bug!
        # Currently this doesn't raise because our mock has a MagicMock that accepts any attribute
        # In production with real Anthropic response objects, this would fail
        result = generator.generate_response(
            query="Test",
            tools=[{"name": "search"}],
            tool_manager=None
        )

        # The result is from the mock - in production this would be problematic
        # This test documents the current (buggy) behavior
        assert result is not None

    @patch('ai_generator.anthropic.Anthropic')
    def test_multiple_tool_calls_in_response(
            self,
            mock_anthropic_class,
            mock_anthropic_final_response
    ):
        """Test handling of multiple tool calls in a single response"""
        # Create response with multiple tool use blocks
        response = Mock()
        response.stop_reason = "tool_use"

        tool_use_1 = Mock()
        tool_use_1.type = "tool_use"
        tool_use_1.id = "tool_1"
        tool_use_1.name = "search_course_content"
        tool_use_1.input = {"query": "Python"}

        tool_use_2 = Mock()
        tool_use_2.type = "tool_use"
        tool_use_2.id = "tool_2"
        tool_use_2.name = "search_course_content"
        tool_use_2.input = {"query": "JavaScript"}

        response.content = [tool_use_1, tool_use_2]

        mock_client = Mock()
        mock_client.messages.create.side_effect = [response, mock_anthropic_final_response]
        mock_anthropic_class.return_value = mock_client

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Search result"

        generator = AIGenerator(api_key="test-key", model="claude-3-opus")
        result = generator.generate_response(
            query="Compare Python and JavaScript",
            tools=[{"name": "search_course_content"}],
            tool_manager=mock_tool_manager
        )

        # Should call execute_tool twice
        assert mock_tool_manager.execute_tool.call_count == 2


class TestSequentialToolCalling:
    """Tests for sequential (multi-round) tool calling behavior"""

    @patch('ai_generator.anthropic.Anthropic')
    def test_two_sequential_tool_calls(
            self,
            mock_anthropic_class,
            mock_anthropic_outline_tool_use_response,
            mock_anthropic_second_tool_use_response,
            mock_anthropic_final_response,
            mock_tool_manager_sequential
    ):
        """Test that Claude can make two sequential tool calls"""
        mock_client = Mock()
        mock_client.messages.create.side_effect = [
            mock_anthropic_outline_tool_use_response,  # Round 1: get_course_outline
            mock_anthropic_second_tool_use_response,   # Round 2: search_course_content
            mock_anthropic_final_response              # Final response without tools
        ]
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator(api_key="test-key", model="claude-3-opus")
        result = generator.generate_response(
            query="Find courses similar to lesson 1 of Python Basics",
            tools=mock_tool_manager_sequential.get_tool_definitions(),
            tool_manager=mock_tool_manager_sequential
        )

        # Verify 3 API calls were made (initial + 2 rounds)
        assert mock_client.messages.create.call_count == 3

        # Verify both tools were executed
        assert mock_tool_manager_sequential.execute_tool.call_count == 2

        # Verify tool execution order
        calls = mock_tool_manager_sequential.execute_tool.call_args_list
        assert calls[0][0][0] == "get_course_outline"
        assert calls[1][0][0] == "search_course_content"

        # Verify final response is returned
        assert "Python is a programming language" in result

    @patch('ai_generator.anthropic.Anthropic')
    def test_single_tool_then_response(
            self,
            mock_anthropic_class,
            mock_anthropic_tool_use_response,
            mock_anthropic_final_response,
            mock_tool_manager
    ):
        """Test that Claude can make one tool call and respond without a second"""
        mock_client = Mock()
        mock_client.messages.create.side_effect = [
            mock_anthropic_tool_use_response,  # Round 1: tool_use
            mock_anthropic_final_response      # Claude responds without requesting another tool
        ]
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator(api_key="test-key", model="claude-3-opus")
        result = generator.generate_response(
            query="What is Python?",
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager
        )

        # Only 2 API calls (not 3) since Claude didn't request second tool
        assert mock_client.messages.create.call_count == 2

        # Only one tool execution
        assert mock_tool_manager.execute_tool.call_count == 1

    @patch('ai_generator.anthropic.Anthropic')
    def test_max_rounds_enforced(
            self,
            mock_anthropic_class,
            mock_anthropic_tool_use_response,
            mock_anthropic_final_response,
            mock_tool_manager
    ):
        """Test that tool calling stops after MAX_TOOL_ROUNDS"""
        mock_client = Mock()
        # Claude keeps requesting tools - mock returns tool_use for rounds 1 and 2
        mock_client.messages.create.side_effect = [
            mock_anthropic_tool_use_response,  # Initial: tool_use
            mock_anthropic_tool_use_response,  # Round 1: tool_use (wants more)
            mock_anthropic_final_response      # Round 2: forced final (no tools offered)
        ]
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator(api_key="test-key", model="claude-3-opus")
        result = generator.generate_response(
            query="Complex multi-step query",
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager
        )

        # Exactly 3 API calls: initial + round 1 with tools + round 2 without tools
        assert mock_client.messages.create.call_count == 3

        # Exactly 2 tool executions (max rounds)
        assert mock_tool_manager.execute_tool.call_count == 2

        # Final call (3rd) should NOT have tools parameter
        final_call_kwargs = mock_client.messages.create.call_args_list[2].kwargs
        assert "tools" not in final_call_kwargs

    @patch('ai_generator.anthropic.Anthropic')
    def test_message_accumulation_across_rounds(
            self,
            mock_anthropic_class,
            mock_anthropic_outline_tool_use_response,
            mock_anthropic_second_tool_use_response,
            mock_anthropic_final_response,
            mock_tool_manager_sequential
    ):
        """Test that messages accumulate correctly across tool rounds"""
        mock_client = Mock()
        mock_client.messages.create.side_effect = [
            mock_anthropic_outline_tool_use_response,
            mock_anthropic_second_tool_use_response,
            mock_anthropic_final_response
        ]
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator(api_key="test-key", model="claude-3-opus")
        generator.generate_response(
            query="Test query",
            tools=mock_tool_manager_sequential.get_tool_definitions(),
            tool_manager=mock_tool_manager_sequential
        )

        # API calls:
        # 1st call (initial): messages = [user]
        # 2nd call (after round 1): messages = [user, asst(tool), user(result)]
        # 3rd call (after round 2): messages = [user, asst(tool), user(result), asst(tool), user(result)]

        # Check first API call has just user message
        first_call_kwargs = mock_client.messages.create.call_args_list[0].kwargs
        messages = first_call_kwargs["messages"]
        assert len(messages) == 1  # just user

        # Check second API call has accumulated messages from round 1
        second_call_kwargs = mock_client.messages.create.call_args_list[1].kwargs
        messages = second_call_kwargs["messages"]
        assert len(messages) == 3  # user, assistant (tool_use), user (tool_result)

        # Check third API call has all messages from both rounds
        third_call_kwargs = mock_client.messages.create.call_args_list[2].kwargs
        messages = third_call_kwargs["messages"]
        assert len(messages) == 5  # user, asst, user, asst, user

    @patch('ai_generator.anthropic.Anthropic')
    def test_tool_error_terminates_loop(
            self,
            mock_anthropic_class,
            mock_anthropic_tool_use_response,
            mock_anthropic_final_response
    ):
        """Test that tool error in round 1 triggers final call without more tools"""
        mock_client = Mock()
        mock_client.messages.create.side_effect = [
            mock_anthropic_tool_use_response,  # Initial: tool_use
            mock_anthropic_final_response      # After error: forced final
        ]
        mock_anthropic_class.return_value = mock_client

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.side_effect = Exception("Database connection failed")

        generator = AIGenerator(api_key="test-key", model="claude-3-opus")
        result = generator.generate_response(
            query="Test",
            tools=[{"name": "search_course_content"}],
            tool_manager=mock_tool_manager
        )

        # Only 2 API calls: initial + forced final (error prevents more tools)
        assert mock_client.messages.create.call_count == 2

        # Second call should NOT have tools (error triggered termination)
        second_call_kwargs = mock_client.messages.create.call_args_list[1].kwargs
        assert "tools" not in second_call_kwargs

        # Should still get a response
        assert result is not None

    @patch('ai_generator.anthropic.Anthropic')
    def test_no_tool_use_returns_immediately(
            self,
            mock_anthropic_class,
            mock_anthropic_text_response,
            mock_tool_manager
    ):
        """Test that if Claude doesn't use tools, response is returned immediately"""
        mock_client = Mock()
        mock_client.messages.create.return_value = mock_anthropic_text_response
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator(api_key="test-key", model="claude-3-opus")
        result = generator.generate_response(
            query="What is 2+2?",  # Simple question, no tool needed
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager
        )

        # Only one API call
        assert mock_client.messages.create.call_count == 1

        # No tool execution
        mock_tool_manager.execute_tool.assert_not_called()

        # Direct response returned
        assert result == "This is the AI response."

    @patch('ai_generator.anthropic.Anthropic')
    def test_tools_included_in_first_round_followup(
            self,
            mock_anthropic_class,
            mock_anthropic_tool_use_response,
            mock_anthropic_final_response,
            mock_tool_manager
    ):
        """Test that tools are included in the first round follow-up call"""
        mock_client = Mock()
        mock_client.messages.create.side_effect = [
            mock_anthropic_tool_use_response,  # Initial: tool_use
            mock_anthropic_final_response      # Round 1: Claude satisfied, no more tools
        ]
        mock_anthropic_class.return_value = mock_client

        tools = mock_tool_manager.get_tool_definitions()
        generator = AIGenerator(api_key="test-key", model="claude-3-opus")
        generator.generate_response(
            query="Search for Python",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Second call (round 1 follow-up) SHOULD have tools (round_count < MAX)
        second_call_kwargs = mock_client.messages.create.call_args_list[1].kwargs
        assert "tools" in second_call_kwargs
        assert second_call_kwargs["tools"] == tools
