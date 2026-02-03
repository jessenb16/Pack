'use client';

import { Suspense, useEffect, useState } from 'react';
import { useUser, useAuth } from '@clerk/nextjs';
import { useRouter, useSearchParams } from 'next/navigation';
import Navbar from '@/components/Navbar';
import DocumentViewer, { type DocumentViewerDocument } from '@/components/DocumentViewer';
import { apiClient } from '@/lib/api';
import { X, Loader2 } from 'lucide-react';

function VaultContent() {
  const { user, isLoaded } = useUser();
  const { getToken } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [documents, setDocuments] = useState<DocumentViewerDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [senders, setSenders] = useState<string[]>([]);
  const [eventTypes, setEventTypes] = useState<string[]>([]);
  const [years, setYears] = useState<number[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<DocumentViewerDocument | null>(null);
  
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, isLoaded, filters.sender, filters.event_type, filters.year]);

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
        const docs = response.data as unknown as DocumentViewerDocument[];
        setDocuments(docs);

        // Only extract unique values for Smart Chips if we don't have them yet
        // (to avoid unnecessary processing on filter changes)
        if (senders.length === 0 || eventTypes.length === 0 || years.length === 0) {
          const uniqueSenders = new Set<string>();
          const uniqueEvents = new Set<string>();
          const uniqueYears = new Set<number>();

          docs.forEach((doc) => {
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

  async function handleDelete(documentId: string) {
    try {
      const token = await getToken();
      const response = await apiClient.deleteDocument(documentId, token);
      
      if (response.error) {
        alert(`Error deleting document: ${response.error}`);
        return;
      }

      // Remove document from local state
      setDocuments(documents.filter(doc => doc.id !== documentId));
      
      // Close the modal
      setSelectedDoc(null);
      
      // Optionally reload documents to ensure consistency
      // loadDocuments();
    } catch (error) {
      console.error('Error deleting document:', error);
      alert('Failed to delete document. Please try again.');
    }
  }

  if (!isLoaded || loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-red-900" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-stone-100 via-slate-50 to-stone-100">
      <Navbar />
      
      <main className="mx-auto max-w-7xl px-4 py-8">
        {/* Document Viewer Modal */}
        <DocumentViewer
          isOpen={!!selectedDoc}
          onClose={() => setSelectedDoc(null)}
          document={selectedDoc}
          uploaderId={selectedDoc?.uploader_id}
          currentUserId={user?.id}
          onDelete={handleDelete}
        />

        <h1 className="mb-8 text-3xl font-bold text-gray-800">The Vault</h1>
        
        {/* Smart Chips Filter */}
        <div className="mb-8 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <div className="mb-4">
            <h2 className="mb-2 text-lg font-semibold text-gray-700">Filter by Sender</h2>
            <div className="flex flex-wrap gap-2">
              {senders.map((sender) => (
                <button
                  key={sender}
                  onClick={() => updateFilter('sender', sender)}
                  className={`rounded-full px-4 py-2 text-sm transition-all ${
                    filters.sender === sender
                      ? 'bg-purple-600 text-white shadow-sm'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
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
                  className={`rounded-full px-4 py-2 text-sm transition-all ${
                    filters.event_type === event
                      ? 'bg-cyan-600 text-white shadow-sm'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
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
                  className={`rounded-full px-4 py-2 text-sm transition-all ${
                    filters.year === year.toString()
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {year}
                </button>
              ))}
            </div>
          </div>
          
          {/* Active Filters */}
          {(filters.sender || filters.event_type || filters.year) && (
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <span className="text-sm text-gray-600">Active filters:</span>
              {filters.sender && (
                <span className="flex items-center gap-1 rounded-full bg-purple-600 px-3 py-1 text-sm text-white">
                  {filters.sender}
                  <button onClick={() => clearFilter('sender')}>
                    <X className="h-4 w-4" />
                  </button>
                </span>
              )}
              {filters.event_type && (
                <span className="flex items-center gap-1 rounded-full bg-cyan-600 px-3 py-1 text-sm text-white">
                  {filters.event_type}
                  <button onClick={() => clearFilter('event_type')}>
                    <X className="h-4 w-4" />
                  </button>
                </span>
              )}
              {filters.year && (
                <span className="flex items-center gap-1 rounded-full bg-indigo-600 px-3 py-1 text-sm text-white">
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
        <div className="rounded-xl bg-gradient-to-br from-amber-50/40 to-orange-50/40 p-6 border border-amber-100">
          {documents.length === 0 ? (
            <div className="rounded-lg border border-dashed border-amber-200 bg-white/50 p-16 text-center">
              <p className="text-lg text-gray-600">No documents found. Try adjusting your filters.</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-6">
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className="group cursor-pointer overflow-hidden rounded-lg bg-white shadow-sm transition-all hover:shadow-md hover:-translate-y-0.5 border border-gray-100"
                  onClick={() => setSelectedDoc(doc)}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={doc.s3_thumbnail_url}
                    alt={doc.metadata?.sender_name || 'Document'}
                    className="h-48 w-full object-cover transition-transform group-hover:scale-105"
                  />
                  <div className="p-3">
                    <p className="text-sm font-medium text-gray-900">
                      {doc.metadata?.sender_name}
                    </p>
                    <p className="text-xs text-gray-600">{doc.metadata?.event_type}</p>
                    <p className="text-xs text-gray-500 mt-1">
                      {new Date(doc.metadata?.doc_date).toLocaleDateString()}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default function VaultPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-red-900" />
        </div>
      }
    >
      <VaultContent />
    </Suspense>
  );
}

