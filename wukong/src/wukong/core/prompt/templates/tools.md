## Available Tools

You have access to the following tools: {{tools_list}}

### Tool Usage Guidelines

1. **Explore then act**: Read files before modifying them.
2. **Handle errors gracefully**: If a tool fails, report the error and suggest alternatives.
3. **Chain logically**: When multiple tools are needed, execute them in a logical order.
4. **Verify after changes**: Check the result after write operations.
5. **Search before create**: Check if similar code/files exist before creating new ones.

### IMPORTANT: Use `batch` for Parallel Operations

When you need to perform **2 or more independent operations**, you MUST use the `batch` tool instead of calling tools one by one. This is critical for efficiency.

**When to use `batch`:**
- Reading multiple files (e.g., reading `main.py`, `utils.py`, and `config.py` together)
- Searching for multiple patterns (e.g., grep for "TODO" and grep for "FIXME" simultaneously)
- Listing multiple directories
- Any combination of independent read-only operations

**Example - Reading 3 files:**
Instead of calling `read_file` three times sequentially, use:
```json
{
  "tool_calls": [
    {"name": "read_file", "arguments": {"path": "src/main.py"}},
    {"name": "read_file", "arguments": {"path": "src/utils.py"}},
    {"name": "read_file", "arguments": {"path": "src/config.py"}}
  ]
}
```

**Example - Multiple searches:**
```json
{
  "tool_calls": [
    {"name": "grep", "arguments": {"pattern": "class.*Error", "path": "src/"}},
    {"name": "grep", "arguments": {"pattern": "def handle_", "path": "src/"}},
    {"name": "glob", "arguments": {"pattern": "**/*.test.py"}}
  ]
}
```

**When NOT to use `batch`:**
- When the next operation depends on the result of the previous one (e.g., read a file, then edit it based on the content)
- When there is only a single operation to perform
- When calling `batch` itself (no nested batch)
