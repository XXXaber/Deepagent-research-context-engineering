# AGENTS.md - Deep Agents UI

> **Component**: `deep-agents-ui/`
> **Type**: Next.js 16 React Frontend
> **Role**: Chat interface for LangGraph DeepAgents

---

## 1. Module Purpose

React-based chat UI that connects to a LangGraph backend. Displays agent messages, tool calls, SubAgent activity, tasks/files sidebar, and handles human-in-the-loop interrupts.

---

## 2. Quick Start

```bash
yarn install
yarn dev          # localhost:3000
```

Configure via Settings dialog:
- **Deployment URL**: `http://127.0.0.1:2024` (LangGraph dev server)
- **Assistant ID**: `research` (or UUID)

---

## 3. Directory Structure

```
src/
  app/
    page.tsx              # Main entry, config handling
    layout.tsx            # Root layout with providers
    components/
      ChatInterface.tsx   # Message input/display area
      ChatMessage.tsx     # Individual message rendering
      ToolCallBox.tsx     # Tool invocation display
      SubAgentIndicator.tsx  # Active SubAgent status
      TasksFilesSidebar.tsx  # TODO list + file tree
      ThreadList.tsx      # Conversation history
      ToolApprovalInterrupt.tsx  # HITL approval UI
      ConfigDialog.tsx    # Settings modal
      FileViewDialog.tsx  # File content viewer
      MarkdownContent.tsx # Markdown renderer

  components/ui/          # Radix UI primitives (shadcn)
  providers/
    ChatProvider.tsx      # Chat state context
    ClientProvider.tsx    # LangGraph SDK client
  lib/
    config.ts             # LocalStorage config persistence
```

---

## 4. Key Components

| Component | Function |
|-----------|----------|
| `ChatProvider` | Manages message state, streaming, thread lifecycle |
| `ClientProvider` | Wraps `@langchain/langgraph-sdk` client |
| `ChatInterface` | Main chat view with input area |
| `ToolCallBox` | Renders tool name, args, result with syntax highlighting |
| `SubAgentIndicator` | Shows which SubAgent is currently active |
| `ToolApprovalInterrupt` | Human-in-the-loop approval/rejection UI |

---

## 5. State Management

| State | Location | Persistence |
|-------|----------|-------------|
| Config | `lib/config.ts` | LocalStorage |
| Thread ID | URL query param `?threadId=` | URL |
| Sidebar | URL query param `?sidebar=` | URL |
| Messages | `ChatProvider` context | Server (LangGraph) |

---

## 6. Styling

- **TailwindCSS** with custom theme
- **shadcn/ui** components (Radix primitives)
- **Dark mode** via CSS variables

---

## 7. Development Commands

```bash
yarn dev          # Start dev server (port 3000)
yarn build        # Production build
yarn lint         # ESLint
yarn format       # Prettier
```

---

## 8. Backend Connection

The UI connects to LangGraph API endpoints:
- `POST /threads` - Create thread
- `POST /threads/{id}/runs` - Stream messages
- `GET /assistants/{id}` - Fetch assistant config

Configured via `ClientProvider` with deployment URL and optional LangSmith API key.

---

## 9. Extension Points

| Task | Where to Modify |
|------|-----------------|
| Add new message type | `ChatMessage.tsx` + type in `ChatProvider` |
| Custom tool rendering | `ToolCallBox.tsx` |
| New sidebar panel | `TasksFilesSidebar.tsx` |
| Theme customization | `tailwind.config.js` + `globals.css` |
