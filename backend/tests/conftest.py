"""
Shared fixtures for RAG chatbot tests.
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

# Add backend to path for imports
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from vector_store import SearchResults


@pytest.fixture
def mock_search_results_success():
    """Create successful search results"""
    return SearchResults(
        documents=["This is sample content about Python programming."],
        metadata=[{"course_title": "Python Basics", "lesson_number": 1}],
        distances=[0.5]
    )


@pytest.fixture
def mock_search_results_multiple():
    """Create search results with multiple documents"""
    return SearchResults(
        documents=[
            "First document about machine learning.",
            "Second document about neural networks."
        ],
        metadata=[
            {"course_title": "ML Fundamentals", "lesson_number": 1},
            {"course_title": "ML Fundamentals", "lesson_number": 2}
        ],
        distances=[0.3, 0.4]
    )


@pytest.fixture
def mock_search_results_empty():
    """Create empty search results (no matches)"""
    return SearchResults(
        documents=[],
        metadata=[],
        distances=[]
    )


@pytest.fixture
def mock_search_results_error():
    """Create search results with an error"""
    return SearchResults(
        documents=[],
        metadata=[],
        distances=[],
        error="Search error: ChromaDB connection failed"
    )


@pytest.fixture
def mock_vector_store(mock_search_results_success):
    """Create a mock VectorStore with configurable behavior"""
    store = Mock()
    store.search.return_value = mock_search_results_success
    store._resolve_course_name.return_value = "Python Basics"
    store.get_course_link.return_value = "https://example.com/python"
    store.get_lesson_link.return_value = "https://example.com/python/lesson1"
    store.get_all_courses_metadata.return_value = [
        {
            "title": "Python Basics",
            "course_link": "https://example.com/python",
            "lessons": [
                {"lesson_number": 1, "lesson_title": "Introduction"},
                {"lesson_number": 2, "lesson_title": "Variables"}
            ]
        }
    ]
    return store


@pytest.fixture
def mock_anthropic_text_response():
    """Create a mock Anthropic API response for text-only response"""
    response = Mock()
    response.stop_reason = "end_turn"

    text_block = Mock()
    text_block.type = "text"
    text_block.text = "This is the AI response."

    response.content = [text_block]
    return response


@pytest.fixture
def mock_anthropic_tool_use_response():
    """Create a mock Anthropic API response with tool use"""
    response = Mock()
    response.stop_reason = "tool_use"

    tool_use_block = Mock()
    tool_use_block.type = "tool_use"
    tool_use_block.id = "tool_123"
    tool_use_block.name = "search_course_content"
    tool_use_block.input = {"query": "What is Python?"}

    response.content = [tool_use_block]
    return response


@pytest.fixture
def mock_anthropic_final_response():
    """Create a mock Anthropic API final response after tool execution"""
    response = Mock()
    response.stop_reason = "end_turn"

    text_block = Mock()
    text_block.type = "text"
    text_block.text = "Based on the search, Python is a programming language."

    response.content = [text_block]
    return response


@pytest.fixture
def mock_anthropic_empty_response():
    """Create a mock Anthropic API response with empty content"""
    response = Mock()
    response.stop_reason = "end_turn"
    response.content = []
    return response


@pytest.fixture
def mock_tool_manager():
    """Create a mock ToolManager"""
    manager = Mock()
    manager.get_tool_definitions.return_value = [
        {
            "name": "search_course_content",
            "description": "Search course materials",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            }
        }
    ]
    manager.execute_tool.return_value = "[Python Basics - Lesson 1]\nPython is a programming language."
    manager.get_last_sources.return_value = [{"text": "Python Basics - Lesson 1", "link": "https://example.com"}]
    manager.reset_sources.return_value = None
    return manager


@pytest.fixture
def mock_anthropic_outline_tool_use_response():
    """Create a mock Anthropic API response requesting get_course_outline tool"""
    response = Mock()
    response.stop_reason = "tool_use"

    tool_use_block = Mock()
    tool_use_block.type = "tool_use"
    tool_use_block.id = "tool_outline_123"
    tool_use_block.name = "get_course_outline"
    tool_use_block.input = {"course_title": "Python Basics"}

    response.content = [tool_use_block]
    return response


@pytest.fixture
def mock_anthropic_second_tool_use_response():
    """Create a mock Anthropic API response requesting a second tool (search after outline)"""
    response = Mock()
    response.stop_reason = "tool_use"

    tool_use_block = Mock()
    tool_use_block.type = "tool_use"
    tool_use_block.id = "tool_search_456"
    tool_use_block.name = "search_course_content"
    tool_use_block.input = {"query": "Introduction to Python"}

    response.content = [tool_use_block]
    return response


@pytest.fixture
def mock_tool_manager_sequential():
    """Create a mock ToolManager that returns different results for different tools"""
    manager = Mock()
    manager.get_tool_definitions.return_value = [
        {
            "name": "get_course_outline",
            "description": "Get the outline of a course",
            "input_schema": {
                "type": "object",
                "properties": {
                    "course_title": {"type": "string"}
                },
                "required": ["course_title"]
            }
        },
        {
            "name": "search_course_content",
            "description": "Search course materials",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            }
        }
    ]

    def execute_tool_side_effect(tool_name, **kwargs):
        if tool_name == "get_course_outline":
            return "Course: Python Basics\nLesson 1: Introduction to Python\nLesson 2: Variables and Data Types"
        elif tool_name == "search_course_content":
            return "[ML Course - Lesson 2]\nPython is widely used in machine learning..."
        return "Unknown tool"

    manager.execute_tool.side_effect = execute_tool_side_effect
    manager.get_last_sources.return_value = [{"text": "Course content", "link": "https://example.com"}]
    manager.reset_sources.return_value = None
    return manager
