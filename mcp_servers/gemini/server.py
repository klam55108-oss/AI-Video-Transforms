"""
Gemini CLI MCP Server for Claude Code.

Provides 6 tools:
- gemini_query: General queries
- gemini_code: Code generation
- gemini_analyze: Content analysis
- gemini_chat: Multi-turn conversation
- gemini_chat_clear: Clear session
- gemini_list_sessions: List active sessions
"""

from fastmcp import FastMCP

from .client import get_client
from .session_manager import get_session_manager

mcp = FastMCP(name="gemini-cli")


@mcp.tool
async def gemini_query(
    prompt: str,
    model: str | None = None,
    timeout_seconds: float = 120.0,
) -> str:
    """
    Send a general query to Gemini and get a response.

    Use this tool for one-off questions, explanations, or any general
    purpose interaction with Gemini.

    Args:
        prompt: The question or prompt to send to Gemini.
        model: Optional Gemini model name (e.g., 'gemini-2.0-flash').
               Defaults to the CLI's default model.
        timeout_seconds: Maximum time to wait for response (default 120s).

    Returns:
        Gemini's response text, or an error message if the request failed.
    """
    if not prompt or not prompt.strip():
        return "Error: prompt is required"

    client = get_client()
    response = await client.query(prompt, model=model, timeout=timeout_seconds)

    if response.success:
        return response.output
    return f"**Error:** {response.error}"


@mcp.tool
async def gemini_code(
    request: str,
    language: str | None = None,
    context: str | None = None,
    timeout_seconds: float = 180.0,
) -> str:
    """
    Generate code using Gemini.

    Use this tool when you need code generation, code review,
    or code-related assistance from Gemini.

    Args:
        request: Description of the code you need or the coding task.
        language: Optional programming language hint (e.g., 'python', 'javascript').
        context: Optional additional context about the codebase or requirements.
        timeout_seconds: Maximum time to wait for response (default 180s).

    Returns:
        Generated code with explanations, or an error message.
    """
    prompt_parts = [f"Generate code for: {request}"]
    if language:
        prompt_parts.append(f"Programming language: {language}")
    if context:
        prompt_parts.append(f"Context: {context}")
    prompt_parts.append("Provide production-quality code with explanations.")

    full_prompt = "\n\n".join(prompt_parts)
    client = get_client()
    response = await client.query(full_prompt, timeout=timeout_seconds)

    if response.success:
        return response.output
    return f"**Error:** {response.error}"


@mcp.tool
async def gemini_analyze(
    content: str,
    analysis_type: str | None = None,
    focus_areas: str | None = None,
    timeout_seconds: float = 180.0,
) -> str:
    """
    Analyze content using Gemini.

    Use this tool for code review, document analysis, data analysis,
    or any content that needs detailed examination.

    Args:
        content: The content to analyze (code, text, data, etc.).
        analysis_type: Type of analysis to perform.
                      Options: 'code_review', 'security', 'performance',
                              'documentation', 'general'.
        focus_areas: Specific aspects to focus on (comma-separated).
        timeout_seconds: Maximum time to wait for response (default 180s).

    Returns:
        Analysis results and recommendations, or an error message.
    """
    prompt_parts = [f"Analyze the following content:\n\n{content}"]
    if analysis_type:
        prompt_parts.append(f"Analysis type: {analysis_type}")
    if focus_areas:
        prompt_parts.append(f"Focus on: {focus_areas}")
    prompt_parts.append("Provide detailed findings and recommendations.")

    full_prompt = "\n\n".join(prompt_parts)
    client = get_client()
    response = await client.query(full_prompt, timeout=timeout_seconds)

    if response.success:
        return response.output
    return f"**Error:** {response.error}"


@mcp.tool
async def gemini_chat(
    message: str,
    session_id: str | None = None,
    timeout_seconds: float = 120.0,
) -> str:
    """
    Have a multi-turn conversation with Gemini.

    Use this tool when you need to have an ongoing conversation
    that maintains context across multiple exchanges.

    Args:
        message: Your message to Gemini.
        session_id: Optional session ID to continue an existing conversation.
                   If not provided or not found, a new session is created.
        timeout_seconds: Maximum time to wait for response (default 120s).

    Returns:
        Gemini's response and the session ID for continuation.
        Format: "Session: {id}\n\n{response}"
    """
    manager = get_session_manager()
    session = manager.get_or_create(session_id)

    prompt = session.build_prompt(message)
    client = get_client()
    response = await client.query(prompt, timeout=timeout_seconds)

    if response.success:
        session.add_turn("user", message)
        session.add_turn("assistant", response.output)
        return f"Session: {session.session_id}\n\n{response.output}"
    return f"Session: {session.session_id}\n\n**Error:** {response.error}"


@mcp.tool
async def gemini_chat_clear(session_id: str) -> str:
    """
    Clear a chat session and its conversation history.

    Use this tool to end a conversation and free up resources.

    Args:
        session_id: The session ID to clear.

    Returns:
        Confirmation message indicating whether the session was cleared.
    """
    manager = get_session_manager()
    if manager.clear(session_id):
        return f"Session '{session_id}' cleared successfully."
    return f"Session '{session_id}' not found."


@mcp.tool
async def gemini_list_sessions() -> str:
    """
    List all active chat sessions.

    Use this tool to see what conversations are currently active
    and their metadata.

    Returns:
        A formatted list of active sessions with their details.
    """
    manager = get_session_manager()
    sessions = manager.list_all()

    if not sessions:
        return "No active sessions."

    lines = ["Active sessions:"]
    for s in sessions:
        lines.append(f"  - {s['id']}: {s['turns']} turns")
    return "\n".join(lines)


# Entry point for CLI: python -m mcp_servers.gemini.server
if __name__ == "__main__":
    mcp.run()
