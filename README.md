# Pack - AI-Native Family Archive

A modern web application for preserving and searching family memories using AI-powered retrieval.

## Tech Stack

- **Frontend**: Next.js 14+ (App Router), TypeScript, Tailwind CSS
- **Backend**: FastAPI (Python), Uvicorn
- **Database**: MongoDB Atlas
- **Authentication**: Clerk (Organizations = Families)
- **Storage**: AWS S3
- **AI**: OpenAI (GPT-4o Vision, text-embedding-3-small, GPT-4o-mini)

## Quick Start

### 1. Set Up MongoDB Atlas

See `MONGODB_SETUP.md` for detailed instructions.

**Quick steps:**
1. Create account at https://www.mongodb.com/cloud/atlas
2. Create free cluster
3. Create database user
4. Whitelist your IP (0.0.0.0/0 for development)
5. Get connection string

### 2. Set Up Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create `backend/.env`:
```env
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/pack?retryWrites=true&w=majority
DATABASE_NAME=pack
CLERK_SECRET_KEY=sk_test_...
OPENAI_API_KEY=sk-...
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_S3_BUCKET_NAME=...
AWS_REGION=us-east-1
FRONTEND_URL=http://localhost:3000
```

Start backend:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Or use: `./run.sh`

### 3. Set Up Frontend

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:
```env
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Start frontend:
```bash
npm run dev
```

### 4. Set Up Clerk

1. Create account at https://clerk.com
2. Create application
3. Get publishable key and secret key
4. In Clerk Dashboard → Organizations → Settings:
   - Set "Membership required" ✅
   - Enable "Allow user-created organizations" ✅
5. Add redirect URLs:
   - After Sign Up: `http://localhost:3000/dashboard`
   - After Sign In: `http://localhost:3000/dashboard`
   - After Invitation: `http://localhost:3000/accept-invitation`

## Project Structure

```
Pack/
├── backend/          # FastAPI backend
│   ├── app/
│   │   ├── api/     # API endpoints
│   │   ├── core/     # Config, database, auth
│   │   ├── models/   # Pydantic models
│   │   ├── services/ # S3, document processing
│   │   └── agents/   # RAG agent tools
│   └── requirements.txt
├── frontend/         # Next.js frontend
│   ├── app/          # Pages and routes
│   ├── components/   # React components
│   └── lib/          # API client
└── README.md
```

## Features

- **Multi-Family Support**: Each family has isolated data
- **Document Upload**: Images and PDFs with automatic processing
- **AI-Powered Search**: RAG agent with dual-tool architecture
- **Smart Filtering**: Metadata-based filtering in the Vault
- **Family Invitations**: Send invites via Clerk organizations
- **On This Day**: Memories from past years

## Development

Backend runs on: `http://localhost:8000`
Frontend runs on: `http://localhost:3000`

API docs: `http://localhost:8000/docs`

## Environment Variables

See `MONGODB_SETUP.md` for MongoDB setup and environment variable details.
