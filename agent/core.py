"""
Agent Runtime - LLM-powered agent with tool calling, self-learning, and memory.
Supports multiple providers: LM Studio and Ollama (OpenAI-compatible API).
"""

import json
import re
import subprocess
import sys
import platform
from datetime import datetime
from pathlib import Path
from openai import OpenAI
from typing import Optional, Generator, Any


# Import shared config (with fallback for backward compat)
try:
    from config import PROVIDERS, MODEL_DETECT_TIMEOUT
except ImportError:
    PROVIDERS = {
        "lmstudio": {
            "label": "LM Studio",
            "default_url": "http://127.0.0.1:1234/v1",
            "default_key": "lm-studio",
        },
        "ollama": {
            "label": "Ollama",
            "default_url": "http://127.0.0.1:11434/v1",
            "default_key": "ollama",
        },
    }
    MODEL_DETECT_TIMEOUT = 3


class Agent:
    """
    AI Agent with:
    - Multi-provider LLM (LM Studio / Ollama)
    - Streaming and non-streaming chat
    - Tool calling (shell, file ops, web search, calculator, flow)
    - Self-learning (extracts facts from conversations)
    - Memory (conversation history + learned facts)
    - Self-reflection (reviews its own responses)
    """

    def __init__(self, base_url: str = "http://127.0.0.1:1234/v1",
                 api_key: str = "lm-studio",
                 model: str = None,
                 memory=None,
                 system_prompt: str = None,
                 provider: str = "lmstudio"):

        self.provider = provider if provider in PROVIDERS else "lmstudio"
        self.base_url = base_url
        self.api_key = api_key
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        self.model = model or self._detect_model()
        self.memory = memory
        self.system_prompt = system_prompt or self._default_system_prompt()
        self.conversation = []
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Define available tools
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "run_command",
                    "description": "Run a shell/command line command. Works on the local system.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "description": "The shell command to execute"}
                        },
                        "required": ["command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read contents of a file from the filesystem.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Absolute or relative path to the file"}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write content to a file. Creates the file if it doesn't exist, overwrites if it does.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path"},
                            "content": {"type": "string", "description": "Content to write"}
                        },
                        "required": ["path", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "calculator",
                    "description": "Evaluate a mathematical expression.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "expression": {"type": "string", "description": "Math expression like '2 + 2 * 3'"}
                        },
                        "required": ["expression"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web for information (requires internet).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"}
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "learn_fact",
                    "description": "Store a fact in the agent's long-term memory for future reference.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "fact": {"type": "string", "description": "The fact to remember"},
                            "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags for categorization"}
                        },
                        "required": ["fact"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_memory_stats",
                    "description": "Get statistics about the agent's memory: facts learned, conversations, skills, etc.",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "flow_create",
                    "description": "Create a flow (scenario) from a user goal. Steps is a JSON array where each step has an 'action' field. Available actions: file_create (path, content), file_write (path, content, mode), file_read (path), file_delete (path), file_mkdir (path), script_exec (code, timeout, workdir), command (code), set_variable (name, value), api_call (url, method, data, headers, timeout), wait (seconds), notify (message). Use $VAR or ${VAR} for variables. Example: [{'action':'file_mkdir','path':'/tmp/test'},{'action':'file_create','path':'/tmp/test/hi.txt','content':'Hello $NAME'}]",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "flow_id": {"type": "string", "description": "Unique ID (lowercase, no spaces)"},
                            "name": {"type": "string", "description": "Human-readable name"},
                            "steps": {"type": "array", "items": {"type": "object"}, "description": "List of step objects"},
                            "description": {"type": "string", "description": "What the flow does"}
                        },
                        "required": ["flow_id", "name", "steps"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "flow_run",
                    "description": "Run a previously created flow by its ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "flow_id": {"type": "string"}
                        },
                        "required": ["flow_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "edit_file",
                    "description": "Edit a file by replacing exact text. Use this to make targeted changes. The oldText must match exactly (including whitespace). Use this for precise, surgical edits.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path to edit"},
                            "oldText": {"type": "string", "description": "Exact text to find and replace (must match exactly)"},
                            "newText": {"type": "string", "description": "New text to replace with"}
                        },
                        "required": ["path", "oldText", "newText"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_dir",
                    "description": "List files and directories in a given path. Shows file sizes and types.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Directory path to list (default: current directory)"},
                            "recursive": {"type": "boolean", "description": "List recursively (default: false)"},
                            "maxDepth": {"type": "integer", "description": "Max recursion depth (default: 2)"}
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "execute_code",
                    "description": "Execute a Python code snippet in a sandboxed subprocess. Has access to installed packages. Use for data processing, file operations, calculations, etc. Not for installing packages.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string", "description": "Python code to execute"},
                            "timeout": {"type": "integer", "description": "Timeout in seconds (default: 30, max: 120)"},
                            "workdir": {"type": "string", "description": "Working directory (default: project root)"}
                        },
                        "required": ["code"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "use_skill",
                    "description": "Load and activate a skill by name. The skill's instructions will be added to context. Use when you need specialized knowledge or workflow.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "skill_name": {"type": "string", "description": "Name of the skill to load (e.g., 'code-reviewer', 'data-analyzer', 'web-scraper')"}
                        },
                        "required": ["skill_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_cmd",
                    "description": "Run a Windows Command Prompt (cmd.exe) command. Use this for file operations, registry, and system commands. cmd /c 'your command here'. Use shell_commands=False (default).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "description": "The CMD command to execute. Wrap full command in cmd /c '...' if needed."},
                            "timeout": {"type": "integer", "description": "Timeout in seconds (default: 30, max: 120)"},
                            "workdir": {"type": "string", "description": "Working directory (optional)"}
                        },
                        "required": ["command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_powershell",
                    "description": "Run a PowerShell command. Use for advanced system management, WMI, Active Directory, etc. PowerShell -Command 'your command here'. Automatically sets -ExecutionPolicy Bypass.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "description": "The PowerShell command to execute"},
                            "timeout": {"type": "integer", "description": "Timeout in seconds (default: 30, max: 120)"},
                            "workdir": {"type": "string", "description": "Working directory (optional)"}
                        },
                        "required": ["command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "system_info",
                    "description": "Get system information: OS version, CPU, RAM, disk usage, network interfaces, environment variables. Full system reconnaissance.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "detail": {"type": "string", "enum": ["basic", "full"], "description": "basic or full (default: full)"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_disks",
                    "description": "List all disks/partitions with their sizes, used/free space, and mount points.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_processes",
                    "description": "List running processes. Can filter by name.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filter": {"type": "string", "description": "Filter processes by name (case-insensitive, optional)"},
                            "limit": {"type": "integer", "description": "Max number of processes to return (default: 50)"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "manage_service",
                    "description": "Start, stop, restart, or check status of a Windows service. Requires admin rights for most operations.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "service_name": {"type": "string", "description": "Name of the service (e.g., 'wuauserv', 'Dnscache', 'Spooler')"},
                            "action": {"type": "string", "enum": ["start", "stop", "restart", "status"], "description": "Action to perform"}
                        },
                        "required": ["service_name", "action"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "rag_search",
                    "description": "Search the knowledge base using RAG (Retrieval Augmented Generation). Finds relevant document chunks.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "top_k": {"type": "integer", "description": "Number of results (default: 3)"}
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "rag_ask",
                    "description": "Ask a question using RAG. Searches documents and generates an answer with sources.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string", "description": "Question to answer"}
                        },
                        "required": ["question"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "rag_index_file",
                    "description": "Index a file into the RAG knowledge base for future search.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path to index"}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "rag_list_docs",
                    "description": "List all indexed documents in the knowledge base.",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "task_create",
                    "description": "Create a new subtask in the task queue (BabyAGI-style).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string", "description": "Task description"},
                            "priority": {"type": "integer", "description": "1=highest, 10=lowest (default: 5)"}
                        },
                        "required": ["description"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "task_list",
                    "description": "List tasks in the queue. Optional status filter: pending, in_progress, completed, failed.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "description": "Filter by status (optional)"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "react_solve",
                    "description": "Use the ReAct (Reasoning+Acting) engine to solve a complex task autonomously. The agent thinks, acts, observes, and iterates.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task": {"type": "string", "description": "Task to solve"},
                            "max_steps": {"type": "integer", "description": "Max reasoning steps (default: 10)"}
                        },
                        "required": ["task"]
                    }
                }
            },
        ]

        # Working directory for tool execution (cross-platform)
        self._workdir = str(Path(__file__).resolve().parent.parent)

    def _get_workdir(self) -> str:
        """Get the project working directory (cross-platform)."""
        return self._workdir

    def set_workdir(self, path: str):
        """Set the working directory for tool execution."""
        self._workdir = str(Path(path).resolve())

    def _detect_model(self) -> str:
        """Auto-detect the loaded model from the provider (MODEL_DETECT_TIMEOUT s timeout)."""
        try:
            from openai import OpenAI as _OpenAI
            c = _OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=MODEL_DETECT_TIMEOUT)
            resp = c.models.list()
            if resp.data:
                return resp.data[0].id
        except Exception:
            pass
        return "local-model"

    def _default_system_prompt(self) -> str:
        return """You are OWL, a helpful AI agent running locally. You have:
- Tool calling capabilities (run commands, read/write/edit files, list directories, calculator, web_search, memory, code execution)
- Self-learning ability - you extract and remember facts from conversations
- Persistent memory across conversations via SQLite database
- Flow automation — you can create and run flows (scenarios) from natural language
- Skill system — you can load specialized knowledge/skills

Available tools:
- run_command: execute shell commands
- run_cmd: run Windows CMD commands (cmd /c)
- run_powershell: run PowerShell commands (advanced system management)
- read_file: read file contents
- write_file: create or overwrite files
- edit_file: make precise targeted edits to files
- list_dir: list files and directories, optionally recursive
- execute_code: run Python code in a sandboxed subprocess
- web_search: search the web via DuckDuckGo
- calculator: evaluate math expressions
- learn_fact: store facts in long-term memory
- get_memory_stats: view memory statistics
- use_skill: load a specialized skill by name
- system_info: get OS, CPU, RAM, disk, network info
- list_disks: list all disks with sizes and free space
- list_processes: list running processes (filterable)
- manage_service: start/stop/restart Windows services
- flow_create: create a scenario/flow from a user goal
- flow_run: execute a previously created flow by its ID

Flow step actions: file_create, file_write, file_read, file_delete, file_mkdir, script_exec, command, set_variable, api_call, wait, notify, if, loop, parallel.

Guidelines:
- Be concise and direct, especially in Russian
- When you learn something new, use the learn_fact tool to remember it
- Use tools proactively when they would help answer the query
- If user writes in Russian, respond in Russian
- Be resourceful - try to solve problems, don't just explain them
- When you make a mistake, acknowledge it and correct yourself
- When user asks to automate something, offer to create a flow
- Use edit_file for precise changes instead of rewriting entire files
- Use execute_code for complex data processing or multi-step Python logic"""

    def _build_messages(self, user_message: str, enabled_skills_only: bool = True) -> list:
        """Build the messages list for an LLM call."""
        messages = [{"role": "system", "content": self.system_prompt}]

        # Inject enabled skills context
        if self.memory:
            try:
                skills = self.memory.get_all_skills()
                if enabled_skills_only:
                    skills = [s for s in skills if s.get("enabled", True)]
                if skills:
                    skill_lines = ["[Active Skills]"]
                    for s in skills:
                        desc = s.get("description", "")[:120]
                        skill_lines.append(f"  - {s['name']}: {desc}")
                    messages.append({
                        "role": "system",
                        "content": "\n".join(skill_lines)
                    })
            except Exception:
                pass

        # Inject memory context
        if self.memory:
            try:
                memory_context = self.memory.build_context(self.session_id, user_message)
                if memory_context:
                    messages.append({
                        "role": "system",
                        "content": f"[Memory Context]\n{memory_context}"
                    })
            except Exception:
                pass

        # Add conversation history (last 20)
        recent = self.conversation[-20:] if len(self.conversation) > 20 else self.conversation
        messages.extend(recent)
        messages.append({"role": "user", "content": user_message})
        return messages

    def _stream_completion(self, messages: list, tool_only: bool = False) -> Generator[dict, None, None]:
        """
        Stream completion from LLM. Yields dicts:
          {"type": "text", "content": "chunk text"}
          {"type": "tool_call", "name": "tool_name", "arguments": {...}, "id": "..."}
          {"type": "done", "finish_reason": "stop"|"tool_calls"|"length"}
        
        For Ollama, uses native /api/chat endpoint (supports think:false, proper streaming).
        """
        # Use native Ollama API for Ollama provider
        if self.provider == "ollama":
            yield from self._stream_ollama_native(messages, tool_only)
            return
        
        # Standard OpenAI-compatible streaming
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tools if not tool_only else None,
                tool_choice="auto" if not tool_only else "none",
                temperature=0.7,
                max_tokens=4096,
                stream=True
            )

            current_tool_args = {}
            current_tool_name = None
            current_tool_id = None

            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                finish = chunk.choices[0].finish_reason if chunk.choices else None

                # Text content
                if delta and delta.content:
                    yield {"type": "text", "content": delta.content}

                # Tool call streaming
                if delta and delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if tc_delta.id:
                            if current_tool_name and current_tool_id:
                                yield {
                                    "type": "tool_call",
                                    "name": current_tool_name,
                                    "arguments": current_tool_args,
                                    "id": current_tool_id
                                }
                            current_tool_id = tc_delta.id
                            current_tool_name = tc_delta.function.name if tc_delta.function else ""
                            current_tool_args = ""
                        if tc_delta.function and tc_delta.function.arguments:
                            current_tool_args += tc_delta.function.arguments

                if finish:
                    if current_tool_name and current_tool_id:
                        try:
                            parsed_args = json.loads(current_tool_args) if current_tool_args else {}
                        except json.JSONDecodeError:
                            parsed_args = {}
                        yield {
                            "type": "tool_call",
                            "name": current_tool_name,
                            "arguments": parsed_args,
                            "id": current_tool_id
                        }
                    yield {"type": "done", "finish_reason": finish}
                    return

            # End of stream without finish_reason
            if current_tool_name and current_tool_id:
                try:
                    parsed_args = json.loads(current_tool_args) if current_tool_args else {}
                except json.JSONDecodeError:
                    parsed_args = {}
                yield {
                    "type": "tool_call",
                    "name": current_tool_name,
                    "arguments": parsed_args,
                    "id": current_tool_id
                }
            yield {"type": "done", "finish_reason": "stop"}

        except Exception as e:
            yield {"type": "error", "content": str(e)}

    def _stream_ollama_native(self, messages: list, tool_only: bool = False) -> Generator[dict, None, None]:
        """Stream from Ollama native /api/chat endpoint — handles thinking models properly."""
        import urllib.request
        import json as _json
        
        ollama_messages = []
        for msg in messages:
            ollama_messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "") or ""})
        
        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": False,
            "think": False,
        }
        
        if not tool_only and self.tools:
            payload["tools"] = self.tools
        
        req_data = _json.dumps(payload).encode("utf-8")
        base = self.base_url.replace("/v1", "")
        url = f"{base.rstrip('/')}/api/chat"
        
        req = urllib.request.Request(
            url, data=req_data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = _json.loads(resp.read().decode("utf-8"))
            
            if "error" in data:
                yield {"type": "error", "content": data["error"]}
                return
            
            msg = data.get("message", {})
            content = msg.get("content", "")
            if content:
                yield {"type": "text", "content": content}
            
            # Check for tool calls in Ollama format
            tool_calls = msg.get("tool_calls", [])
            for tc in tool_calls:
                func = tc.get("function", {})
                yield {
                    "type": "tool_call",
                    "name": func.get("name", ""),
                    "arguments": func.get("arguments", {}),
                    "id": tc.get("id", "")
                }
            
            yield {"type": "done", "finish_reason": "stop"}
            
        except Exception as e:
            yield {"type": "error", "content": str(e)}

    def chat_stream(self, user_message: str) -> Generator[dict, None, None]:
        """
        Streaming chat with tool calling loop.
        Yields SSE-safe dicts:
          {"type": "text", "content": "..."}         — text chunk
          {"type": "tool_start", "name": "..."}       — tool call started
          {"type": "tool_end", "name": "...", "result_preview": "..."} — tool done
          {"type": "done", "session_id": "...", "model": "..."}
          {"type": "error", "content": "..."}
        """
        messages = self._build_messages(user_message)

        # Store user message
        if self.memory:
            self.memory.add_message(self.session_id, "user", user_message)

        full_response = ""
        tool_calls_made = []
        max_iterations = 5
        iteration = 0

        try:
            while iteration < max_iterations:
                iteration += 1

                accumulated_text = ""
                pending_tools = []

                # Stream one LLM response
                for event in self._stream_completion(messages):
                    if event["type"] == "text":
                        accumulated_text += event["content"]
                        yield {"type": "text", "content": event["content"]}
                    elif event["type"] == "tool_call":
                        pending_tools.append(event)
                    elif event["type"] == "done":
                        pass
                    elif event["type"] == "error":
                        yield event
                        return

                full_response += accumulated_text

                if not pending_tools:
                    # No tool calls — we're done
                    break

                # Build assistant message with tool calls
                assistant_msg = {
                    "role": "assistant",
                    "content": accumulated_text or None,
                    "tool_calls": [
                        {
                            "id": t["id"],
                            "type": "function",
                            "function": {
                                "name": t["name"],
                                "arguments": json.dumps(t["arguments"])
                            }
                        }
                        for t in pending_tools
                    ]
                }
                messages.append(assistant_msg)

                # Execute each tool
                for tc in pending_tools:
                    tool_name = tc["name"]
                    tool_args = tc["arguments"]

                    yield {"type": "tool_start", "name": tool_name, "arguments": tool_args}

                    result = self._execute_tool(tool_name, tool_args)
                    result_str = str(result)
                    tool_calls_made.append({
                        "tool": tool_name,
                        "args": tool_args,
                        "result_preview": result_str[:200]
                    })

                    yield {"type": "tool_end", "name": tool_name, "result_preview": result_str[:200]}

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": tool_name,
                        "content": result_str
                    })

        except Exception as e:
            yield {"type": "error", "content": f"Stream error: {str(e)}"}
            return

        # Store assistant response
        if self.memory and full_response:
            self.memory.add_message(self.session_id, "assistant", full_response)
            self._self_learn(user_message, full_response)
            self._self_reflect(user_message, full_response, tool_calls_made)

        # Update conversation history
        self.conversation.append({"role": "user", "content": user_message})
        self.conversation.append({"role": "assistant", "content": full_response})

        yield {
            "type": "done",
            "session_id": self.session_id,
            "model": self.model,
            "tool_calls": tool_calls_made
        }

    def chat(self, user_message: str, stream: bool = False) -> dict:
        """
        Main chat method. Returns dict with response and metadata.
        Handles tool calling loop automatically.
        """
        if stream:
            # Run the stream and collect everything
            full_response = ""
            tool_calls_made = []
            for event in self.chat_stream(user_message):
                if event["type"] == "text":
                    full_response += event["content"]
                elif event["type"] == "tool_end":
                    tool_calls_made.append({"tool": event["name"], "result_preview": event.get("result_preview", "")})
            return {
                "response": full_response,
                "tool_calls": tool_calls_made,
                "model": self.model,
                "session_id": self.session_id
            }

        # Non-streaming: collect from stream internally (reuse logic)
        messages = self._build_messages(user_message)

        if self.memory:
            self.memory.add_message(self.session_id, "user", user_message)

        full_response = ""
        tool_calls_made = []

        try:
            max_iterations = 5
            iteration = 0
            pending_tools = []

            while iteration < max_iterations:
                iteration += 1
                pending_tools = []
                accumulated_text = ""

                for event in self._stream_completion(messages):
                    if event["type"] == "text":
                        accumulated_text += event["content"]
                    elif event["type"] == "tool_call":
                        pending_tools.append(event)
                    elif event["type"] == "error":
                        raise Exception(event["content"])

                full_response += accumulated_text

                if not pending_tools:
                    break

                messages.append({
                    "role": "assistant",
                    "content": accumulated_text or None,
                    "tool_calls": [
                        {
                            "id": t["id"],
                            "type": "function",
                            "function": {"name": t["name"], "arguments": json.dumps(t["arguments"])}
                        }
                        for t in pending_tools
                    ]
                })

                for tc in pending_tools:
                    result = self._execute_tool(tc["name"], tc["arguments"])
                    tool_calls_made.append({
                        "tool": tc["name"],
                        "args": tc["arguments"],
                        "result_preview": str(result)[:100]
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": tc["name"],
                        "content": str(result)
                    })

        except Exception as e:
            full_response = f"Error communicating with LLM: {str(e)}"
            if self.memory:
                self.memory.reflect("llm_error", str(e), "returned_error_to_user")

        if self.memory:
            self.memory.add_message(self.session_id, "assistant", full_response)
            self._self_learn(user_message, full_response)
            self._self_reflect(user_message, full_response, tool_calls_made)

        self.conversation.append({"role": "user", "content": user_message})
        self.conversation.append({"role": "assistant", "content": full_response})

        return {
            "response": full_response,
            "tool_calls": tool_calls_made,
            "model": self.model,
            "session_id": self.session_id
        }

    def switch_provider(self, provider: str, base_url: str = None, api_key: str = None):
        """Switch to a different provider (lmstudio / ollama)."""
        if provider not in PROVIDERS:
            raise ValueError(f"Unknown provider: {provider}. Available: {list(PROVIDERS.keys())}")

        p = PROVIDERS[provider]
        self.provider = provider
        self.base_url = base_url or p["default_url"]
        self.api_key = api_key or p["default_key"]
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        self.model = self._detect_model()
        return {"provider": provider, "url": self.base_url, "model": self.model}

    def _execute_tool(self, tool_name: str, args: dict) -> str:
        """Execute a tool and return the result."""
        try:
            if tool_name == "run_command":
                return self._tool_run_command(args.get("command", ""))
            elif tool_name == "read_file":
                return self._tool_read_file(args.get("path", ""))
            elif tool_name == "write_file":
                return self._tool_write_file(args.get("path", ""), args.get("content", ""))
            elif tool_name == "edit_file":
                return self._tool_edit_file(args.get("path", ""), args.get("oldText", ""), args.get("newText", ""))
            elif tool_name == "list_dir":
                return self._tool_list_dir(args.get("path", "."), args.get("recursive", False), args.get("maxDepth", 2))
            elif tool_name == "execute_code":
                return self._tool_execute_code(args.get("code", ""), args.get("timeout", 30), args.get("workdir", self._get_workdir()))
            elif tool_name == "calculator":
                return self._tool_calculator(args.get("expression", ""))
            elif tool_name == "web_search":
                return self._tool_web_search(args.get("query", ""))
            elif tool_name == "learn_fact":
                if self.memory:
                    self.memory.learn_fact(args["fact"], tags=args.get("tags", []))
                    return f"Fact learned: {args['fact']}"
                return "Memory system not available"
            elif tool_name == "get_memory_stats":
                if self.memory:
                    stats = self.memory.get_stats()
                    return json.dumps(stats, indent=2)
                return "Memory system not available"
            elif tool_name == "flow_create":
                from agent.flow_engine import FlowEngine
                fe = FlowEngine()
                fe.create_flow(
                    args["flow_id"], args["name"],
                    args["steps"], args.get("description", ""),
                    args.get("variables", {})
                )
                return f"Flow '{args['flow_id']}' created with {len(args['steps'])} steps"
            elif tool_name == "flow_run":
                from agent.flow_engine import FlowEngine
                fe = FlowEngine()
                result = fe.run_flow(args["flow_id"])
                return json.dumps(result, ensure_ascii=False, indent=2)[:3000]
            elif tool_name == "use_skill":
                return self._tool_use_skill(args.get("skill_name", ""))
            elif tool_name == "run_cmd":
                return self._tool_run_cmd(args.get("command", ""), args.get("timeout", 30), args.get("workdir"))
            elif tool_name == "run_powershell":
                return self._tool_run_powershell(args.get("command", ""), args.get("timeout", 30), args.get("workdir"))
            elif tool_name == "system_info":
                return self._tool_system_info(args.get("detail", "full"))
            elif tool_name == "list_disks":
                return self._tool_list_disks()
            elif tool_name == "list_processes":
                return self._tool_list_processes(args.get("filter", ""), args.get("limit", 50))
            elif tool_name == "manage_service":
                return self._tool_manage_service(args.get("service_name", ""), args.get("action", "status"))
            # -- RAG tools --
            elif tool_name == "rag_search":
                from agent.rag_engine import search
                results = search(args.get("query", ""), top_k=args.get("top_k", 3))
                if not results:
                    return "No relevant documents found."
                lines = []
                for r in results:
                    lines.append(f"[{r['source']}] (score: {r['score']:.3f})\n{r['content'][:300]}")
                return "\n---\n".join(lines)
            elif tool_name == "rag_ask":
                from agent.rag_engine import search_and_generate
                result = search_and_generate(
                    args.get("question", ""),
                    self.client, self.model,
                    top_k=args.get("top_k", 3)
                )
                sources = ", ".join([s["source"] for s in result.get("sources", [])])
                return f"{result['answer']}\n\nSources: {sources}"
            elif tool_name == "rag_index_file":
                from agent.rag_engine import load_file
                result = load_file(args.get("path", ""))
                if "error" in result:
                    return result["error"]
                return f"Indexed: {result['source']} ({result['chunks']} chunks)"
            elif tool_name == "rag_list_docs":
                from agent.rag_engine import list_documents
                docs = list_documents()
                if not docs:
                    return "No documents indexed."
                lines = [f"- {d['title']} ({d['source']}): {d['chunk_count']} chunks" for d in docs]
                return "\n".join(lines)
            # -- Task management tools --
            elif tool_name == "task_create":
                from agent.react_engine import create_task
                t = create_task(args.get("description", ""), priority=args.get("priority", 5))
                return f"Task created: [{t['id']}] {t['description']}"
            elif tool_name == "task_list":
                from agent.react_engine import list_tasks
                tasks = list_tasks(status=args.get("status"))
                if not tasks:
                    return "No tasks found."
                lines = []
                for t in tasks:
                    lines.append(f"[{t['status']}] (p{t['priority']}) {t['description']}")
                return "\n".join(lines)
            # -- ReAct tool --
            elif tool_name == "react_solve":
                from agent.react_engine import ReActEngine
                engine = ReActEngine(self)
                result = engine.run(
                    args.get("task", ""),
                    max_steps=args.get("max_steps", 10)
                )
                return json.dumps(result, ensure_ascii=False, indent=2)[:5000]
            else:
                return f"Unknown tool: {tool_name}"
        except Exception as e:
            return f"Tool error ({tool_name}): {str(e)}"

    def _tool_run_command(self, command: str) -> str:
        """Run a shell command and return output."""
        if not command:
            return "No command provided"
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=30, cwd=self._get_workdir()
            )
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR: {result.stderr}"
            if result.returncode != 0:
                output += f"\nExit code: {result.returncode}"
            return output[:5000] if output else "(no output)"
        except subprocess.TimeoutExpired:
            return "Command timed out (30s limit)"
        except Exception as e:
            return f"Error: {str(e)}"

    def _tool_read_file(self, path: str) -> str:
        """Read a file."""
        if not path:
            return "No path provided"
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()[:10000]
        except FileNotFoundError:
            return f"File not found: {path}"
        except Exception as e:
            return f"Error reading {path}: {str(e)}"

    def _tool_write_file(self, path: str, content: str) -> str:
        """Write a file."""
        if not path:
            return "No path provided"
        import os
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Written to {path} ({len(content)} chars)"
        except Exception as e:
            return f"Error writing {path}: {str(e)}"

    def _tool_calculator(self, expression: str) -> str:
        """Safely evaluate a math expression."""
        if not expression:
            return "No expression provided"
        try:
            safe = re.sub(r'[^0-9+\-*/.()eE\s%^//]', '', expression)
            if not safe:
                return "Invalid expression"
            result = eval(safe, {"__builtins__": {}}, {})
            return f"{expression} = {result}"
        except Exception as e:
            return f"Calculation error: {str(e)}"

    def _tool_web_search(self, query: str) -> str:
        """Search the web via DuckDuckGo."""
        if not query:
            return "No query provided"
        try:
            import urllib.parse, re as _re, urllib.request
            ddg_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(query)}"
            req = urllib.request.Request(ddg_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            results = []
            for m in _re.finditer(r'result__url[^>]*>([^<]+)<', html):
                url = m.group(1).strip()
                if url and url.startswith("http"):
                    results.append(url)
                if len(results) >= 5:
                    break
            if not results:
                for m in _re.finditer(r'href="(https?://[^"]+)"', html):
                    url = m.group(1)
                    if "duckduckgo" not in url:
                        results.append(url)
                    if len(results) >= 5:
                        break
            return "\n".join(f"{i+1}. {u}" for i, u in enumerate(results[:5])) or "No results"
        except Exception as e:
            return f"Search error: {e}"

    def _tool_edit_file(self, path: str, old_text: str, new_text: str) -> str:
        """Edit a file by replacing exact text."""
        if not path:
            return "No path provided"
        if not old_text:
            return "No oldText provided"
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            if old_text not in content:
                # Try with normalized whitespace
                return f"Text not found in {path}. Use read_file to see current content."
            new_content = content.replace(old_text, new_text, 1)
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
            return f"Edited {path}: replaced {len(old_text)} chars with {len(new_text)} chars"
        except FileNotFoundError:
            return f"File not found: {path}"
        except Exception as e:
            return f"Error editing {path}: {str(e)}"

    def _tool_list_dir(self, path: str, recursive: bool = False, max_depth: int = 2) -> str:
        """List files and directories."""
        if not path:
            path = "."
        try:
            p = Path(path)
            if not p.exists():
                return f"Path not found: {path}"
            lines = []
            if recursive:
                for item in sorted(p.rglob("*")):
                    depth = len(item.relative_to(p).parts)
                    if depth > max_depth:
                        continue
                    indent = "  " * depth
                    if item.is_dir():
                        lines.append(f"{indent}[DIR]  {item.name}/")
                    else:
                        size = item.stat().st_size
                        unit = "B"
                        if size > 1024:
                            size /= 1024
                            unit = "KB"
                        if size > 1024:
                            size /= 1024
                            unit = "MB"
                        lines.append(f"{indent}[FILE] {item.name} ({size:.0f}{unit})")
            else:
                for item in sorted(p.iterdir()):
                    if item.is_dir():
                        lines.append(f"[DIR]  {item.name}/")
                    else:
                        size = item.stat().st_size
                        unit = "B"
                        if size > 1024:
                            size /= 1024
                            unit = "KB"
                        if size > 1024:
                            size /= 1024
                            unit = "MB"
                        lines.append(f"[FILE] {item.name} ({size:.0f}{unit})")
            return "\n".join(lines) if lines else "(empty directory)"
        except Exception as e:
            return f"Error listing {path}: {str(e)}"

    def _tool_execute_code(self, code: str, timeout: int = 30, workdir: str = None) -> str:
        """Execute Python code in a subprocess sandbox."""
        if not code:
            return "No code provided"
        import tempfile
        timeout = min(int(timeout), 120)
        if not workdir:
            workdir = self._get_workdir()
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False,
                                              prefix="owl_exec_", dir=workdir) as tf:
                tf.write(code)
                tmp_path = tf.name
            result = subprocess.run(
                [sys.executable, tmp_path],
                shell=False, capture_output=True, text=True,
                timeout=timeout, cwd=workdir
            )
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR: {result.stderr}"
            if result.returncode != 0:
                output += f"\nExit code: {result.returncode}"
            # Cleanup
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
            return output[:5000] if output else "(no output)"
        except subprocess.TimeoutExpired:
            return f"Code execution timed out ({timeout}s limit)"
        except Exception as e:
            return f"Execution error: {str(e)}"

    def _tool_use_skill(self, skill_name: str) -> str:
        """Load a skill and return its content for context injection."""
        if not skill_name:
            return "No skill name provided"
        if not self.memory:
            return "Memory system not available"
        # Try to find and read the skill
        skill_base = Path(__file__).parent.parent / "skills"
        # Search case-insensitive
        found = None
        for d in skill_base.iterdir():
            if d.is_dir() and d.name.lower().replace("-", " ").replace("_", " ") == skill_name.lower().replace("-", " ").replace("_", " "):
                md = d / "SKILL.md"
                if md.exists():
                    found = md
                    break
        if not found:
            # Try direct match
            for ext in ["", ".md"]:
                candidate = skill_base / f"{skill_name}{ext}"
                if candidate.exists():
                    found = candidate
                    break
        if not found:
            # List available skills
            available = [d.name for d in sorted(skill_base.iterdir()) if d.is_dir()]
            return f"Skill '{skill_name}' not found. Available: {', '.join(available)}"
        try:
            content = found.read_text(encoding="utf-8")
            # Extract just the instruction part (skip frontmatter if present)
            lines = content.split("\n")
            in_frontmatter = False
            instruction_lines = []
            for line in lines:
                if line.strip() == "---":
                    in_frontmatter = not in_frontmatter
                    continue
                if not in_frontmatter:
                    instruction_lines.append(line)
            instructions = "\n".join(instruction_lines).strip()
            # Also store in memory for persistence
            if self.memory:
                self.memory.learn_fact(f"Skill loaded: {skill_name}", source="skill", confidence=0.95)
            return f"SKILL [{skill_name}]:\n{instructions}"
        except Exception as e:
            return f"Error reading skill: {str(e)}"

    def _tool_run_cmd(self, command: str, timeout: int = 32, workdir: str = None) -> str:
        """Run a Windows CMD command."""
        if not command:
            return "No command provided"
        timeout = min(int(timeout), 120)
        cwd = workdir or self._get_workdir()
        try:
            # On Windows, wrap in cmd /c; on Unix run directly
            import platform
            if platform.system() == "Windows":
                cmd = f'cmd /c "{command}"'
            else:
                cmd = command
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=cwd
            )
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR: {result.stderr}"
            if result.returncode != 0:
                output += f"\nExit code: {result.returncode}"
            return output[:5000] if output else "(no output)"
        except subprocess.TimeoutExpired:
            return f"Command timed out ({timeout}s)"
        except Exception as e:
            return f"Error: {str(e)}"

    def _tool_run_powershell(self, command: str, timeout: int = 32, workdir: str = None) -> str:
        """Run a PowerShell command."""
        if not command:
            return "No command provided"
        timeout = min(int(timeout), 120)
        cwd = workdir or self._get_workdir()
        try:
            import platform
            if platform.system() == "Windows":
                # Escape double quotes inside the command
                escaped = command.replace('"', '\\"')
                ps_cmd = f'powershell -ExecutionPolicy Bypass -Command "{escaped}"'
            else:
                # On Linux, try pwsh or fall back to bash
                ps_cmd = command
            result = subprocess.run(
                ps_cmd, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=cwd
            )
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR: {result.stderr}"
            if result.returncode != 0:
                output += f"\nExit code: {result.returncode}"
            return output[:5000] if output else "(no output)"
        except subprocess.TimeoutExpired:
            return f"PowerShell timed out ({timeout}s)"
        except Exception as e:
            return f"Error: {str(e)}"

    def _tool_system_info(self, detail: str = "full") -> str:
        """Get comprehensive system information."""
        import platform
        lines = []
        lines.append(f"OS: {platform.system()} {platform.release()}")
        lines.append(f"Version: {platform.version()}")
        lines.append(f"Machine: {platform.machine()}")
        lines.append(f"Processor: {platform.processor()}")
        lines.append(f"Python: {platform.python_version()}")
        lines.append(f"Node: {platform.node()}")
        
        try:
            import os
            lines.append(f"CPU cores: {os.cpu_count()}")
        except:
            pass
        
        try:
            import psutil
            mem = psutil.virtual_memory()
            lines.append(f"RAM: {mem.total/(1024**3):.1f} GB total, {mem.available/(1024**3):.1f} GB free ({mem.percent}% used)")
            lines.append(f"CPU usage: {psutil.cpu_percent(interval=0.5)}%")
            
            if detail == "full":
                lines.append("\n--- Disks ---")
                for part in psutil.disk_partitions():
                    try:
                        usage = psutil.disk_usage(part.mountpoint)
                        lines.append(f"  {part.device} ({part.mountpoint}): {usage.total/(1024**3):.1f} GB total, {usage.free/(1024**3):.1f} GB free")
                    except:
                        lines.append(f"  {part.device} ({part.mountpoint}): access denied")
                
                lines.append("\n--- Network ---")
                for name, addrs in psutil.net_if_addrs().items():
                    for addr in addrs:
                        if addr.family.name == 'AF_INET':
                            lines.append(f"  {name}: {addr.address}")
            
            return "\n".join(lines)
        except ImportError:
            # psutil not available, try basic commands
            lines.append("\n(psutil not installed, using basic commands)")
            try:
                result = subprocess.run("wmic cpu get Name /value 2>nul || echo 'wmic not available'", 
                                      shell=True, capture_output=True, text=True, timeout=5)
                if result.stdout.strip():
                    lines.append(f"CPU: {result.stdout.strip()}")
            except:
                pass
            return "\n".join(lines)
        except Exception as e:
            return "\n".join(lines) + f"\nError: {e}"

    def _tool_list_disks(self) -> str:
        """List all disks/partitions with sizes."""
        import platform
        lines = []
        try:
            import psutil
            for part in psutil.disk_partitions(all=True):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    lines.append(f"{part.device} | {part.fstype} | {part.mountpoint} | "
                               f"{usage.total/(1024**3):.1f}GB total | {usage.used/(1024**3):.1f}GB used | "
                               f"{usage.free/(1024**3):.1f}GB free | {usage.percent}%")
                except PermissionError:
                    lines.append(f"{part.device} | {part.fstype} | {part.mountpoint} | access denied")
        except ImportError:
            # Fallback without psutil
            if platform.system() == "Windows":
                result = subprocess.run("wmic logicaldisk get DeviceID,Size,FreeSpace,FileSystem /format:csv",
                                      shell=True, capture_output=True, text=True, timeout=10)
                lines.append(result.stdout.strip())
            else:
                result = subprocess.run("df -h", shell=True, capture_output=True, text=True, timeout=5)
                lines.append(result.stdout.strip())
        
        return "\n".join(lines) if lines else "No disk info available"

    def _tool_list_processes(self, filter_name: str = "", limit: int = 50) -> str:
        """List running processes."""
        import platform
        lines = []
        try:
            import psutil
            procs = []
            for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
                try:
                    info = p.info
                    if filter_name and filter_name.lower() not in info['name'].lower():
                        continue
                    procs.append(info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Sort by CPU usage
            procs.sort(key=lambda x: x.get('cpu_percent', 0) or 0, reverse=True)
            
            lines.append(f"{'PID':<10} {'CPU%':<8} {'MEM%':<8} {'Status':<12} {'Name'}")
            lines.append("-" * 60)
            for p in procs[:limit]:
                lines.append(f"{p['pid']:<10} {p.get('cpu_percent',0) or 0:<8.1f} "
                           f"{p.get('memory_percent',0) or 0:<8.1f} {p.get('status',''):<12} {p.get('name','')}")
        except ImportError:
            if platform.system() == "Windows":
                result = subprocess.run("tasklist /fo csv /nh", shell=True, capture_output=True, text=True, timeout=10)
                lines.append(result.stdout.strip())
            else:
                result = subprocess.run("ps aux --sort=-%cpu | head -20", shell=True, capture_output=True, text=True, timeout=5)
                lines.append(result.stdout.strip())
        
        return "\n".join(lines) if lines else "No process info available"

    def _tool_manage_service(self, service_name: str, action: str = "status") -> str:
        """Manage Windows services (start, stop, restart, status)."""
        import platform
        if platform.system() != "Windows":
            return "Service management is Windows-only"
        
        if not service_name:
            return "No service name provided"
        
        valid_actions = ["start", "stop", "restart", "status"]
        if action not in valid_actions:
            return f"Invalid action. Use: {', '.join(valid_actions)}"
        
        try:
            if action == "status":
                result = subprocess.run(f'sc query "{service_name}"', shell=True, 
                                      capture_output=True, text=True, timeout=10)
            elif action == "start":
                result = subprocess.run(f'net start "{service_name}"', shell=True,
                                      capture_output=True, text=True, timeout=30)
            elif action == "stop":
                result = subprocess.run(f'net stop "{service_name}"', shell=True,
                                      capture_output=True, text=True, timeout=30)
            elif action == "restart":
                subprocess.run(f'net stop "{service_name}"', shell=True,
                             capture_output=True, text=True, timeout=30)
                result = subprocess.run(f'net start "{service_name}"', shell=True,
                                      capture_output=True, text=True, timeout=30)
            
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR: {result.stderr}"
            return output[:3000] if output else "(no output)"
        except subprocess.TimeoutExpired:
            return f"Service {action} timed out"
        except Exception as e:
            return f"Error: {str(e)}"

    def _self_learn(self, user_message: str, assistant_response: str):
        """Extract facts from USER message only."""
        if not self.memory:
            return
        try:
            fact_patterns = [
                (r'(?:меня\s+зовут)\s+([А-Яа-яЁёA-Za-z\-]{2,30})', 0.85),
                (r'(?:мне\s+нравится|я\s+предпочитаю|я\s+люблю)\s+([^.!?\\n]{3,80})', 0.7),
                (r'(?:запомни|remember)\b\s*[:\\-]?\s*([^.!?\\n]{3,100})', 0.9),
                (r'(?:(?:\я\s+)?(?:работаю|живу|учусь)\s+(?:в|на|у))\s+([^.!?\\n]{3,80})', 0.6),
                (r'(?:my\s+name\s+is|i\s+am|i\'?m)\s+([^.!?\\n]{2,50})', 0.85),
                (r'(?:i\s+(?:like|prefer|want|love))\s+([^.!?\\n]{3,80})', 0.7),
            ]
            extracted = 0
            for pattern, conf in fact_patterns:
                for m in re.findall(pattern, user_message, re.IGNORECASE):
                    fact = m.strip() if isinstance(m, str) else " ".join(m).strip()
                    fact = re.sub(r'\s+', ' ', fact).strip()
                    if 3 < len(fact) < 120 and not fact.startswith('\n'):
                        self.memory.learn_fact(fact, source="conversation", confidence=conf)
                        extracted += 1
            if extracted > 0:
                self.memory.reflect("self_learning", f"Extracted {extracted} facts", "stored_in_memory")
        except Exception:
            pass

    def _self_reflect(self, user_message: str, response: str, tool_calls: list):
        """Self-reflection."""
        if not self.memory:
            return
        try:
            reflection = f"Response given ({len(response)} chars)"
            if tool_calls:
                tool_names = [t["tool"] for t in tool_calls]
                reflection += f". Tools used: {', '.join(tool_names)}"
            if len(response) < 10:
                reflection += ". WARNING: Very short response"
            if len(tool_calls) >= 5:
                reflection += ". NOTE: Many tool calls"
            self.memory.reflect("conversation_complete", reflection, "")
        except Exception:
            pass

    def get_conversation_history(self) -> list:
        return self.conversation.copy()

    def clear_conversation(self):
        self.conversation = []
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    def change_model(self, model_name: str):
        self.model = model_name

    def list_models(self) -> list:
        """List available models from the current provider (MODEL_DETECT_TIMEOUT s timeout)."""
        try:
            from openai import OpenAI as _OpenAI
            c = _OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=MODEL_DETECT_TIMEOUT)
            resp = c.models.list()
            return [m.id for m in resp.data]
        except Exception:
            return []
