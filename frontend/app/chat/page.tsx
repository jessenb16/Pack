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
  documents?: any[];
}

export default function ChatPage() {
  const { user, isLoaded } = useUser();
  const { getToken } = useAuth();
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
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
      const response = await apiClient.askPack(
        input,
        messages.map((m) => ({ role: m.role, content: m.content })),
        token
      );

      if (response.data) {
        const assistantMessage: Message = {
          role: 'assistant',
          content: response.data.answer || 'I found some documents for you.',
          documents: response.data.documents,
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
    <div className="flex min-h-screen flex-col bg-gray-50">
      <Navbar />
      
      <main className="flex flex-1 flex-col">
        <div className="mx-auto w-full max-w-4xl px-4 py-8">
          <h1 className="mb-6 text-3xl font-bold text-gray-900">Ask Pack</h1>
          
          {/* Messages */}
          <div className="mb-4 flex-1 space-y-4 overflow-y-auto rounded-lg bg-white p-6 shadow">
            {messages.length === 0 && (
              <div className="text-center text-gray-500">
                <p className="mb-2 text-lg">Ask me anything about your family memories!</p>
                <p className="text-sm">Try: "Show me birthday cards from Mom" or "What advice did Dad give?"</p>
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
                      ? 'bg-red-900 text-white'
                      : 'bg-gray-100 text-gray-900'
                  }`}
                >
                  <p className="whitespace-pre-wrap">{message.content}</p>
                  
                  {/* Show documents if available */}
                  {message.documents && message.documents.length > 0 && (
                    <div className="mt-3 grid grid-cols-2 gap-2">
                      {message.documents.slice(0, 4).map((doc: any) => (
                        <img
                          key={doc.id}
                          src={doc.s3_thumbnail_url}
                          alt="Document"
                          className="h-24 w-full rounded object-cover"
                        />
                      ))}
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
              className="flex-1 rounded-lg border border-gray-300 px-4 py-2 focus:border-red-900 focus:outline-none focus:ring-2 focus:ring-red-900"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="rounded-lg bg-red-900 px-6 py-2 text-white transition-colors hover:bg-red-800 disabled:bg-gray-400"
            >
              <Send className="h-5 w-5" />
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}

