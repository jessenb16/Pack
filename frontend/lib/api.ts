/**
 * API client for communicating with FastAPI backend
 * Uses Clerk for authentication
 * 
 * Note: This is a client-side API client. Token retrieval should be done
 * in components using useAuth().getToken() and passed to these methods.
 */

// Ensure base URL has a protocol so it's never treated as a relative path
function normalizeApiBase(url: string): string {
  const trimmed = (url || '').trim().replace(/\/+$/, '');
  if (!trimmed) return 'http://localhost:8000';
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  return `https://${trimmed}`;
}
const API_BASE_URL = normalizeApiBase(process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000');

export interface ApiResponse<T> {
  data?: T;
  error?: string;
  message?: string;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    token?: string | null
  ): Promise<ApiResponse<T>> {
    const url = `${this.baseUrl}${endpoint}`;
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {}),
    };

    // Add Clerk token if available
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
        credentials: 'include',
      });

      const data = await response.json();

      if (!response.ok) {
        return {
          error: data.detail || data.error || 'An error occurred',
        };
      }

      return { data };
    } catch (error) {
      return {
        error: error instanceof Error ? error.message : 'Network error',
      };
    }
  }

  // Note: Auth is handled by Clerk, these endpoints are for backend sync

  // Family endpoints
  async getFamily(token?: string | null) {
    return this.request<Record<string, unknown>>('/api/families/me', {}, token);
  }

  async createFamily(name: string, token?: string | null) {
    return this.request<Record<string, unknown>>('/api/families', {
      method: 'POST',
      body: JSON.stringify({ name }),
    }, token);
  }

  async getFamilyMembers(token?: string | null) {
    return this.request<Record<string, unknown>[]>('/api/families/members', {}, token);
  }

  // Document endpoints
  async getDocuments(filters?: { sender?: string; event_type?: string; year?: number }, token?: string | null) {
    const params = new URLSearchParams();
    if (filters?.sender) params.append('sender', filters.sender);
    if (filters?.event_type) params.append('event_type', filters.event_type);
    if (filters?.year) params.append('year', filters.year.toString());
    
    const query = params.toString();
    return this.request<Record<string, unknown>[]>(`/api/documents${query ? `?${query}` : ''}`, {}, token);
  }

  async uploadDocument(file: File, metadata: {
    sender_name: string;
    event_type: string;
    recipient_name?: string;
    doc_date: string;
  }, token?: string | null) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('sender_name', metadata.sender_name);
    formData.append('event_type', metadata.event_type);
    formData.append('doc_date', metadata.doc_date);
    if (metadata.recipient_name) {
      formData.append('recipient_name', metadata.recipient_name);
    }

    const url = `${this.baseUrl}/api/documents/upload`;
    const headers: HeadersInit = {};
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: formData,
      credentials: 'include',
    });

    const data = await response.json();
    if (!response.ok) {
      return { error: data.detail || data.error || 'Upload failed' };
    }
    return { data };
  }

  async deleteDocument(documentId: string, token?: string | null) {
    const url = `${this.baseUrl}/api/documents/${documentId}`;
    const headers: Record<string, string> = {};
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    try {
      const response = await fetch(url, {
        method: 'DELETE',
        headers,
        credentials: 'include',
      });

      // DELETE endpoint returns 204 No Content on success
      if (response.status === 204) {
        return { data: { success: true } };
      }

      // If there's an error, try to parse the response
      const data = await response.json().catch(() => ({}));
      return {
        error: data.detail || data.error || 'Failed to delete document',
      };
    } catch (error) {
      return {
        error: error instanceof Error ? error.message : 'Network error',
      };
    }
  }

  // Chat endpoints
  async askPack(query: string, sessionId?: string | null, token?: string | null) {
    // Note: conversation_history is no longer needed - handled by thread_id on backend
    // sessionId: Optional - if provided, creates session-based thread (new conversation per session)
    //            if not provided, creates persistent thread (all conversations share history)
    return this.request<{ 
      type: string;  // "filter" or "detective"
      content: {
        answer: string;
        documents?: Record<string, unknown>[];
      };
      count: number;
    }>('/api/chat/ask', {
      method: 'POST',
      body: JSON.stringify({ query, session_id: sessionId || null }),
    }, token);
  }

  // Invitation endpoints
  async sendInvitation(email: string, token?: string | null) {
    return this.request<{ message: string; invitation_id: string; email: string }>('/api/families/invitations', {
      method: 'POST',
      body: JSON.stringify({ email: email.trim() }),
    }, token);
  }

  async getInvitations(token?: string | null) {
    return this.request<Record<string, unknown>[]>('/api/families/invitations', {}, token);
  }

  async revokeInvitation(invitationId: string, token?: string | null) {
    return this.request<{ message: string }>(`/api/families/invitations/${invitationId}/revoke`, {
      method: 'POST',
    }, token);
  }
}

export const apiClient = new ApiClient(API_BASE_URL);

