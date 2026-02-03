'use client';

import { useEffect, useState, useRef } from 'react';
import { useUser, useAuth } from '@clerk/nextjs';
import { useRouter } from 'next/navigation';
import Navbar from '@/components/Navbar';
import { apiClient } from '@/lib/api';
import { Send, Loader2 } from 'lucide-react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  documents?: Record<string, unknown>[];
}

export default function ChatPage() {
  const { user, isLoaded } = useUser();
  const { getToken } = useAuth();
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState<string>(() => {
    // Generate a session ID for this page load
    // This creates a new conversation thread per page session
    // To share history across page reloads, use localStorage
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  });
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isLoaded) return;
    
    if (!user) {
      router.push('/login');
      return;
    }
  }, [user, isLoaded]);


  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage: Message = { role: 'user', content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const token = await getToken();
      // Pass sessionId to create session-based conversation thread
      // Remove sessionId parameter to use persistent thread (all conversations share history)
      const response = await apiClient.askPack(input, sessionId, token);

      if (response.data) {
        // Debug: log the response to see document structure
        console.log('Chat response:', response.data);
        console.log('Documents:', response.data.content.documents);
        
        const assistantMessage: Message = {
          role: 'assistant',
          content: response.data.content.answer || 'I found some documents for you.',
          documents: response.data.content.documents || [],
        };
        setMessages((prev) => [...prev, assistantMessage]);
      } else {
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: response.error || 'Sorry, I encountered an error.' },
        ]);
      }
    } catch (error) {
      console.error('Error asking Pack:', error);
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Sorry, I encountered an error. Please try again.' },
      ]);
    } finally {
      setLoading(false);
    }
  }

  if (!isLoaded) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-lg">Loading...</div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-gradient-to-br from-stone-100 via-slate-50 to-stone-100">
      <Navbar />
      
      <main className="flex flex-1 flex-col">
        <div className="mx-auto w-full max-w-4xl px-4 py-8">
          <h1 className="mb-6 text-3xl font-bold text-gray-800">Ask Pack</h1>
          
          {/* Messages */}
          <div className="mb-4 flex-1 space-y-4 overflow-y-auto rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
            {messages.length === 0 && (
              <div className="text-center text-gray-500">
                <p className="mb-2 text-lg">Ask me anything about your family memories!</p>
                <p className="text-sm">Try: &quot;Show me birthday cards from Mom&quot; or &quot;What advice did Dad give?&quot;</p>
              </div>
            )}
            
            {messages.map((message, idx) => (
              <div
                key={idx}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg px-4 py-2 ${
                    message.role === 'user'
                      ? 'bg-purple-600 text-white shadow-sm'
                      : 'bg-gray-100 text-gray-900'
                  }`}
                >
                  <p className="whitespace-pre-wrap">{message.content}</p>
                  
                  {/* Show documents if available */}
                  {message.documents && message.documents.length > 0 && (
                    <div className="mt-3 space-y-2">
                      <p className="text-xs font-semibold text-gray-600">Referenced Documents:</p>
                      <div className="grid grid-cols-2 gap-2">
                        {message.documents.slice(0, 6).map((doc: Record<string, unknown>, idx: number) => {
                          // Debug: log each document
                          console.log(`Document ${idx}:`, doc);
                          
                          const thumbnailUrl = typeof doc.url === 'string' ? doc.url : typeof doc.s3_thumbnail_url === 'string' ? doc.s3_thumbnail_url : '';
                          const originalUrl = typeof doc.s3_original_url === 'string' ? doc.s3_original_url : typeof doc.url === 'string' ? doc.url : '';
                          
                          if (!thumbnailUrl) {
                            console.warn('No thumbnail URL for document:', doc);
                            return null;
                          }
                          
                          const summary = typeof doc.summary === 'string' ? doc.summary : '';
                          return (
                            <a
                              key={`doc-${idx}`}
                              href={originalUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="group relative overflow-hidden rounded border border-gray-200 transition-shadow hover:shadow-md"
                            >
                              <img
                                src={thumbnailUrl}
                                alt={summary || 'Document'}
                                className="h-24 w-full object-cover"
                                onError={(e) => {
                                  console.error('Image load error for:', thumbnailUrl, doc);
                                  (e.target as HTMLImageElement).style.display = 'none';
                                }}
                              />
                              {summary ? (
                                <div className="absolute bottom-0 left-0 right-0 bg-black/60 p-1 text-xs text-white opacity-0 transition-opacity group-hover:opacity-100">
                                  <p className="truncate">{summary}</p>
                                </div>
                              ) : null}
                            </a>
                          );
                        })}
                      </div>
                      {message.documents.length > 6 && (
                        <p className="text-xs text-gray-500">
                          +{message.documents.length - 6} more document{message.documents.length - 6 !== 1 ? 's' : ''}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
            
            {loading && (
              <div className="flex justify-start">
                <div className="rounded-lg bg-gray-100 px-4 py-2">
                  <Loader2 className="h-5 w-5 animate-spin text-gray-600" />
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>

          {/* Input Form */}
          <form onSubmit={handleSubmit} className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask Pack about your family memories..."
              className="flex-1 rounded-lg border border-gray-300 px-4 py-2 focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="rounded-lg bg-purple-600 px-6 py-2 text-white transition-colors hover:bg-purple-700 disabled:bg-gray-400 shadow-sm"
            >
              <Send className="h-5 w-5" />
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}

