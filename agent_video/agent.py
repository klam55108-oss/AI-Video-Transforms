"""
Video Transcription Agent - Interactive Multi-Turn Agent.

This script creates an interactive Claude Agent that guides users through
video transcription and offers follow-up actions on the transcribed content.

Usage:
    uv run python ./agent_video/agent.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path for development imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load environment variables before importing SDK
load_dotenv()

# Import system prompt from versioned prompts module
from agent_video.prompts import SYSTEM_PROMPT  # noqa: E402


def check_environment() -> bool:
    """Verify required environment variables are set."""
    print("=" * 60)
    print("Environment Check")
    print("=" * 60)

    openai_key = os.environ.get("OPENAI_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

    openai_status = "SET" if openai_key else "MISSING"
    anthropic_status = "SET" if anthropic_key else "MISSING"

    print(f"OPENAI_API_KEY:    {openai_status}")
    print(f"ANTHROPIC_API_KEY: {anthropic_status}")
    print()

    if not anthropic_key:
        print("ERROR: ANTHROPIC_API_KEY is required to run the agent.")
        print("Please add your Anthropic API key to the .env file.")
        print("Get your key at: https://console.anthropic.com/settings/keys")
        return False

    if not openai_key:
        print("WARNING: OPENAI_API_KEY is not set.")
        print("The transcribe_video tool will not work without it.")
        print()

    return True


def print_separator(char: str = "-", title: str | None = None) -> None:
    """Print a visual separator line."""
    if title:
        padding = (56 - len(title)) // 2
        print(f"{char * padding} {title} {char * padding}")
    else:
        print(char * 60)


async def run_transcription_agent() -> None:
    """Run the interactive multi-turn transcription agent."""
    # Import SDK components after dotenv is loaded
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ClaudeSDKClient,
        TextBlock,
    )

    from agent_video import video_tools_server

    print_separator("=", "Video Transcription Agent")
    print()
    print("Starting interactive transcription session...")
    print("Type 'quit' or 'exit' at any time to end the session.")
    print()

    options = ClaudeAgentOptions(
        model="claude-opus-4-5",
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={"video-tools": video_tools_server},
        allowed_tools=[
            "mcp__video-tools__transcribe_video",
            "mcp__video-tools__write_file",
            "mcp__video-tools__save_transcript",
            "mcp__video-tools__get_transcript",
            "mcp__video-tools__list_transcripts",
        ],
        max_turns=50,  # Allow for extended multi-turn conversation
    )

    try:
        async with ClaudeSDKClient(options) as client:
            print_separator("-", "Agent Connected")
            print()

            # Initial prompt to start the conversation
            initial_prompt = (
                "Start the conversation by greeting me and asking for a video "
                "to transcribe. Follow your workflow."
            )

            await client.query(initial_prompt)

            # Process initial response
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            print(f"\nAssistant: {block.text}\n")

            # Multi-turn conversation loop
            while True:
                print_separator("-")
                try:
                    user_input = input("You: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\n\nSession interrupted.")
                    break

                if not user_input:
                    continue

                if user_input.lower() in ("quit", "exit", "q"):
                    print("\nEnding session. Goodbye!")
                    break

                # Send user message
                await client.query(user_input)

                # Process and display response
                async for message in client.receive_response():
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                print(f"\nAssistant: {block.text}\n")

            print_separator("=", "Session Ended")

    except Exception as e:
        print(f"\nERROR: {e}")
        print()
        if "authentication" in str(e).lower() or "api key" in str(e).lower():
            print("This appears to be an authentication error.")
            print("Please verify your ANTHROPIC_API_KEY is correct.")
        else:
            print("An unexpected error occurred.")
            print("Please check your configuration and try again.")
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    print()
    print_separator("=", "Video Transcription Agent")
    print()
    print("An interactive AI assistant for transcribing videos")
    print("and working with the transcribed content.")
    print()

    if not check_environment():
        sys.exit(1)

    asyncio.run(run_transcription_agent())


if __name__ == "__main__":
    main()
