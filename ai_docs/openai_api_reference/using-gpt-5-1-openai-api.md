# Using GPT-5.1 - OpenAI API

A comprehensive guide to GPT-5.1, OpenAI's newest flagship model from the GPT-5 model family.

---

## Overview

GPT-5.1 is the newest flagship model, part of the GPT-5 model family. Our most intelligent model yet, GPT-5.1 has similar training for:

- Code generation, bug fixing, and refactoring
- Instruction following
- Long context and tool calling

Unlike the previous GPT-5 model, GPT-5.1 has a new `none` reasoning setting for faster responses, increased steerability in model output, and new tools for coding use cases.

---

## Quickstart

### Basic Usage

**JavaScript (Node.js):**

```javascript
import OpenAI from "openai";

const openai = new OpenAI();

const result = await openai.responses.create({
  model: "gpt-5.1",
  input: "Write a haiku about code.",
  reasoning: { effort: "low" },
  text: { verbosity: "low" },
});

console.log(result.output_text);
```

**Python:**

```python
from openai import OpenAI

client = OpenAI()

result = client.responses.create(
    model="gpt-5.1",
    input="Write a haiku about code.",
    reasoning={"effort": "low"},
    text={"verbosity": "low"},
)

print(result.output_text)
```

**cURL:**

```bash
curl https://api.openai.com/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "gpt-5.1",
    "input": "Write a haiku about code.",
    "reasoning": { "effort": "low" }
  }'
```

### Using GPT-5.1-Codex-Max for Coding Tasks

**JavaScript (Node.js):**

```javascript
import OpenAI from "openai";

const openai = new OpenAI();

const result = await openai.responses.create({
  model: "gpt-5.1-codex-max",
  input: "Find the null pointer exception: ...your code here...",
  reasoning: { effort: "high" },
});

console.log(result.output_text);
```

---

## Meet the Models

There are three main models in the GPT-5 series:

| Model | Best For | Notes |
|-------|----------|-------|
| `gpt-5.1` | Most complex tasks requiring broad world knowledge | Replaces the previous `gpt-5` model |
| `gpt-5.1-codex-max` | Agentic coding tasks in Codex or Codex-like environments | Faster, more capable, more token-efficient for coding |
| `gpt-5-mini` | Well-defined tasks with lower cost/latency requirements | Trades some general world knowledge for efficiency |
| `gpt-5-nano` | Lightweight, cost-sensitive applications | Smallest model in the family |

---

## New Features in GPT-5.1

Just like GPT-5, the new GPT-5.1 has API features like custom tools, parameters to control verbosity and reasoning, and an allowed tools list. What's new in 5.1:

- A `none` setting for reasoning effort
- Increased steerability
- Two new tools for coding use cases (`apply_patch` and `shell`)

### Lower Reasoning Effort

The `reasoning.effort` parameter controls how many reasoning tokens the model generates before producing a response.

| Setting | Description |
|---------|-------------|
| `none` | **New in GPT-5.1** - Lowest latency, default setting |
| `low` | Favors speed and fewer tokens |
| `medium` | Balanced reasoning |
| `high` | Most thorough reasoning |

With GPT-5.1, the lowest setting is now `none` to provide lower-latency interactions. This is the default setting in GPT-5.1.

> **Tip:** With reasoning effort set to `none`, prompting is important. To improve the model's reasoning quality, encourage it to "think" or outline its steps before answering.

**Example - Reasoning Effort:**

```python
from openai import OpenAI

client = OpenAI()

response = client.responses.create(
    model="gpt-5.1",
    input="How much gold would it take to coat the Statue of Liberty in a 1mm layer?",
    reasoning={"effort": "none"}
)

print(response)
```

### Verbosity

Verbosity determines how many output tokens are generated. Lowering the number of tokens reduces overall latency.

| Setting | Use Case |
|---------|----------|
| `high` | Thorough explanations, extensive code refactoring |
| `medium` | Default - balanced output |
| `low` | Concise answers, simple code generation (e.g., SQL queries) |

**Example - Verbosity:**

```python
from openai import OpenAI

client = OpenAI()

response = client.responses.create(
    model="gpt-5",
    input="What is the answer to the ultimate question of life, the universe, and everything?",
    text={"verbosity": "low"}
)

print(response)
```

> **Note:** You can still steer verbosity through prompting after setting it to `low` in the API. The verbosity parameter defines a general token range at the system prompt level, but the actual output is flexible to both developer and user prompts within that range.

---

## New Tool Types in GPT-5.1

GPT-5.1 has been post-trained on specific tools commonly used in coding use cases.

### Apply Patch Tool

The `apply_patch` tool lets GPT-5.1 create, update, and delete files in your codebase using structured diffs. Instead of just suggesting edits, the model emits patch operations that your application applies and then reports back on, enabling iterative, multistep code editing workflows.

This is a new tool type in GPT-5.1, so you don't have to write custom descriptions for the tool. In testing, the named function decreased `apply_patch` failure rates by **35%**.

### Shell Tool

The shell tool allows the model to interact with your local computer through a controlled command-line interface. The model proposes shell commands; your integration executes them and returns the outputs. This creates a simple plan-execute loop that lets models inspect the system, run utilities, and gather data until they finish the task.

The shell tool is invoked in the same way as `apply_patch`: include it as a tool of type `shell`.

---

## Custom Tools

Custom tools let models send any raw text as tool call input but still constrain outputs if desired.

Define your tool with `type: custom` to enable models to send plaintext inputs directly to your tools, rather than being limited to structured JSON. The model can send any raw text—code, SQL queries, shell commands, configuration files, or long-form prose—directly to your tool.

**Example:**

```json
{
  "type": "custom",
  "name": "code_exec",
  "description": "Executes arbitrary python code"
}
```

### Context-Free Grammars (CFGs)

GPT-5.1 supports context-free grammars (CFGs) for custom tools, letting you provide a Lark grammar to constrain outputs to a specific syntax or DSL. Attaching a CFG (e.g., a SQL or DSL grammar) ensures the assistant's text matches your grammar.

**Best Practices:**

- Write concise, explicit tool descriptions. The model chooses what to send based on your description; state clearly if you want it to always call the tool.
- Validate outputs on the server side. Freeform strings are powerful but require safeguards against injection or unsafe commands.

---

## Allowed Tools

The `allowed_tools` parameter under `tool_choice` lets you pass N tool definitions but restrict the model to only M (< N) of them.

List your full toolkit in `tools`, and then use an `allowed_tools` block to name the subset and specify a mode:

| Mode | Behavior |
|------|----------|
| `auto` | The model may pick any of the allowed tools |
| `required` | The model must invoke one of the allowed tools |

**Example:**

```json
{
  "tool_choice": {
    "type": "allowed_tools",
    "mode": "auto",
    "tools": [
      { "type": "function", "name": "get_weather" },
      { "type": "function", "name": "search_docs" }
    ]
  }
}
```

By separating all possible tools from the subset that can be used now, you gain greater safety, predictability, and improved prompt caching.

---

## Preambles

Preambles are brief, user-visible explanations that GPT-5.1 generates before invoking any tool or function, outlining its intent or plan (e.g., "why I'm calling this tool"). They appear after the chain-of-thought and before the actual tool call.

**Benefits:**

- Transparency into the model's reasoning
- Enhanced debuggability
- User confidence
- Fine-grained steerability

**How to enable:** Add a system or developer instruction—for example: "Before you call a tool, explain why you are calling it." GPT-5.1 prepends a concise rationale to each specified tool call.

---

## Migration Guidance

GPT-5.1 is our best model yet, and it works best with the Responses API, which supports passing chain of thought (CoT) between turns.

### Migrating from Other Models to GPT-5.1

| Current Model | Migration Path |
|---------------|----------------|
| `gpt-5` | `gpt-5.1` with default settings is a drop-in replacement |
| `o3` | `gpt-5.1` with `medium` or `high` reasoning. Start with `medium` reasoning with prompt tuning, then increase to `high` if needed |
| `gpt-4.1` | `gpt-5` with `none` reasoning. Start with `none` and tune your prompts |
| `o4-mini` / `gpt-4.1-mini` | `gpt-5-mini` with prompt tuning |
| `gpt-4.1-nano` | `gpt-5-nano` with prompt tuning |

### GPT-5.1 Parameter Compatibility

> ⚠️ **Important:** The following parameters are **only supported** when using GPT-5.1 with reasoning effort set to `none`:
> - `temperature`
> - `top_p`
> - `logprobs`

Requests to GPT-5.1 with any other reasoning effort setting, or to other GPT-5 models (e.g., `gpt-5`, `gpt-5-mini`, `gpt-5-nano`) that include these fields will raise an error.

**Alternative Parameters:**

| Goal | Parameter |
|------|-----------|
| Reasoning depth | `reasoning: { effort: "none" \| "low" \| "medium" \| "high" }` |
| Output verbosity | `text: { verbosity: "low" \| "medium" \| "high" }` |
| Output length | `max_output_tokens` |

---

## Migrating from Chat Completions to Responses API

The biggest difference, and main reason to migrate from Chat Completions to the Responses API for GPT-5.1, is support for passing chain of thought (CoT) between turns.

**Benefits of Responses API:**

- Improved intelligence
- Fewer generated reasoning tokens
- Higher cache hit rates
- Lower latency

### Parameter Comparison

**Reasoning Effort - Responses API:**

```bash
curl --request POST \
  --url https://api.openai.com/v1/responses \
  --header "Authorization: Bearer $OPENAI_API_KEY" \
  --header 'Content-type: application/json' \
  --data '{
    "model": "gpt-5.1",
    "input": "How much gold would it take to coat the Statue of Liberty in a 1mm layer?",
    "reasoning": { "effort": "none" }
  }'
```

**Reasoning Effort - Chat Completions API:**

```bash
curl --request POST \
  --url https://api.openai.com/v1/chat/completions \
  --header "Authorization: Bearer $OPENAI_API_KEY" \
  --header 'Content-type: application/json' \
  --data '{
    "model": "gpt-5.1",
    "messages": [
      { "role": "user", "content": "How much gold would it take to coat the Statue of Liberty in a 1mm layer?" }
    ],
    "reasoning_effort": "none"
  }'
```

---

## Prompting Guidance

We specifically designed GPT-5.1 to excel at coding and agentic tasks. We also recommend iterating on prompts for GPT-5.1 using the **prompt optimizer**.

### GPT-5.1 is a Reasoning Model

Reasoning models like GPT-5.1 break problems down step by step, producing an internal chain of thought that encodes their reasoning.

**To maximize performance:**

1. Pass reasoning items back to the model to avoid re-reasoning
2. In multi-turn conversations, passing a `previous_response_id` automatically makes earlier reasoning items available
3. This is especially important when using tools—for example, when a function call requires an extra round trip
4. Either include them with `previous_response_id` or add them directly to `input`

---

## FAQ

### How are these models integrated into ChatGPT?

In ChatGPT, there are two models: **GPT-5.1 Instant** and **GPT-5.1 Thinking**. They offer reasoning and minimal-reasoning capabilities, with a routing layer that selects the best model based on the user's question. Users can also invoke reasoning directly through the ChatGPT UI.

### Will these models be supported in Codex?

Yes, `gpt-5.1-codex-max` is the model that powers Codex and Codex CLI. You can also use this as a standalone model for building agentic coding applications.

### How does GPT-5.1 compare to GPT-5-Codex?

**GPT-5.1-Codex-Max** was specifically designed for use in Codex. Unlike GPT-5.1, which is a general-purpose model, we recommend using GPT-5.1-Codex-Max only for agentic coding tasks in Codex or Codex-like environments, and GPT-5.1 for use cases in other domains.

GPT-5.1-Codex-Max is only available in the Responses API and supports:
- `none`, `medium`, `high`, and `xhigh` reasoning effort settings
- Function calling
- Structured outputs
- Compaction
- The `web_search` tool

### What is the deprecation plan for previous models?

Any model deprecations will be posted on our deprecations page. We'll send advanced notice of any model deprecations.

---

## Further Reading

- [GPT-5.1 Prompting Guide](https://platform.openai.com/docs/guides/gpt-5-1-prompting)
- [GPT-5.1-Codex-Max Integration Guide](https://platform.openai.com/docs/guides/codex-max)
- [GPT-5 Frontend Guide](https://platform.openai.com/docs/guides/gpt-5-frontend)
- [GPT-5 New Features Guide](https://platform.openai.com/docs/guides/gpt-5-features)
- [Cookbook on Reasoning Models](https://cookbook.openai.com/reasoning)
- [Comparison of Responses API vs. Chat Completions](https://platform.openai.com/docs/guides/responses-vs-completions)
