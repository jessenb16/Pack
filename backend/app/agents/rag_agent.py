"""RAG Agent for FastAPI."""
from app.agents.query_router import route_query
from app.agents.filter_tool import execute_filter_query
from app.agents.detective_tool import execute_detective_query
from pymongo.database import Database
from bson import ObjectId
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class RAGAgent:
    """RAG Agent for processing queries."""
    
    def __init__(self, family_id: str, db: Database):
        """Initialize RAG agent with family context."""
        self.family_id = family_id
        self.db = db
    
    def get_family_members(self) -> List[str]:
        """Get list of family member names."""
        try:
            family = self.db.families.find_one({"_id": ObjectId(self.family_id)})
            if not family:
                return []
            
            member_ids = [ObjectId(mid) for mid in family.get('members', [])]
            members = list(self.db.users.find({"_id": {"$in": member_ids}}))
            return [m.get('name', '') for m in members if m.get('name')]
        except Exception as e:
            logger.error(f"Error getting family members: {e}")
            return []
    
    def get_family_event_types(self) -> List[str]:
        """Get list of event types for this family."""
        try:
            family = self.db.families.find_one({"_id": ObjectId(self.family_id)})
            if not family:
                return []
            return family.get('event_types', [])
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
                    self.family_id,
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
                result = execute_detective_query(self.family_id, query, self.db)
                
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

