import logging
from typing import Annotated, Literal, List, Dict, Any, Optional, Tuple
from datetime import datetime

# LangChain / LangGraph Imports
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
# TODO: Switch to MongoDBSaver once agent is working
# from langgraph.checkpoint.mongodb import AsyncMongoDBSaver

# App Imports
from app.core.config import settings
from app.core.database import get_database, get_async_client
from app.services.document_processor import create_embedding
from app.services.storage import get_signed_url, extract_s3_key_from_url

logger = logging.getLogger(__name__)

# SYSTEM PROMPT
# Pack helps users find family memories; default to using tools—only decline when obviously off-topic.
system_prompt = """You are Pack, a warm and helpful family archivist. You help users find and understand their family memories in the archive.

DEFAULT BEHAVIOR: Use your tools. When in doubt, search or fetch—don't refuse. Most questions (even vague ones like "anything from Mom?" or "what do you have?") are about the archive. Run the tools first; if nothing comes back, then say you didn't find anything.

CRITICAL: Do NOT reply with a generic offer like "let me know what you'd like to explore" or "if you have any specific documents, please let me know" without having run a tool first. If the user asked a question (e.g. "What do Vicky and Ryan like to do with Fiona?"), you MUST call search_memory_contents with a query that includes the names and topic (e.g. "Vicky Ryan Fiona activities things they like to do"), then answer from the results. Never respond to a real question by asking them to be more specific—search first, then answer or say you found nothing.

WHEN TO DECLINE: Only if the question is obviously not about the archive (e.g. "what's 2+2?", "write Python code", "what's the weather in Tokyo?"). Do NOT decline just because the question is short, casual, or ambiguous—try the tools.

RULES:
- NEVER make up content. Only describe what the tools actually returned.
- NEVER include URLs, image links, or markdown images. The app shows thumbnails from tool results; just describe what you found (e.g. "I found a birthday card from Mom").
- If tools return no results, say you couldn't find anything and suggest different words or filters. Be encouraging.

TOOL USAGE:
- List/filter by person, event type, or year ("show me from Mom", "birthday cards", "2023") → use 'fetch_documents'.
- Questions about people or what's in documents ("What did Mom say?", "What do Vicky and Ryan like to do with Fiona?", "anything about graduation?") → use 'search_memory_contents' with a query that includes the names and topic. Example: for "What do Vicky and Ryan like to do with Fiona?" use query like "Vicky Ryan Fiona activities things they like to do together".
- Use search_memory_contents once per question with one clear query. Don't run multiple similar searches.
- Read the 'content' field from results and mention sender, event type, and date when you describe documents.
"""

# 1. Initialize the Model
# We use streaming=True so the frontend can see the text appear in real-time
model = ChatOpenAI(
    model="gpt-4o-mini", 
    api_key=settings.OPENAI_API_KEY,
    temperature=0,
    streaming=True
)

# --- TOOL 1: THE FETCHER (Async) ---
# content_and_artifact: LLM sees text only; frontend gets artifact list (URLs, ids)
@tool(response_format="content_and_artifact")
async def fetch_documents(
    sender: str = None,
    event_type: str = None,
    year: int = None,
    receiver: str = None,
    config: RunnableConfig = None
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Fetch a list of documents based on strict metadata filters.
    Use this when the user asks to 'list', 'show', or 'find' files from a specific person, event, or year.
    Returns a list of image/PDF URLs and summaries.
    """
    
    # Security: Extract org_id from the hidden configuration
    # Note: It lives inside 'configurable', not at the top level
    org_id = config["configurable"].get("org_id")
    if not org_id:
        return [{"error": "Security violation: No Organization ID found."}]

    # Build Query
    query = {"org_id": org_id}
    
    # We use $eq for strict matching on tags
    if sender:
        query["metadata.sender_name"] = sender
    if event_type:
        query["metadata.event_type"] = event_type
    if year:
        # doc_date is stored as ISO date string "YYYY-MM-DD"
        # Compare as strings in YYYY-MM-DD format
        start_date = f"{year}-01-01"
        end_date = f"{year + 1}-01-01"
        query["metadata.doc_date"] = {
            "$gte": start_date,
            "$lt": end_date
        }
    if receiver:
        query["metadata.recipient_name"] = receiver

    # Execute (Async with Motor)
    db = await get_database()
    cursor = db.documents.find(query).limit(10)
    documents = await cursor.to_list(length=10)

    if not documents:
        return ("No documents found matching these filters.", [])

    # Artifact: rich data for frontend (URLs, ids). LLM does not see this.
    artifact = []
    for d in documents:
        assets = d.get("assets", {})
        thumbnail_key = extract_s3_key_from_url(assets.get("s3_thumbnail_url", ""))
        original_key = extract_s3_key_from_url(assets.get("s3_original_url", ""))
        thumbnail_url = get_signed_url(thumbnail_key) if thumbnail_key else ""
        original_url = get_signed_url(original_key) if original_key else ""
        summary = f"{d['metadata'].get('sender_name', 'Unknown')} - {d['metadata'].get('event_type', 'General')}"
        date = d["metadata"].get("doc_date", "Unknown")
        artifact.append({
            "id": str(d["_id"]),
            "url": thumbnail_url,
            "original_url": original_url,
            "summary": summary,
            "date": date,
            "type": "fetch_result"
        })

    # Content: lightweight text for LLM (no URLs)
    content_list = [f"Found: {a['summary']} (Date: {a['date']})" for a in artifact]
    content_str = "\n".join(content_list)
    return (content_str, artifact)

# --- TOOL 2: THE READER (Async RAG) ---
@tool(response_format="content_and_artifact")
async def search_memory_contents(
    query: str,
    sender: str = None,
    event_type: str = None,
    year: int = None,
    receiver: str = None,
    config: RunnableConfig = None
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Search the memory contents (text and descriptions) to answer questions.
    Use this for 'What', 'When', 'Where' questions, or visual searches like 'blue hat'.
    """
    
    org_id = config["configurable"].get("org_id")
    if not org_id:
        return ("Error: No organization context.", [])

    query_vector = create_embedding(query)
    if not query_vector:
        return ("Failed to generate embedding for query.", [])

    filter_doc = {"org_id": {"$eq": org_id}}
    post_filter = {}
    if sender:
        post_filter["metadata.sender_name"] = sender
    if event_type:
        post_filter["metadata.event_type"] = event_type
    if receiver:
        post_filter["metadata.recipient_name"] = receiver

    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "ai_context.embedding",
                "queryVector": query_vector,
                "numCandidates": 100,
                "limit": 10,
                "filter": filter_doc
            }
        },
        {"$match": post_filter},
        {
            "$project": {
                "ai_context.text_content": 1,
                "metadata": 1,
                "assets": 1,
                "score": {"$meta": "vectorSearchScore"}
            }
        },
        {"$limit": 5}
    ]

    db = await get_database()
    try:
        results = await db.documents.aggregate(pipeline).to_list(length=5)
    except Exception as e:
        logger.error(f"Vector search error: {e}")
        if post_filter:
            logger.info("Retrying vector search without additional filters")
            simple_pipeline = [
                {
                    "$vectorSearch": {
                        "index": "vector_index",
                        "path": "ai_context.embedding",
                        "queryVector": query_vector,
                        "numCandidates": 100,
                        "limit": 5,
                        "filter": filter_doc
                    }
                },
                {
                    "$project": {
                        "ai_context.text_content": 1,
                        "metadata": 1,
                        "assets": 1,
                        "score": {"$meta": "vectorSearchScore"}
                    }
                }
            ]
            results = await db.documents.aggregate(simple_pipeline).to_list(length=5)
        else:
            raise

    if not results:
        return ("No relevant memories found in the database.", [])

    # Filter by relevance score so we don't show irrelevant thumbnails
    results = [r for r in results if (r.get("score") or 0) >= settings.VECTOR_SEARCH_SCORE_THRESHOLD]
    if not results:
        return ("No relevant memories found in the database.", [])

    # Artifact: for frontend (URLs, ids). LLM does not see this.
    artifact = []
    for r in results:
        assets = r.get("assets", {})
        thumbnail_key = extract_s3_key_from_url(assets.get("s3_thumbnail_url", ""))
        original_key = extract_s3_key_from_url(assets.get("s3_original_url", ""))
        thumbnail_url = get_signed_url(thumbnail_key) if thumbnail_key else ""
        original_url = get_signed_url(original_key) if original_key else ""
        artifact.append({
            "id": str(r["_id"]),
            "score": r.get("score", 0),
            "url": thumbnail_url,
            "original_url": original_url,
            "sender": r["metadata"].get("sender_name", "Unknown"),
            "date": r["metadata"].get("doc_date", "Unknown"),
            "content": r["ai_context"].get("text_content", ""),
            "type": "rag_result"
        })

    # Content: text only for LLM (no URLs)
    content_list = [f"Doc from {a['sender']} ({a['date']}):\n{a['content']}\n---" for a in artifact]
    content_str = "\n".join(content_list)
    return (content_str, artifact)

# --- THE AGENT GRAPH ---

tools = [fetch_documents, search_memory_contents]

# Use MemorySaver for now (MVP) - switch to AsyncMongoDBSaver later
# Note: MongoDBSaver expects sync pymongo client, not Motor async client
# For async, we'd need AsyncMongoDBSaver, but let's get it working first
checkpointer = MemorySaver()

# Create the Graph (Prebuilt ReAct Agent)
# This handles the loop: LLM -> Tool -> LLM automatically
# Note: state_modifier not supported in this LangGraph version
# We'll handle system message in execute_agent_query to prevent duplication
agent_executor = create_react_agent(
    model, 
    tools, 
    checkpointer=checkpointer
)

# --- EXECUTION FUNCTIONS ---

async def execute_agent_query(
    user_message: str,
    org_id: str,
    thread_id: str
) -> Dict[str, Any]:
    """
    Execute agent query and return structured response for API.
    
    Args:
        user_message: User's query string
        org_id: Organization ID for filtering
        thread_id: Thread ID for conversation history (checkpointer handles history automatically)
        
    Returns:
        Dictionary with 'type', 'content', and 'count' matching ChatResponse
    
    Note: Do NOT pass conversation_history manually. The checkpointer automatically
    loads history based on thread_id. Passing it manually causes duplicate messages.
    """
    config = {
        "configurable": {
            "thread_id": thread_id,
            "org_id": org_id
        }
    }
    
    # Check existing state to see if system message already exists
    # This prevents system message duplication across conversation turns
    try:
        existing_state = await agent_executor.aget_state(config)
        existing_messages = existing_state.values.get("messages", [])
        
        # Check if system message already exists in history
        has_system_message = any(
            isinstance(msg, SystemMessage) and msg.content == system_prompt 
            for msg in existing_messages
        )
        
        if has_system_message:
            # System message already in history - just send user message
            inputs = {"messages": [HumanMessage(content=user_message)]}
            logger.debug("System message found in history - not adding duplicate")
        else:
            # First message in conversation - add system message
            inputs = {"messages": [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]}
            logger.debug("First message - adding system prompt")
    except Exception as e:
        # If we can't get state (new conversation), add system message
        logger.debug(f"Could not get existing state (likely new conversation): {e}")
        inputs = {"messages": [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]}
    
    # Execute agent (non-streaming)
    try:
        final_state = await agent_executor.ainvoke(inputs, config=config)
    except Exception as e:
        logger.error(f"Error executing agent: {e}", exc_info=True)
        
        # Check if error is due to invalid chat history (orphaned tool calls)
        error_str = str(e)
        if "tool_calls that do not have a corresponding ToolMessage" in error_str or "INVALID_CHAT_HISTORY" in error_str:
            logger.warning("Invalid chat history detected - clearing thread and retrying")
            # Clear the thread by using a new thread_id with timestamp
            import time
            config["configurable"]["thread_id"] = f"{config['configurable']['thread_id']}_{int(time.time())}"
            try:
                final_state = await agent_executor.ainvoke(inputs, config=config)
            except Exception as retry_error:
                logger.error(f"Error on retry: {retry_error}")
                return {
                    "type": "error",
                    "content": {
                        "answer": "I encountered an error processing your query. Please try again.",
                        "documents": []
                    },
                    "count": 0
                }
        else:
            return {
                "type": "error",
                "content": {
                    "answer": "I encountered an error processing your query. Please try again.",
                    "documents": []
                },
                "count": 0
            }
    
    # Extract answer from final message
    last_message = final_state["messages"][-1]
    answer = last_message.content if hasattr(last_message, "content") else str(last_message)
    
    # Determine response type and extract documents
    # Only extract from the MOST RECENT tool calls (for current query), not all history
    response_type = "detective"  # Default to detective (RAG)
    documents = []
    seen_ids = set()  # Track seen document IDs to avoid duplicates
    
    # Find the most recent user message (the current query)
    user_message_index = -1
    for i in range(len(final_state["messages"]) - 1, -1, -1):
        if isinstance(final_state["messages"][i], HumanMessage):
            user_message_index = i
            break
    
    # Only look at messages AFTER the most recent user message
    # This ensures we only get documents from the current query, not previous ones
    messages_to_check = final_state["messages"][user_message_index + 1:] if user_message_index >= 0 else final_state["messages"]
    
    # Look through messages to find tool calls and extract documents
    for msg in messages_to_check:
        # Check if this message has tool calls
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tool_call in msg.tool_calls:
                if tool_call["name"] == "fetch_documents":
                    response_type = "filter"
                elif tool_call["name"] == "search_memory_contents":
                    response_type = "detective"
        
        # Extract documents from tool messages
        if isinstance(msg, ToolMessage):
            try:
                # Prefer artifact (content_and_artifact): no URLs in LLM context
                if getattr(msg, "artifact", None) and isinstance(msg.artifact, list):
                    tool_results = msg.artifact
                else:
                    # Fallback: parse content (legacy or when artifact not supported)
                    import json
                    content = msg.content
                    if isinstance(content, list):
                        tool_results = content
                    elif isinstance(content, str):
                        try:
                            tool_results = json.loads(content)
                        except json.JSONDecodeError:
                            continue
                    else:
                        continue

                if not isinstance(tool_results, list):
                    continue

                for doc in tool_results:
                    if not isinstance(doc, dict):
                        continue
                    doc_id = doc.get("id")
                    if not doc_id or str(doc_id) in seen_ids:
                        continue
                    seen_ids.add(str(doc_id))
                    document = {
                        "id": str(doc_id),
                        "url": doc.get("url", ""),
                        "s3_original_url": doc.get("original_url", ""),
                        "summary": doc.get("summary", ""),
                    }
                    if "sender" in doc:
                        document["sender"] = doc["sender"]
                    if "event_type" in doc:
                        document["event_type"] = doc["event_type"]
                    if "date" in doc:
                        document["date"] = doc["date"]
                    documents.append(document)
            except Exception as e:
                logger.debug(f"Error parsing tool message: {e}")
    
    unique_documents = documents  # Already deduplicated using seen_ids
    
    return {
        "type": response_type,
        "content": {
            "answer": answer,
            "documents": unique_documents
        },
        "count": len(unique_documents)
    }


async def run_agent_chat(user_message: str, org_id: str, thread_id: str):
    """
    Stream agent responses for real-time chat (future use).
    
    Args:
        user_message: User's query string
        org_id: Organization ID for filtering
        thread_id: Thread ID for conversation history
        
    Yields:
        Streaming events from the agent
    """
    config = {
        "configurable": {
            "thread_id": thread_id,
            "org_id": org_id
        }
    }
    
    inputs = {"messages": [HumanMessage(content=user_message)]}

    # Stream the output back to the API
    # The frontend will receive "on_chat_model_stream" (text) and "on_tool_end" (JSON citations)
    async for event in agent_executor.astream_events(inputs, config=config, version="v1"):
        yield event