"""Detective Tool for FastAPI."""
from app.core.database import get_family_filter
from openai import OpenAI
from app.core.config import settings
from typing import List, Dict
from pymongo.database import Database
from bson import ObjectId
import logging
import math

logger = logging.getLogger(__name__)

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def vector_search(family_id: str, query: str, db: Database, limit: int = 5) -> List[Dict]:
    """Perform vector search using Atlas Vector Search or fallback."""
    try:
        # Generate query embedding
        embedding_response = client.embeddings.create(
            model="text-embedding-3-small",
            input=query
        )
        query_embedding = embedding_response.data[0].embedding
        
        documents = db.documents
        
        # Try Atlas Vector Search
        try:
            pipeline = [
                {"$match": {"family_id": family_id}},
                {
                    "$vectorSearch": {
                        "index": "vector_index",
                        "path": "ai_context.embedding",
                        "queryVector": query_embedding,
                        "numCandidates": 100,
                        "limit": limit
                    }
                },
                {
                    "$project": {
                        "ai_context.text_content": 1,
                        "metadata": 1,
                        "s3_original_url": 1,
                        "s3_thumbnail_url": 1,
                        "score": {"$meta": "vectorSearchScore"}
                    }
                }
            ]
            
            results = list(documents.aggregate(pipeline))
            logger.info(f"Atlas Vector Search used for query: {query}")
            
            for doc in results:
                doc['_id'] = str(doc['_id'])
                if 'uploader_id' in doc:
                    doc['uploader_id'] = str(doc['uploader_id'])
            
            return results
        except Exception as e:
            logger.warning(f"Atlas Vector Search failed, using fallback: {e}")
            
            # Fallback to cosine similarity
            family_filter = get_family_filter(family_id)
            family_filter["ai_context.embedding"] = {"$exists": True}
            
            all_docs = list(documents.find(family_filter))
            
            def cosine_similarity(vec1, vec2):
                if not vec1 or not vec2:
                    return 0.0
                dot_product = sum(a * b for a, b in zip(vec1, vec2))
                magnitude1 = math.sqrt(sum(a * a for a in vec1))
                magnitude2 = math.sqrt(sum(a * a for a in vec2))
                if magnitude1 == 0 or magnitude2 == 0:
                    return 0.0
                return dot_product / (magnitude1 * magnitude2)
            
            scored_docs = []
            for doc in all_docs:
                if 'ai_context' in doc and 'embedding' in doc['ai_context']:
                    similarity = cosine_similarity(query_embedding, doc['ai_context']['embedding'])
                    scored_docs.append({
                        'doc': doc,
                        'similarity': similarity
                    })
            
            scored_docs.sort(key=lambda x: x['similarity'], reverse=True)
            results = [item['doc'] for item in scored_docs[:limit]]
            
            for doc in results:
                doc['_id'] = str(doc['_id'])
                if 'uploader_id' in doc:
                    doc['uploader_id'] = str(doc['uploader_id'])
            
            return results
            
    except Exception as e:
        logger.error(f"Error in vector search: {e}")
        return []


def generate_answer(query: str, relevant_docs: List[Dict]) -> str:
    """Generate answer from relevant documents."""
    try:
        context_parts = []
        for i, doc in enumerate(relevant_docs, 1):
            text_content = doc.get('ai_context', {}).get('text_content', '')
            sender = doc.get('metadata', {}).get('sender_name', 'Unknown')
            event = doc.get('metadata', {}).get('event_type', 'Unknown')
            date = doc.get('metadata', {}).get('doc_date', 'Unknown')
            
            context_parts.append(
                f"[Document {i}] From {sender}, {event} ({date}):\n{text_content}"
            )
        
        context = "\n\n".join(context_parts)
        
        system_prompt = """You are a helpful assistant answering questions about family memories.
Use the provided document context to answer the user's question accurately.
If the answer is not in the context, say so.
Include references to which document the information came from."""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"}
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        answer = response.choices[0].message.content
        
        citations = []
        for i, doc in enumerate(relevant_docs, 1):
            doc_id = str(doc['_id'])
            citations.append(f"[{i}] {doc_id}")
        
        if citations:
            answer += f"\n\nReferences: {', '.join(citations)}"
        
        return answer
        
    except Exception as e:
        logger.error(f"Error generating answer: {e}")
        return "I apologize, but I encountered an error while generating an answer."


def execute_detective_query(family_id: str, query: str, db: Database) -> Dict:
    """Execute detective query: vector search + answer generation."""
    relevant_docs = vector_search(family_id, query, db, limit=5)
    
    if not relevant_docs:
        return {
            'answer': "I couldn't find any relevant documents to answer your question.",
            'documents': []
        }
    
    answer = generate_answer(query, relevant_docs)
    
    return {
        'answer': answer,
        'documents': relevant_docs
    }

