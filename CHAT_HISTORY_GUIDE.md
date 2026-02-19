# Chat History Implementation in Policy Chatbot

## 🎯 **How Chat History Works**

Your Policy Chatbot uses **backend-managed chat history** with LangChain. The frontend **does NOT** need to send all previous messages - the backend automatically handles conversation context.

## 📡 **API Flow**

### **Frontend Responsibilities:**
1. **Send only the current message** in each request
2. **Provide a consistent session_id** for the conversation
3. **Receive the response** with full context awareness

### **Backend Responsibilities:**
1. **Store conversation history** in memory (per session)
2. **Automatically inject previous messages** into LLM prompts
3. **Maintain context** across multiple turns
4. **Handle session management** and cleanup

## 🔧 **Technical Implementation**

### **1. Session-Based Storage (In-Memory)**

```python
# Location: apps/chatbot/services/chat_history.py

class LangChainChatMessageHistory:
    def __init__(self, session_id: str, max_messages: int = 100):
        self.session_id = session_id
        self._messages: List[BaseMessage] = []  # Stores all conversation
        self.max_messages = max_messages
        
    def add_message(self, message: BaseMessage):
        # Automatically evicts old messages when limit reached
        if len(self._messages) >= self.max_messages:
            self._messages = self._messages[-(self.max_messages - 1):]
        self._messages.append(message)
```

### **2. API Request Format**

```json
{
    "message": "What are the working hours?",
    "session_id": "user-123-conversation", 
    "include_sources": true
}
```

**Note:** Frontend only sends the current message - no previous context needed!

### **3. Backend Processing Flow**

```python
# 1. Extract user message and session_id
user_message = "What are the working hours?"
session_id = "user-123-conversation"

# 2. Search for relevant documents  
search_results = search_service.search(query=user_message, limit=5)

# 3. LangChain automatically retrieves previous messages for this session
conversation_chain = RunnableWithMessageHistory(
    chain,
    get_session_history_for_langchain,  # Auto-retrieves session history
    input_messages_key="input",
    history_messages_key="history",
)

# 4. Generate response with full conversation context
response = conversation_chain.invoke(
    {"input": user_message, "context": document_context},
    config={"configurable": {"session_id": session_id}}
)

# 5. Store new messages in session history (automatic)
# - User message and AI response are automatically stored
```

### **4. LangChain Prompt Template**

```python
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant..."),
    MessagesPlaceholder(variable_name="history"),  # Previous conversation
    ("human", "{input}"),  # Current user message
])
```

## 💬 **Conversation Example**

### **Turn 1:**
```bash
POST /api/v1/chat/
{
    "message": "What are the working hours?",
    "session_id": "user-abc-123"
}

# Backend processes:
# - History: [] (empty)
# - Current: "What are the working hours?"
# - Stores: [HumanMessage, AIMessage]
```

### **Turn 2:**
```bash  
POST /api/v1/chat/
{
    "message": "What about vacation days?",  # No context needed!
    "session_id": "user-abc-123"           # Same session
}

# Backend processes:
# - History: [Previous HumanMessage, Previous AIMessage] 
# - Current: "What about vacation days?"
# - LLM sees full context automatically
```

### **Turn 3:**
```bash
POST /api/v1/chat/
{
    "message": "How many days exactly?",    # Follow-up question
    "session_id": "user-abc-123"
}

# Backend processes:  
# - History: [All previous messages in conversation]
# - Current: "How many days exactly?"
# - LLM understands "days" refers to vacation days from context
```

## 🏗️ **Session Management**

### **Session Storage Configuration:**
```python
DEFAULT_MAX_SESSIONS = 1000              # Max concurrent sessions
DEFAULT_MAX_MESSAGES_PER_SESSION = 100  # Max messages per session  
DEFAULT_SESSION_TTL_SECONDS = 3600      # 1 hour expiry
```

### **Automatic Cleanup:**
- **LRU Eviction**: Oldest sessions removed when limit reached
- **TTL Expiry**: Sessions expire after 1 hour of inactivity  
- **Message Limits**: Oldest messages evicted when per-session limit reached

### **Thread Safety:**
- Uses threading locks for concurrent access
- Safe for multiple simultaneous conversations

## 🔍 **Session Stats API**

```bash
GET /api/v1/chat/stats/
```

```json
{
    "status": "success",
    "stats": {
        "active_sessions": 25,
        "total_messages": 150,
        "max_sessions": 1000,
        "max_messages_per_session": 100,
        "session_ttl_seconds": 3600,
        "langchain_enabled": true
    }
}
```

## 🚀 **Benefits of Backend-Managed History**

### **For Frontend:**
✅ **Simplicity**: Only send current message
✅ **Performance**: No need to send large conversation history  
✅ **Reliability**: Backend handles context management
✅ **Consistency**: Same session_id maintains context

### **For Backend:**
✅ **Control**: Manage conversation length and memory
✅ **Optimization**: Efficient context window management
✅ **Security**: Validate and sanitize all messages
✅ **Analytics**: Track conversation patterns

## 🔧 **Frontend Implementation Example**

```javascript
class ChatService {
    constructor() {
        this.sessionId = 'user-' + Math.random().toString(36).substr(2, 9);
        this.apiKey = 'Sample Organization'; // Your org identifier
    }
    
    async sendMessage(message) {
        const response = await fetch('/api/v1/chat/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': this.apiKey
            },
            body: JSON.stringify({
                message: message,           // Only current message!
                session_id: this.sessionId, // Consistent session ID
                include_sources: true
            })
        });
        
        return response.json(); // Backend provides full context-aware response
    }
}

// Usage:
const chat = new ChatService();

// Turn 1 - No previous context needed
await chat.sendMessage("What are the working hours?");

// Turn 2 - Backend remembers previous conversation  
await chat.sendMessage("What about vacation days?");

// Turn 3 - Follow-up works automatically
await chat.sendMessage("How many days do I get?");
```

## ⚙️ **Configuration Options**

In your Django settings:

```python
# Enable/disable chat history
CHATBOT_ENABLE_CHAT_HISTORY = True

# LLM Provider settings
CHATBOT_LLM_PROVIDER = "ollama"  # or "openai"
CHATBOT_LLM_MODEL = "mistral"

# Context limits
CHATBOT_MAX_CONTEXT_CHARS = 8000

# Ollama settings
OLLAMA_BASE_URL = "http://localhost:11434"

# OpenAI settings (if using OpenAI)
OPENAI_API_KEY = "your-api-key"
```

## 🎯 **Key Takeaway**

**The frontend NEVER sends conversation history!** 

The backend automatically manages all conversation context using:
1. **Session IDs** to group related messages
2. **LangChain's message history** for context injection  
3. **In-memory storage** for fast access
4. **Automatic cleanup** for memory management

This design provides a clean API while maintaining rich conversational context! 🎉
