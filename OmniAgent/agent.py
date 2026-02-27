"""
OmniAgent - Agentic Reasoning Engine
=====================================
A ReAct-style agent powered by Azure OpenAI that connects to the MCP server
and performs chain-of-thought reasoning across multiple domains.

Run with:  python agent.py
Requires:
  - services.py running on port 8000
  - .env file with Azure OpenAI credentials
"""

import asyncio
import inspect
import json
import os
import re
import sys
from datetime import datetime, timedelta

import httpx
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AzureOpenAI

load_dotenv()

# ---------------------------------------------------------------------------
# Azure OpenAI Configuration
# ---------------------------------------------------------------------------

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
)
DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")


def serialize_to_json(obj: object) -> str:
    """Serialize any object to a JSON string.

    Handles non-serializable types (datetime, set, bytes, custom objects)
    via a fallback encoder.
    """
    def default(o):
        if isinstance(o, (datetime,)):
            return o.isoformat()
        if isinstance(o, set):
            return list(o)
        if isinstance(o, bytes):
            return o.decode("utf-8", errors="replace")
        if hasattr(o, "__dict__"):
            return o.__dict__
        return str(o)

    return json.dumps(obj, default=default, ensure_ascii=False)

def print_object(obj: object):
    frame = inspect.currentframe().f_back
    call_line = inspect.getframeinfo(frame).code_context[0].strip()
    match = re.search(r'print_object\((.+)\)', call_line)
    var_name = match.group(1).strip() if match else type(obj).__qualname__
    print("Start "+"@" * 80)
    print(var_name)
    raw = serialize_to_json(obj)
    try:
        parsed = json.loads(raw)
        print(json.dumps(parsed, indent=2, ensure_ascii=False))
    except (json.JSONDecodeError, TypeError):
        print(raw)
    print("End "+"@" * 80)
    print()
    



SYSTEM_PROMPT = f"""You are OmniAgent, a helpful multi-domain personal assistant.
You have access to tools for weather, currency conversion, member lookup,
flight search/booking, and movie search/booking.

Today's date is {datetime.now().strftime('%Y-%m-%d')}.
Tomorrow's date is {(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')}.

When a user mentions "tomorrow", use tomorrow's date in YYYY-MM-DD format.

IMPORTANT REASONING INSTRUCTIONS:
1. Break down complex requests into sequential steps.
2. Always look up the member first if an email is provided — you need the member_id for bookings.
3. Execute tool calls one domain at a time, then synthesize all results into a final natural-language response.
4. When presenting options (flights, movies), format them clearly and ask before booking unless the user explicitly asks you to book.
5. Think step by step and explain your reasoning.
"""

print_object(SYSTEM_PROMPT)


async def run_agent():
    """Connect to the MCP server and run the interactive agent loop."""

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_server.py"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )
    print_object(server_params)

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Discover available tools from MCP server
            tools_result = await session.list_tools()
            print_object(tools_result)
            mcp_tools = tools_result.tools
            print_object(mcp_tools)

            # Convert MCP tool schemas to OpenAI function format
            openai_tools = []
            for tool in mcp_tools:
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.inputSchema if tool.inputSchema else {"type": "object", "properties": {}},
                    },
                })
            print_object(openai_tools)
            print("=" * 60)
            print("  OmniAgent - Multi-Domain AI Assistant")
            print("  Powered by Azure OpenAI + MCP")
            print(f"  Available tools: {[t.name for t in mcp_tools]}")
            print("=" * 60)
            print()
            print("Type your request (or 'quit' to exit):")
            print()

            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            print_object(messages)

            while True:
                print("Start first while")
                try:
                    user_input = input("You: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nGoodbye!")
                    break

                if not user_input:
                    continue
                if user_input.lower() in ("quit", "exit", "q"):
                    print("Goodbye!")
                    break

                messages.append({"role": "user", "content": user_input})
                print_object(messages)

                # ReAct loop: keep calling LLM until it stops requesting tools
                while True:
                    print("Start 2nd while - calling LLM for response and tool calls")
                    response = client.chat.completions.create(
                        model=DEPLOYMENT,
                        messages=messages,
                        tools=openai_tools if openai_tools else None,
                        temperature=0.3,
                    )
                    print("LLM response received:")
                    print_object(response)

                    choice = response.choices[0]
                    print_object(choice)
                    message = choice.message
                    print_object(message)

                    # If the model wants to call tools
                    if message.tool_calls:
                        # Add assistant message with tool calls
                        print("Enter message.tool_call-  model wants to call tools")
                        messages.append(message.model_dump())

                        for tool_call in message.tool_calls:
                            fn_name = tool_call.function.name
                            fn_args = json.loads(tool_call.function.arguments)

                            print(f"\n  [Tool Call] {fn_name}({fn_args})")

                            # Execute via MCP
                            try:
                                result = await session.call_tool(fn_name, fn_args)
                                tool_result = result.content[0].text if result.content else "No result"
                            except Exception as e:
                                tool_result = f"Error calling {fn_name}: {e}"

                            print(f"  [Result] {tool_result[:200]}{'...' if len(tool_result) > 200 else ''}")

                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": tool_result,
                            })
                            print_object(messages)
                    else:
                        print("Model has no tool calls, breaking out of tool call loop")
                        # Model produced a final text response
                        print(f"\nAgent: {message.content}\n")
                        messages.append({"role": "assistant", "content": message.content})
                        break
                    print("End 2nd while - back to top of tool call loop")
                print("End first while - back to top of user input loop")    


if __name__ == "__main__":
    asyncio.run(run_agent())
