"""Query router for FastAPI."""
from openai import OpenAI
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def route_query(query: str) -> str:
    """Route query to appropriate tool: Filter or Detective."""
    try:
        system_prompt = """You are a query classifier for a family memory archive system.
Determine if the user query is asking for:
1. Filter Tool: Specific documents by metadata (sender, event type, date)
   Examples: "Show me birthday cards from Mom", "Find all Christmas cards", "Cards from 2023"
2. Detective Tool: Semantic questions about content
   Examples: "What advice did Mom give?", "What did Dad write about?", "Tell me about graduation"
   
Respond with only "filter" or "detective"."""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            max_tokens=10,
            temperature=0
        )
        
        result = response.choices[0].message.content.strip().lower()
        
        if "filter" in result:
            return "filter"
        else:
            return "detective"
            
    except Exception as e:
        logger.error(f"Error routing query: {e}")
        return "detective"

