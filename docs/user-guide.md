# End User Guide — PH Agent Hub

This guide is for end users (`user` role) who use PH Agent Hub to chat with AI agents. It covers everything you can do in the chat area — from starting your first conversation to using advanced features like branching, memory, and file uploads.

---

## 1. Getting Started

### 1.1 Logging In

1. Open the PH Agent Hub web app in your browser
2. Enter your email and password
3. Click **Log In**

Your login persists across page reloads — you won't need to re-enter your credentials until your session expires.

### 1.2 The Chat Area

After logging in, you'll see the chat area with:
- **Left sidebar**: Your session list, search bar, and new session button
- **Main area**: The active conversation
- **Top bar**: Model selector, template selector, and session controls
- **Input area**: Message composer with skill selector, tool manager, file upload, and memory buttons

---

## 2. Chat Sessions

### 2.1 Create a Session

Click **New Session** in the left sidebar, or start typing a message — a session is created automatically.

Sessions can be:
- **Permanent**: Saved to the database. Appears in your session list. Supports all features.
- **Temporary**: Lives only in Redis. Disappears after inactivity. Does not support file uploads, branching, or editing.

### 2.2 Pin a Session

Click the pin icon on any session to keep it at the top of your session list.

### 2.3 Rename a Session

Click the session title to edit it directly. Good titles help you find conversations later.

### 2.4 Search Sessions

Use the search bar at the top of the session sidebar. Search matches both session titles and message content.

---

## 3. Chatting with AI

### 3.1 Send a Message

Type your message in the input box at the bottom and press **Enter** (or click Send). The AI responds in real time — you'll see tokens appear as they're generated.

### 3.2 Streaming Responses

Responses stream live via Server-Sent Events (SSE). You'll see:
- **Tokens** appearing word by word as the AI generates them
- **Tool calls** — when the agent uses an activated tool, you'll see what it's doing
- **Step completion** — when a tool call finishes

### 3.3 Stop Generation

Click the **Stop** button while the AI is responding to cancel generation. The partial response is saved.

---

## 4. Model Selection

Use the model selector in the top bar to choose which AI model to use. You can only select from models that:
- Your administrator has enabled for your tenant
- Are currently active

Different models have different strengths — try a few to find what works best for your use case.

---

## 5. Templates, Prompts & Skills

### 5.1 Templates

Templates are curated by administrators. They define the AI's behavior — its system prompt, default model, and available tools. Select a template from the dropdown to apply its configuration to your session.

### 5.2 Prompts

Prompts are reusable message templates you create yourself. Save commonly used instructions or question formats as prompts, then insert them into any session.

**Create a prompt:**
1. Click the prompts menu
2. Click **New Prompt**
3. Give it a title and content
4. Save

Your prompts are private — only you can see and use them.

### 5.3 Skills

Skills are reusable execution profiles that bundle model, template, and tool defaults. Selecting a skill changes how the agent behaves — it might switch to a specialized persona or a multi-step workflow.

There are two types of skills:
- **Prompt Based** — A conversational agent with a specific system prompt (from a template), tools, and model. Best for domain-specific assistants like "Tax Advisor" or "Code Reviewer".
- **Workflow Based** — A multi-step orchestration that can coordinate multiple agents, branch on conditions, and wait for human approval. Best for business processes like invoice processing or multi-agent research.

**Create a personal skill:**
1. Click the skills menu (gear icon next to the skill selector)
2. Click **New Skill**
3. Choose the execution type:
   - **Prompt Based**: Select a Template (provides the system prompt), optionally pick a default model
   - **Workflow Based**: Enter the MAF Target Key that matches a registered workflow
4. Optionally add a description
5. Save

Tenant skills (created by admins) are available to everyone in your tenant. You can view and select them but cannot edit or delete them.

---

## 6. Tools

Tools let the AI interact with external systems — query databases, call APIs, or perform actions.

### 6.1 Activate Tools

1. Click the **Tools** button in the input area
2. Toggle on the tools you want the AI to use in this session
3. The AI will now be able to call these tools when relevant

You can only activate tools that your administrator has approved for your tenant.

### 6.2 Always-On Tools

You can mark a tool as **always-on** — it will be automatically activated for every new session you create. In the tool selector, toggle the always-on switch next to a tool. Your preference is saved and applied to all future sessions.

### 6.3 Deactivate Tools

Toggle a tool off to prevent the AI from using it. The change takes effect immediately.

---

## 7. File Uploads

You can attach files to your chat sessions for the AI to reference.

### 7.1 Upload a File

1. Click the **Upload** (paperclip) button in the input area
2. Select a file from your computer
3. The file is uploaded and attached to the current session

**Supported file types**: Plain text, CSV, Markdown, PDF, JSON, PNG, JPEG, GIF, WebP.
**Maximum file size**: 20 MB.

### 7.2 File Limitations

- File uploads are only available for **permanent sessions** (not temporary ones)
- Uploaded files are stored securely and scoped to your session

### 7.3 Delete an Upload

Hover over an uploaded file in the session and click the delete icon. The file is removed from storage.

---

## 8. Memory

Memory lets the AI remember information across sessions. Think of it as a persistent notepad the AI can reference.

### 8.1 View Memory

Click the **Memory** button to see all stored memory entries.

### 8.2 Add Memory

1. Click **Add Memory**
2. Enter the information you want the AI to remember
3. Save

### 8.3 Edit Memory

Click any memory entry to edit its key or value inline. Changes take effect immediately.

### 8.4 Delete Memory

Click the delete icon on any memory entry to remove it. The AI will no longer reference it.

Memory is private to you — no other user can see your memory entries.

---

## 9. Message Actions

### 9.1 Edit a Message

1. Hover over your message
2. Click the **Edit** (pencil) icon
3. Modify the text and save

The original user message and its assistant response are replaced. The conversation stays linear — your edit becomes the new history.

### 9.2 Regenerate a Response

Click the **Regenerate** icon on an assistant message to get a new response to the same prompt. The old response is replaced with a fresh one — the conversation stays linear.

### 9.3 Delete a Message

Click the **Delete** (trash) icon on any message to permanently remove it from the conversation. Both the message and any attached file uploads are deleted.

### 9.4 Message Feedback

Click **thumbs up** or **thumbs down** on any assistant message to provide feedback. This helps administrators understand model performance.

---

## 10. Auto-Tagging & Follow-Up Questions

### 10.1 Auto-Tagging

After each agent response, the session is automatically labeled with 3–5 topic tags (e.g., "programming", "data analysis", "erpnext"). These tags appear in the session sidebar and help you find conversations later. Tags are displayed as colored badges below the session title.

### 10.2 Follow-Up Questions

After each response, three suggested follow-up questions appear below the assistant message. Click any question to ask it instantly. This feature is enabled per-model by your administrator — not all models generate follow-up questions.

---

## 11. Thinking Mode

> Available for DeepSeek models only.

When enabled, you'll see the model's internal reasoning process before the final answer. The reasoning appears in an expandable panel labeled **Reasoning**. This is useful for understanding *how* the model arrived at its answer, especially for complex or multi-step problems.

Toggle thinking mode in your session settings. Your administrator controls whether a model supports this feature.

---

## 12. Tips & Best Practices

- **Use descriptive session titles** — it makes searching and organizing much easier
- **Pin important sessions** — they stay at the top of your list
- **Use memory for cross-session context** — the AI will remember preferences and facts
- **Mark frequently-used tools as always-on** — they'll be active in every new session automatically
- **Try different models** — some are better at coding, others at writing or analysis
- **Experiment with skills** — skills can dramatically change the AI's capabilities
- **Activate tools only when needed** — unnecessary tools can slow down responses
- **Use prompts for repeated workflows** — save time by reusing common instructions
- **Branch instead of deleting** — editing creates branches, preserving your history
- **Use temporary sessions for quick, disposable chats** — they leave no trace

---

## 13. Troubleshooting

### The AI isn't responding

- Check your internet connection
- Wait a moment — some models take longer to process
- Click **Stop** and try again

### I can't see certain models

Only models enabled by your administrator for your tenant appear in the selector. Contact your admin if you need access to a specific model.

### My file won't upload

- Check the file type is supported (see §7.1)
- Check the file is under 20 MB
- Make sure you're in a permanent session, not a temporary one

### I see an error message

Error messages appear inline in the chat. They usually include details about what went wrong. If errors persist, contact your administrator.
