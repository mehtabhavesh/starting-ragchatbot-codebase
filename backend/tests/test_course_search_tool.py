"""
Tests for CourseSearchTool.execute() method.

These tests verify the CourseSearchTool correctly:
- Executes basic queries
- Handles course and lesson filters
- Handles empty results
- Handles vector store errors
- Properly formats results and tracks sources
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock

# Add backend to path for imports
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from search_tools import CourseSearchTool
from vector_store import SearchResults


class TestCourseSearchToolExecute:
    """Tests for the execute method of CourseSearchTool"""

    def test_execute_basic_query(self, mock_vector_store, mock_search_results_success):
        """Test basic query execution returns formatted results"""
        mock_vector_store.search.return_value = mock_search_results_success

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="What is Python?")

        # Should call search with correct parameters
        mock_vector_store.search.assert_called_once_with(
            query="What is Python?",
            course_name=None,
            lesson_number=None
        )

        # Should return formatted content
        assert "Python Basics" in result
        assert "Lesson 1" in result
        assert "sample content about Python" in result

    def test_execute_with_course_filter(self, mock_vector_store, mock_search_results_success):
        """Test query with course_name filter"""
        mock_vector_store.search.return_value = mock_search_results_success

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="variables", course_name="Python Basics")

        mock_vector_store.search.assert_called_once_with(
            query="variables",
            course_name="Python Basics",
            lesson_number=None
        )
        assert result is not None

    def test_execute_with_lesson_filter(self, mock_vector_store, mock_search_results_success):
        """Test query with lesson_number filter"""
        mock_vector_store.search.return_value = mock_search_results_success

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="intro", lesson_number=1)

        mock_vector_store.search.assert_called_once_with(
            query="intro",
            course_name=None,
            lesson_number=1
        )
        assert result is not None

    def test_execute_with_both_filters(self, mock_vector_store, mock_search_results_success):
        """Test query with both course and lesson filters"""
        mock_vector_store.search.return_value = mock_search_results_success

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="functions", course_name="Python", lesson_number=3)

        mock_vector_store.search.assert_called_once_with(
            query="functions",
            course_name="Python",
            lesson_number=3
        )
        assert result is not None

    def test_execute_no_results(self, mock_vector_store, mock_search_results_empty):
        """Test query with no matching results returns friendly message"""
        mock_vector_store.search.return_value = mock_search_results_empty

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="nonexistent topic")

        assert "No relevant content found" in result

    def test_execute_no_results_with_course_filter(self, mock_vector_store, mock_search_results_empty):
        """Test no results message includes course filter context"""
        mock_vector_store.search.return_value = mock_search_results_empty

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="xyz", course_name="Python Basics")

        assert "No relevant content found" in result
        assert "Python Basics" in result

    def test_execute_no_results_with_lesson_filter(self, mock_vector_store, mock_search_results_empty):
        """Test no results message includes lesson filter context"""
        mock_vector_store.search.return_value = mock_search_results_empty

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="xyz", lesson_number=5)

        assert "No relevant content found" in result
        assert "lesson 5" in result

    def test_execute_vector_store_error(self, mock_vector_store, mock_search_results_error):
        """Test that vector store errors are properly returned"""
        mock_vector_store.search.return_value = mock_search_results_error

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="test query")

        # Should return the error message
        assert "Search error" in result
        assert "ChromaDB" in result

    def test_execute_course_not_found(self, mock_vector_store):
        """Test error when course name doesn't resolve"""
        # Create results with course not found error
        not_found_results = SearchResults(
            documents=[],
            metadata=[],
            distances=[],
            error="No course found matching 'NonExistent Course'"
        )
        mock_vector_store.search.return_value = not_found_results

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="test", course_name="NonExistent Course")

        assert "No course found" in result or "error" in result.lower()


class TestCourseSearchToolFormatResults:
    """Tests for result formatting and source tracking"""

    def test_format_results_with_sources(self, mock_vector_store, mock_search_results_success):
        """Test that sources are properly tracked in last_sources"""
        mock_vector_store.search.return_value = mock_search_results_success

        tool = CourseSearchTool(mock_vector_store)
        tool.execute(query="Python")

        # Should have populated last_sources
        assert len(tool.last_sources) > 0
        assert "text" in tool.last_sources[0]
        assert "link" in tool.last_sources[0]

    def test_format_results_multiple_documents(self, mock_vector_store, mock_search_results_multiple):
        """Test formatting with multiple search results"""
        mock_vector_store.search.return_value = mock_search_results_multiple

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="machine learning")

        # Should contain content from multiple documents
        assert "machine learning" in result or "neural networks" in result

        # Should have multiple sources
        assert len(tool.last_sources) == 2

    def test_format_results_with_missing_metadata(self, mock_vector_store):
        """Test handling of results with missing metadata fields"""
        # Create results with incomplete metadata
        incomplete_results = SearchResults(
            documents=["Some content"],
            metadata=[{"course_title": "Test Course"}],  # Missing lesson_number
            distances=[0.5]
        )
        mock_vector_store.search.return_value = incomplete_results
        mock_vector_store.get_lesson_link.return_value = None  # No lesson link

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="test")

        # Should still format without crashing
        assert "Test Course" in result
        # Should not include "Lesson None"
        assert "Lesson None" not in result

    def test_last_sources_reset_between_calls(self, mock_vector_store, mock_search_results_success):
        """Test that last_sources is updated (not appended) on each call"""
        mock_vector_store.search.return_value = mock_search_results_success

        tool = CourseSearchTool(mock_vector_store)

        # First call
        tool.execute(query="first query")
        first_sources = tool.last_sources.copy()

        # Second call
        tool.execute(query="second query")
        second_sources = tool.last_sources

        # Sources should be from the second call only
        assert len(second_sources) == len(first_sources)


class TestCourseSearchToolEdgeCases:
    """Tests for edge cases and error conditions"""

    def test_execute_with_empty_query(self, mock_vector_store, mock_search_results_success):
        """Test behavior with empty query string"""
        mock_vector_store.search.return_value = mock_search_results_success

        tool = CourseSearchTool(mock_vector_store)
        # Should not crash with empty query
        result = tool.execute(query="")

        # Should still call search
        mock_vector_store.search.assert_called_once()

    def test_execute_vector_store_raises_exception(self, mock_vector_store):
        """Test that unhandled exceptions from vector store propagate.

        Note: This tests the CourseSearchTool directly, not through ToolManager.
        When called through ToolManager, exceptions are caught there.
        """
        mock_vector_store.search.side_effect = Exception("Unexpected database error")

        tool = CourseSearchTool(mock_vector_store)

        # CourseSearchTool itself doesn't catch exceptions - it relies on
        # VectorStore.search() to catch internally and return SearchResults.error
        # If an unexpected exception occurs, it propagates
        with pytest.raises(Exception) as exc_info:
            tool.execute(query="test")

        assert "Unexpected database error" in str(exc_info.value)

    def test_get_tool_definition_structure(self, mock_vector_store):
        """Test that tool definition has correct structure for Anthropic API"""
        tool = CourseSearchTool(mock_vector_store)
        definition = tool.get_tool_definition()

        assert "name" in definition
        assert "description" in definition
        assert "input_schema" in definition
        assert definition["name"] == "search_course_content"

        # Check schema structure
        schema = definition["input_schema"]
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "query" in schema["properties"]
        assert "required" in schema
        assert "query" in schema["required"]
