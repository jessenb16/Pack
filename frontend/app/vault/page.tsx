'use client';

import { useEffect, useState } from 'react';
import { useUser, useAuth } from '@clerk/nextjs';
import { useRouter, useSearchParams } from 'next/navigation';
import Navbar from '@/components/Navbar';
import { apiClient } from '@/lib/api';
import { X, Loader2 } from 'lucide-react';

export default function VaultPage() {
  const { user, isLoaded } = useUser();
  const { getToken } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [documents, setDocuments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [senders, setSenders] = useState<string[]>([]);
  const [eventTypes, setEventTypes] = useState<string[]>([]);
  const [years, setYears] = useState<number[]>([]);
  
  const [filters, setFilters] = useState({
    sender: searchParams.get('sender') || '',
    event_type: searchParams.get('event_type') || '',
    year: searchParams.get('year') || '',
  });

  useEffect(() => {
    if (!isLoaded) return;
    
    if (!user) {
      router.push('/login');
      return;
    }

    loadDocuments();
  }, [user, isLoaded, filters]);

  async function loadDocuments() {
    try {
      setLoading(true);
      const token = await getToken();
      const response = await apiClient.getDocuments(
        {
          sender: filters.sender || undefined,
          event_type: filters.event_type || undefined,
          year: filters.year ? parseInt(filters.year) : undefined,
        },
        token
      );
      
      if (response.data) {
        setDocuments(response.data);
        
        // Extract unique values for Smart Chips
        const uniqueSenders = new Set<string>();
        const uniqueEvents = new Set<string>();
        const uniqueYears = new Set<number>();
        
        response.data.forEach((doc: any) => {
          if (doc.metadata?.sender_name) uniqueSenders.add(doc.metadata.sender_name);
          if (doc.metadata?.event_type) uniqueEvents.add(doc.metadata.event_type);
          if (doc.metadata?.doc_date) {
            const year = new Date(doc.metadata.doc_date).getFullYear();
            uniqueYears.add(year);
          }
        });
        
        setSenders(Array.from(uniqueSenders).sort());
        setEventTypes(Array.from(uniqueEvents).sort());
        setYears(Array.from(uniqueYears).sort((a, b) => b - a));
      }
    } catch (error) {
      console.error('Error loading documents:', error);
    } finally {
      setLoading(false);
    }
  }

  function updateFilter(key: string, value: string) {
    const newFilters = { ...filters, [key]: value };
    setFilters(newFilters);
    
    // Update URL
    const params = new URLSearchParams();
    Object.entries(newFilters).forEach(([k, v]) => {
      if (v) params.set(k, v);
    });
    router.push(`/vault?${params.toString()}`);
  }

  function clearFilter(key: string) {
    const newFilters = { ...filters, [key]: '' };
    setFilters(newFilters);
    
    const params = new URLSearchParams();
    Object.entries(newFilters).forEach(([k, v]) => {
      if (v) params.set(k, v);
    });
    router.push(`/vault?${params.toString()}`);
  }

  if (!isLoaded || loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-red-900" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      
      <main className="mx-auto max-w-7xl px-4 py-8">
        <h1 className="mb-8 text-3xl font-bold text-gray-900">The Vault</h1>
        
        {/* Smart Chips Filter */}
        <div className="mb-8">
          <div className="mb-4">
            <h2 className="mb-2 text-lg font-semibold text-gray-700">Filter by Sender</h2>
            <div className="flex flex-wrap gap-2">
              {senders.map((sender) => (
                <button
                  key={sender}
                  onClick={() => updateFilter('sender', sender)}
                  className={`rounded-full px-4 py-2 text-sm transition-colors ${
                    filters.sender === sender
                      ? 'bg-red-900 text-white'
                      : 'bg-white text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  {sender}
                </button>
              ))}
            </div>
          </div>
          
          <div className="mb-4">
            <h2 className="mb-2 text-lg font-semibold text-gray-700">Filter by Event</h2>
            <div className="flex flex-wrap gap-2">
              {eventTypes.map((event) => (
                <button
                  key={event}
                  onClick={() => updateFilter('event_type', event)}
                  className={`rounded-full px-4 py-2 text-sm transition-colors ${
                    filters.event_type === event
                      ? 'bg-red-900 text-white'
                      : 'bg-white text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  {event}
                </button>
              ))}
            </div>
          </div>
          
          <div className="mb-4">
            <h2 className="mb-2 text-lg font-semibold text-gray-700">Filter by Year</h2>
            <div className="flex flex-wrap gap-2">
              {years.map((year) => (
                <button
                  key={year}
                  onClick={() => updateFilter('year', year.toString())}
                  className={`rounded-full px-4 py-2 text-sm transition-colors ${
                    filters.year === year.toString()
                      ? 'bg-red-900 text-white'
                      : 'bg-white text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  {year}
                </button>
              ))}
            </div>
          </div>
          
          {/* Active Filters */}
          {(filters.sender || filters.event_type || filters.year) && (
            <div className="mt-4 flex items-center gap-2">
              <span className="text-sm text-gray-600">Active filters:</span>
              {filters.sender && (
                <span className="flex items-center gap-1 rounded-full bg-red-900 px-3 py-1 text-sm text-white">
                  {filters.sender}
                  <button onClick={() => clearFilter('sender')}>
                    <X className="h-4 w-4" />
                  </button>
                </span>
              )}
              {filters.event_type && (
                <span className="flex items-center gap-1 rounded-full bg-red-900 px-3 py-1 text-sm text-white">
                  {filters.event_type}
                  <button onClick={() => clearFilter('event_type')}>
                    <X className="h-4 w-4" />
                  </button>
                </span>
              )}
              {filters.year && (
                <span className="flex items-center gap-1 rounded-full bg-red-900 px-3 py-1 text-sm text-white">
                  {filters.year}
                  <button onClick={() => clearFilter('year')}>
                    <X className="h-4 w-4" />
                  </button>
                </span>
              )}
            </div>
          )}
        </div>

        {/* Document Grid */}
        {documents.length === 0 ? (
          <p className="text-gray-600">No documents found. Try adjusting your filters.</p>
        ) : (
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-6">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="group cursor-pointer overflow-hidden rounded-lg bg-white shadow transition-shadow hover:shadow-lg"
              >
                <img
                  src={doc.s3_thumbnail_url}
                  alt={doc.metadata?.sender_name || 'Document'}
                  className="h-48 w-full object-cover"
                />
                <div className="p-3">
                  <p className="text-sm font-medium text-gray-900">
                    {doc.metadata?.sender_name}
                  </p>
                  <p className="text-xs text-gray-500">{doc.metadata?.event_type}</p>
                  <p className="text-xs text-gray-400">
                    {new Date(doc.metadata?.doc_date).toLocaleDateString()}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

