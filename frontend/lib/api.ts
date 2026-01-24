/**
 * API client for communicating with FastAPI backend
 * Uses Clerk for authentication
 * 
 * Note: This is a client-side API client. Token retrieval should be done
 * in components using useAuth().getToken() and passed to these methods.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
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
    return this.request<any>('/api/families/me', {}, token);
  }

  async createFamily(name: string, token?: string | null) {
    return this.request<any>('/api/families', {
      method: 'POST',
      body: JSON.stringify({ name }),
    }, token);
  }

  async getFamilyMembers(token?: string | null) {
    return this.request<any[]>('/api/families/members', {}, token);
  }

  // Document endpoints
  async getDocuments(filters?: { sender?: string; event_type?: string; year?: number }, token?: string | null) {
    const params = new URLSearchParams();
    if (filters?.sender) params.append('sender', filters.sender);
    if (filters?.event_type) params.append('event_type', filters.event_type);
    if (filters?.year) params.append('year', filters.year.toString());
    
    const query = params.toString();
    return this.request<any[]>(`/api/documents${query ? `?${query}` : ''}`, {}, token);
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

  // Chat endpoints
  async askPack(query: string, conversation_history?: any[], token?: string | null) {
    return this.request<{ answer: string; documents?: any[] }>('/api/chat/ask', {
      method: 'POST',
      body: JSON.stringify({ query, conversation_history }),
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
    return this.request<any[]>('/api/families/invitations', {}, token);
  }

  async revokeInvitation(invitationId: string, token?: string | null) {
    return this.request<{ message: string }>(`/api/families/invitations/${invitationId}/revoke`, {
      method: 'POST',
    }, token);
  }
}

export const apiClient = new ApiClient(API_BASE_URL);

