"""Filter Tool for FastAPI."""
from app.core.database import get_family_filter
from typing import List, Dict, Optional
from pymongo.database import Database
from bson import ObjectId
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)


def parse_filter_query(query: str, available_event_types: List[str] = None) -> Dict:
    """Parse user query to extract filter parameters."""
    filters = {}
    query_lower = query.lower()
    
    if available_event_types:
        for event_type in available_event_types:
            event_lower = event_type.lower()
            if (event_lower in query_lower or 
                event_type.replace("'", "").lower() in query_lower or
                event_type.replace(" ", "").lower() in query_lower):
                filters['event_type'] = event_type
                break
    
    year_match = re.search(r'\b(20\d{2})\b', query)
    if year_match:
        year = int(year_match.group(1))
        filters['year'] = year
    
    return filters


def execute_filter_query(
    family_id: str, 
    query: str, 
    family_members: List[str],
    available_event_types: List[str],
    db: Database
) -> List[Dict]:
    """Execute filter query with automatic sender detection."""
    filters = parse_filter_query(query, available_event_types)
    
    query_lower = query.lower()
    sender_name = None
    for member in family_members:
        if member.lower() in query_lower:
            sender_name = member
            break
    
    # Build filter
    filter_query = get_family_filter(family_id)
    
    if sender_name:
        filter_query["metadata.sender_name"] = sender_name
    
    if filters.get('event_type'):
        filter_query["metadata.event_type"] = filters['event_type']
    
    if filters.get('year'):
        start_date = datetime(filters['year'], 1, 1).isoformat()
        end_date = datetime(filters['year'] + 1, 1, 1).isoformat()
        filter_query["metadata.doc_date"] = {"$gte": start_date, "$lt": end_date}
    
    # Query documents
    results = list(db.documents.find(filter_query).sort("created_at", -1).limit(50))
    
    # Convert ObjectId to string
    for doc in results:
        doc['_id'] = str(doc['_id'])
        if 'uploader_id' in doc:
            doc['uploader_id'] = str(doc['uploader_id'])
    
    return results

