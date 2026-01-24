"""Chat API endpoints for RAG agent."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List, Dict

from app.core.database import get_db
from app.api.auth import get_current_user
from pymongo.database import Database
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatQuery(BaseModel):
    """Chat query model."""
    query: str
    conversation_history: Optional[List[Dict]] = None


class ChatResponse(BaseModel):
    """Chat response model."""
    type: str  # "filter" or "detective"
    content: Dict
    count: int


@router.post("/ask", response_model=ChatResponse)
async def ask_pack(
    chat_query: ChatQuery,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Process a chat query using the RAG agent."""
    org_id = current_user.get("org_id")
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not part of an organization"
        )
    
    try:
        from app.agents.rag_agent import RAGAgent
        
        agent = RAGAgent(org_id, db)
        result = agent.process_query(chat_query.query, chat_query.conversation_history)
        
        return ChatResponse(
            type=result.get('type', 'detective'),
            content=result.get('content', {}),
            count=result.get('count', 0)
        )
        
    except Exception as e:
        logger.error(f"Error processing chat query: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing query: {str(e)}"
        )

