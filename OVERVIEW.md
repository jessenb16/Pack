# Project Pack: The Digital Family Shoebox
**Context & Architecture Document**

## 1. High-Level Vision
**Pack** is a multi-tenant web application designed to preserve family memories (cards, letters, photos). It allows families to upload physical media, digitize it with AI, and retrieve it using either visual filters ("The Vault") or a natural language chat agent ("Ask Pack").

**Core Requirement:**
* **Privacy:** Data is strictly isolated by Family (Organization).
* **Hybrid Search:** Supports both rigid filtering (Tags) and semantic search (Vector/RAG).
* **Media Types:** Handles Images (Vision AI) and PDFs (Text Extraction) in a unified pipeline.

---

## 2. The Tech Stack
* **Frontend:** Next.js 14+ (App Router), Tailwind CSS.
* **Backend:** FastAPI (Python), Motor (Async Mongo Driver).
* **Auth & Organization:** Clerk (Handling Users, Invites, and Family switching).
* **Database:** MongoDB Atlas (Storing Metadata, Text, and Vector Embeddings).
* **Storage:** AWS S3 (Original files + Generated Thumbnails).
* **AI Orchestration:** **LangGraph** (managing the Agent workflow).
* **Models:** OpenAI GPT-4o (Vision/Chat) and `text-embedding-3-small`.

---

## 3. Core Workflows

### A. Authentication & Security (The "Silo")
* **Identity:** Handled by Clerk.
* **Grouping:** We use **Clerk Organizations** to represent Families.
* **Security Rule:** Every single request to the Backend includes a Clerk Token. The Backend extracts the `org_id` from this token and **MUST** inject it into every MongoDB query.
    * *Constraint:* No user can ever query data without the `org_id` filter.

### B. Ingestion Pipeline (The "Upload Wizard")
We use a **Hybrid Ingestion Strategy** to balance cost and accuracy.
1.  **User Action:** User drags file -> Manually selects Metadata (Sender, Recipient, Event, Date).
2.  **Processing (Backend):**
    * **Thumbnail:** Generate a 300px JPG (using `pdf2image` for PDFs or `Pillow` for Images).
    * **Text Extraction:**
        * *If PDF:* Use `pypdf` to extract text (Free).
        * *If Image:* Use **GPT-4o Vision** to transcribe handwriting and generate a visual description (Paid).
3.  **Storage:** Save File to S3 $\rightarrow$ Save Metadata + Text to MongoDB $\rightarrow$ Generate Embedding $\rightarrow$ Save Vector to MongoDB.

### C. The AI Agent (LangGraph)
We use **LangGraph** to build a reactive agent that routes user queries to the correct tool.

**The Logic:**
* **System Prompt:** "You are Pack. Use `fetch_documents` for list/view requests. Use `search_memory_contents` for specific questions or visual details."
* **Tool 1: The Fetcher (`fetch_documents`)**
    * *Role:* The Librarian.
    * *Logic:* Executes a precise MongoDB `find()` query using rigid tags (`sender`, `event`, `year`).
    * *Output:* A list of document assets (images/thumbnails).
* **Tool 2: The Reader (`search_memory_contents`)**
    * *Role:* The Detective (RAG).
    * *Logic:* Performs a **Vector Search** (Atlas) but applies metadata filters *first* (Pre-filtering).
    * *Output:* A text answer synthesized from the document content + citation links.

---

## 4. Database Schema (MongoDB)

**Collection: `documents`**
* **Indices:**
    1.  Vector Search Index (Atlas) on `ai_context.embedding`.
    2.  Standard Index: `{ "org_id": 1, "metadata.sender_name": 1 }`
    3.  Standard Index: `{ "org_id": 1, "metadata.event_type": 1 }`
    4.  Standard Index: `{ "org_id": 1, "metadata.doc_date": -1 }`

```javascript
{
  "_id": ObjectId("..."),
  "org_id": "org_clerk_123",     // 🔒 CRITICAL SECURITY FILTER (From Clerk)
  "uploader_id": "user_clerk_abc",
  "created_at": ISODate("2026-01-23..."),
  
  // 1. User-Defined Metadata (For "Fetcher" Tool)
  "metadata": {
    "sender_name": "Mom",        // Matches 'org_settings'
    "recipient_name": "Sam",     // Matches 'org_settings' (Optional)
    "event_type": "Birthday",    // Matches 'org_settings' (Or "General")
    "doc_date": ISODate("2023-...")
  },

  // 2. File Assets (For Grid Display)
  "assets": {
    "file_type": "image/jpeg",   // or "application/pdf"
    "s3_original_url": "https://s3...",
    "s3_thumbnail_url": "https://s3..."
  },

  // 3. AI Context (For "Reader" Tool / RAG)
  "ai_context": {
    // Combined string of Metadata + Description + Extracted Text
    "text_content": "Sender: Mom. Event: Birthday. Content: Happy Birthday! [Visual: Red balloon]", 
    "embedding": [0.01, -0.2, ...] // 1536 dim (text-embedding-3-small)
  }
}

**Collection: `org_settings`**
* Stores the "Autocomplete" options for the specific family.
* _id is the org_id for fast lookup.
    
```javascript
{
  "_id": "org_clerk_123",
  "event_types": ["Birthday", "Christmas", "Graduation", "Vacation"],
  "sender_names": ["Mom", "Dad", "Grandma"],
  "recipient_names": ["Sam", "Jessica", "The Family"]
}