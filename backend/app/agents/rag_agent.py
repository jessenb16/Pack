"""RAG Agent for FastAPI."""
from app.agents.query_router import route_query
from app.agents.filter_tool import execute_filter_query
from app.agents.detective_tool import execute_detective_query
from app.core.clerk_org import get_organization_members
from app.services.org_settings import get_org_settings
from pymongo.database import Database
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class RAGAgent:
    """RAG Agent for processing queries."""
    
    def __init__(self, org_id: str, db: Database):
        """Initialize RAG agent with organization context."""
        self.org_id = org_id
        self.db = db
    
    def get_family_members(self) -> List[str]:
        """Get list of family member names from Clerk."""
        try:
            memberships = get_organization_members(self.org_id)
            members = []
            for membership in memberships:
                public_user_data = membership.get("public_user_data", {})
                first_name = public_user_data.get("first_name") or ""
                last_name = public_user_data.get("last_name") or ""
                name = f"{first_name} {last_name}".strip()
                if name:
                    members.append(name)
            return members
        except Exception as e:
            logger.error(f"Error getting family members: {e}")
            return []
    
    def get_family_event_types(self) -> List[str]:
        """Get list of event types from org_settings."""
        try:
            org_settings = get_org_settings(self.org_id, self.db)
            return org_settings.get('event_types', [])
        except Exception as e:
            logger.error(f"Error getting event types: {e}")
            return []
    
    def process_query(self, query: str, conversation_history: List[Dict] = None) -> Dict:
        """Process a user query."""
        try:
            tool_type = route_query(query)
            
            if tool_type == "filter":
                family_members = self.get_family_members()
                available_event_types = self.get_family_event_types()
                documents = execute_filter_query(
                    self.org_id,
                    query,
                    family_members,
                    available_event_types,
                    self.db
                )
                
                return {
                    'type': 'filter',
                    'content': {
                        'documents': documents,
                        'count': len(documents)
                    },
                    'count': len(documents)
                }
            else:
                result = execute_detective_query(self.org_id, query, self.db)
                
                return {
                    'type': 'detective',
                    'content': {
                        'answer': result['answer'],
                        'documents': result['documents'],
                        'count': len(result['documents'])
                    },
                    'count': len(result['documents'])
                }
                
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return {
                'type': 'error',
                'content': {
                    'error': 'An error occurred while processing your query.'
                },
                'count': 0
            }

