"""Chat API endpoints for LangGraph agent."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List, Dict

from app.api.auth import get_current_user_light
import logging
import hashlib

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatQuery(BaseModel):
    """Chat query model."""
    query: str
    conversation_history: Optional[List[Dict]] = None  # Deprecated - kept for backward compatibility
    session_id: Optional[str] = None  # Optional: if provided, creates a new conversation thread per session


class ChatResponse(BaseModel):
    """Chat response model."""
    type: str  # "filter" or "detective"
    content: Dict
    count: int


def generate_thread_id(org_id: str, user_id: str, session_id: Optional[str] = None) -> str:
    """
    Generate a thread ID for conversation history.
    
    If session_id is provided, creates a session-specific thread (new conversation per session).
    If not provided, creates a persistent thread per user/org (all conversations share history).
    
    Args:
        org_id: Organization ID
        user_id: User ID
        session_id: Optional session ID for session-based conversations
        
    Returns:
        Thread ID string
    """
    if session_id:
        # Session-based: each session gets its own conversation thread
        thread_string = f"{org_id}_{user_id}_{session_id}"
    else:
        # Persistent: all conversations for this user/org share the same thread
        thread_string = f"{org_id}_{user_id}"
    
    thread_id = hashlib.md5(thread_string.encode()).hexdigest()
    return thread_id


@router.post("/ask", response_model=ChatResponse)
async def ask_pack(
    chat_query: ChatQuery,
    current_user: dict = Depends(get_current_user_light)
):
    """Process a chat query using the LangGraph agent."""
    org_id = current_user.get("org_id")
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not part of an organization"
        )
    
    user_id = current_user.get("clerk_user_id", "")
    
    # Generate thread ID for conversation history
    # If session_id is provided, creates session-based thread (new conversation per session)
    # If not, creates persistent thread (all conversations share history)
    thread_id = generate_thread_id(org_id, user_id, chat_query.session_id)
    
    try:
        from app.services.agent_service import execute_agent_query
        
        result = await execute_agent_query(
            chat_query.query,
            org_id,
            thread_id
            # Note: conversation_history removed - checkpointer handles it via thread_id
        )
        
        return ChatResponse(
            type=result.get('type', 'detective'),
            content=result.get('content', {}),
            count=result.get('count', 0)
        )
        
    except Exception as e:
        logger.error(f"Error processing chat query: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing query: {str(e)}"
        )

