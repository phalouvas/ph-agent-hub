# DeepSeek Stabilizer — PH Agent Hub

DeepSeek models are powerful but produce outputs that often break standard agent frameworks.  
The **DeepSeek Stabilizer** is a backend module designed to normalize, repair, and validate DeepSeek responses before they reach the agent loop or tool execution pipeline.

This document defines the stabilization strategy, required patches, and integration points.

---

# 1. Purpose of the Stabilizer

DeepSeek models frequently produce:

- Mixed reasoning + output (`<think>` tokens)
- Invalid or partial JSON
- Hallucinated tool names
- Incorrect tool argument structures
- Missing fields in tool calls
- Overly verbose reasoning
- Infinite or repeated agent loops
- Non‑schema‑compliant responses

The stabilizer ensures:

- Clean, valid JSON
- Valid tool calls
- Safe agent loop execution
- Predictable behavior
- Compatibility with the Microsoft Agent Framework

---

# 2. Stabilizer Responsibilities

The stabilizer performs the following tasks:

### **2.1 Strip Reasoning Tokens**
DeepSeek outputs internal thoughts inside `<think>` blocks.

The stabilizer removes:

- `<think> ... </think>`
- Any hidden reasoning tokens
- Any pre‑ or post‑amble reasoning

### **2.2 JSON Repair**
DeepSeek often returns:

- Missing braces
- Trailing commas
- Mixed text + JSON
- Incorrect quoting

The stabilizer uses:

- Regex cleanup
- JSON5‑style tolerant parsing
- Bracket balancing
- Key normalization

### **2.3 Tool Call Validation**
The stabilizer ensures:

- Tool name exists
- Tool is enabled for the tenant
- Arguments match expected schema
- No hallucinated fields
- No missing required fields

Invalid tool calls are:

- Repaired if possible
- Rejected with a fallback assistant message

### **2.4 Retry Logic**
If DeepSeek returns invalid output:

- Retry up to N times (configurable)
- Each retry includes a corrective system message
- Final fallback is a plain assistant message

### **2.5 Loop Protection**
DeepSeek sometimes loops in agent mode.

The stabilizer enforces:

- Max steps per agent run
- Max tool calls per message
- Max recursion depth

### **2.6 Output Normalization**
Ensures:

- Consistent JSON structure
- Consistent message format
- No stray text outside JSON
- No hallucinated metadata

---

# 3. Stabilizer Pipeline

```
Raw DeepSeek Output
        │
        ▼
[1] Strip reasoning tokens
        │
        ▼
[2] Extract JSON block
        │
        ▼
[3] Repair malformed JSON
        │
        ▼
[4] Validate tool calls
        │
        ▼
[5] Retry if invalid
        │
        ▼
[6] Normalize final output
        │
        ▼
Clean Agent Response
```

---

# 4. Integration Points

The stabilizer is applied in:

### **4.1 Model Adapter Layer**
Before returning model output to the agent loop.

### **4.2 Agent Loop**
Before executing tool calls.

### **4.3 Streaming Layer**
Filters out `<think>` tokens during streaming.

### **4.4 Error Handling**
Wraps DeepSeek errors with retry logic.

---

# 5. Stabilizer Configuration

Example configuration fields:

```
DEEPSEEK_MAX_RETRIES=3
DEEPSEEK_STRIP_REASONING=true
DEEPSEEK_VALIDATE_TOOL_CALLS=true
DEEPSEEK_JSON_REPAIR=true
```

---

# 6. Monkey‑Patching Strategy

The stabilizer is implemented as a set of monkey‑patches applied to:

### **6.1 Model Output Parser**
Override:
- `parse_output()`
- `extract_json()`
- `strip_reasoning()`

### **6.2 Tool Execution Validator**
Override:
- `validate_tool_call()`

### **6.3 Streaming Handler**
Override:
- `on_token()`

### **6.4 Agent Loop**
Override:
- `run_step()`
- `should_retry()`

All patches are isolated in:

```
/backend/src/agents/deepseek_patch.py
```

---

# 7. Example Stabilizer Behaviors

### **7.1 Remove reasoning**
Input:
```
<think>internal chain of thought</think>
{"tool": "erpnext.get_doc", "args": {...}}
```

Output:
```
{"tool": "erpnext.get_doc", "args": {...}}
```

---

### **7.2 Repair malformed JSON**
Input:
```
{ "tool": "erpnext.get_doc", "args": { "doctype": "Customer", } }
```

Output:
```
{ "tool": "erpnext.get_doc", "args": { "doctype": "Customer" } }
```

---

### **7.3 Validate tool name**
Input:
```
{"tool": "erpnext.get_docc", "args": {...}}
```

Output:
```
Error: Unknown tool "erpnext.get_docc"
```

---

### **7.4 Retry invalid output**
If DeepSeek returns:

```
I think the answer is...
```

The stabilizer retries with:

```
Return ONLY valid JSON. No text. No reasoning.
```

---

# 8. Goals of the Stabilizer

- Make DeepSeek reliable for agent workflows
- Prevent invalid tool calls
- Ensure schema‑compliant JSON
- Protect against infinite loops
- Provide predictable behavior for the Chat UI
- Maintain compatibility with the Agent Framework

The stabilizer is essential for production‑grade DeepSeek integration.
