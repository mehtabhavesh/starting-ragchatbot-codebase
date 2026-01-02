import anthropic
from typing import List, Optional, Dict, Any

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    # Maximum number of sequential tool-calling rounds per query
    MAX_TOOL_ROUNDS = 2

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to search and outline tools for course information.

Search Tool Usage:
- Use the search tool for questions about specific course content or detailed educational materials
- You may use tools sequentially (up to 2 calls) when needed to gather complete information
- For multi-step queries, use one tool to get initial information, then another based on results
- Synthesize search results into accurate, fact-based responses
- If search yields no results, state this clearly without offering alternatives

Course Outline Tool Usage:
- Use the course outline tool when users ask for:
  - Course structure or outline
  - List of lessons in a course
  - What topics a course covers
  - Course overview or table of contents
- Present the course title, link, and lesson list with numbers and titles
- You can combine outline and search tools for complex queries
  (e.g., get outline first, then search for specific lesson content)

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without searching
- **Course-specific questions**: Search first, then answer
- **Course outline requests**: Use the outline tool, then present the course title, link, and lesson list with numbers and titles
- **Complex questions requiring multiple sources**: Use tools sequentially to gather all needed information
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, search explanations, or question-type analysis
 - Do not mention "based on the search results"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""
    
    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        
        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string, or error message on failure
        """

        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        # Prepare API call parameters efficiently
        api_params = {
            **self.base_params,
            "messages": [{"role": "user", "content": query}],
            "system": system_content
        }

        # Add tools if available
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}

        try:
            # Get response from Claude
            response = self.client.messages.create(**api_params)

            # Handle tool execution if needed
            if response.stop_reason == "tool_use" and tool_manager:
                return self._handle_tool_execution(response, api_params, tool_manager, tools)

            # Return direct response with content validation
            return self._extract_text_response(response)

        except anthropic.AuthenticationError as e:
            return f"Authentication error: Please check your API key configuration."
        except anthropic.RateLimitError as e:
            return f"Rate limit exceeded. Please try again in a moment."
        except anthropic.APIError as e:
            return f"API error occurred: {str(e)}"
        except Exception as e:
            return f"An unexpected error occurred: {str(e)}"

    def _extract_text_response(self, response) -> str:
        """
        Extract text from API response with validation.

        Args:
            response: Anthropic API response object

        Returns:
            Text content from response, or fallback message if not found
        """
        if response.content and len(response.content) > 0:
            for block in response.content:
                if hasattr(block, 'text'):
                    return block.text
            return "I received your request but couldn't generate a text response."
        return "I received your request but the response was empty."

    def _handle_tool_execution(
        self,
        initial_response,
        base_params: Dict[str, Any],
        tool_manager,
        tools: Optional[List] = None
    ) -> str:
        """
        Handle execution of tool calls with support for sequential rounds.

        Supports up to MAX_TOOL_ROUNDS sequential tool calls, where Claude can
        request a tool, see results, and optionally request another tool.

        Args:
            initial_response: The response containing tool use requests
            base_params: Base API parameters (includes messages and system)
            tool_manager: Manager to execute tools
            tools: Tool definitions for subsequent API calls

        Returns:
            Final response text after all tool rounds complete
        """
        messages = base_params["messages"].copy()
        current_response = initial_response
        round_count = 0

        while round_count < self.MAX_TOOL_ROUNDS:
            round_count += 1

            # Add Claude's tool-use response to messages
            messages.append({"role": "assistant", "content": current_response.content})

            # Execute all tool calls from this response and collect results
            tool_results = []
            tool_error_occurred = False

            for content_block in current_response.content:
                if content_block.type == "tool_use":
                    try:
                        tool_result = tool_manager.execute_tool(
                            content_block.name,
                            **content_block.input
                        )
                    except Exception as e:
                        tool_result = f"Tool execution error: {str(e)}"
                        tool_error_occurred = True

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": content_block.id,
                        "content": tool_result
                    })

            # Add tool results as user message
            if tool_results:
                messages.append({"role": "user", "content": tool_results})

            # Determine if more tools should be allowed
            # Allow more tools if: not at max rounds AND no critical errors
            allow_more_tools = (round_count < self.MAX_TOOL_ROUNDS) and not tool_error_occurred

            # Build API params for next call
            next_params = {
                **self.base_params,
                "messages": list(messages),  # Copy to preserve state for this call
                "system": base_params["system"]
            }

            if allow_more_tools and tools:
                next_params["tools"] = tools
                next_params["tool_choice"] = {"type": "auto"}
            # else: no tools parameter, forcing Claude to generate final answer

            # Make the API call
            try:
                current_response = self.client.messages.create(**next_params)
            except anthropic.APIError as e:
                return f"API error during tool round {round_count}: {str(e)}"
            except Exception as e:
                return f"Error in tool round {round_count}: {str(e)}"

            # Check if Claude wants more tools
            if current_response.stop_reason != "tool_use":
                # Claude is done with tools, exit loop
                break

        # Extract and return final text response
        return self._extract_text_response(current_response)