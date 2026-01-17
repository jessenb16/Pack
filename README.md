# Pack: The AI-Native Family Archive

### 🚧 Status: Active Re-Architecture (2026)
**Current Focus:** Migrating backend from relational SQL to **MongoDB (NoSQL)** and integrating **Agentic RAG workflows** for memory retrieval.

---

## 📅 2026 Engineering Roadmap
I am currently refactoring this legacy application to support unstructured data (photos, stories, audio) and natural language search.

- [ ] **Database Migration:**
    - [ ] Migrate schema from MySQL (Relational) to **PyMongo/MongoDB Atlas**.
    - [ ] Redesign data model to support "Document-based" memories (JSON-like storage for mixed media).
- [ ] **AI & RAG Implementation:**
    - [ ] Implement **Vector Embeddings** for user posts using OpenAI.
    - [ ] Build a "Historian Agent" using **LangChain** that answers questions like *"What did we do for Mom's 50th?"* based on stored memories.
    - [ ] Implement semantic search to cluster similar family events automatically.
- [ ] **Frontend Modernization:**
    - [ ] Update Jinja2 templates to dynamic React components (Planned).

---

## 📖 About The Project
**Pack** is a private digital space for families to archive memories, share updates, and preserve their history. Unlike standard social media, Pack is designed for **privacy** and **retrieval**—acting as a long-term family historian rather than a temporary feed.

### The Technical Pivot
The original application was built using a standard Flask + SQL stack. However, family data is inherently unstructured (scanned letters, voice notes, photos). I am re-architecting the backend to use **MongoDB**, which allows for flexible document storage, and adding an **LLM layer** to make that data searchable via natural language.

## 🛠 Tech Stack (Evolution)
* **Legacy:** Python, Flask, MySQL, HTML/CSS/Bootstrap.
* **New Architecture:** MongoDB Atlas, Vector Search, OpenAI API, Python.