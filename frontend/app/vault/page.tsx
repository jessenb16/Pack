'use client';

import { Suspense, useEffect, useState } from 'react';
import { useUser, useAuth } from '@clerk/nextjs';
import { useRouter, useSearchParams } from 'next/navigation';
import Navbar from '@/components/Navbar';
import DocumentViewer, { type DocumentViewerDocument, type LabelCatalog } from '@/components/DocumentViewer';
import { apiClient } from '@/lib/api';
import { formatDocDate, parseLocalDate } from '@/lib/date';
import { X, Loader2 } from 'lucide-react';

function VaultContent() {
  const { user, isLoaded } = useUser();
  const { getToken, orgId } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [documents, setDocuments] = useState<DocumentViewerDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [catalog, setCatalog] = useState<LabelCatalog>({
    senders: [],
    event_types: [],
    recipients: [],
  });
  const [years, setYears] = useState<number[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<DocumentViewerDocument | null>(null);

  const [filters, setFilters] = useState({
    sender_id: searchParams.get('sender_id') || '',
    event_type_id: searchParams.get('event_type_id') || '',
    year: searchParams.get('year') || '',
  });

  useEffect(() => {
    if (!isLoaded) return;

    if (!user) {
      router.push('/login');
      return;
    }

    if (!orgId) {
      setLoading(false);
      return;
    }
    loadDocuments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, isLoaded, orgId, filters.sender_id, filters.event_type_id, filters.year]);

  useEffect(() => {
    if (!orgId) return;
    setDocuments([]);
    setCatalog({ senders: [], event_types: [], recipients: [] });
    setYears([]);
    setSelectedDoc(null);
  }, [orgId]);

  async function loadDocuments() {
    try {
      setLoading(true);
      const token = await getToken({ organizationId: orgId || undefined });
      const [familyResponse, response] = await Promise.all([
        apiClient.getFamily(token),
        apiClient.getDocuments(
          {
            sender_id: filters.sender_id || undefined,
            event_type_id: filters.event_type_id || undefined,
            year: filters.year ? parseInt(filters.year, 10) : undefined,
          },
          token
        ),
      ]);
      if (familyResponse.data) {
        const d = familyResponse.data as Record<string, unknown>;
        setCatalog({
          senders: Array.isArray(d.senders) ? (d.senders as LabelCatalog['senders']) : [],
          event_types: Array.isArray(d.event_types) ? (d.event_types as LabelCatalog['event_types']) : [],
          recipients: Array.isArray(d.recipients) ? (d.recipients as LabelCatalog['recipients']) : [],
        });
      }

      if (response.data) {
        const docs = response.data;
        setDocuments(docs);

        const uniqueYears = new Set<number>();
        docs.forEach((doc) => {
          if (doc.metadata?.doc_date) {
            const date = parseLocalDate(doc.metadata.doc_date);
            if (date) uniqueYears.add(date.getFullYear());
          }
        });
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
      const token = await getToken({ organizationId: orgId || undefined });
      const response = await apiClient.deleteDocument(documentId, token);

      if (response.error) {
        alert(`Error deleting document: ${response.error}`);
        return;
      }

      setDocuments(documents.filter((doc) => doc.id !== documentId));
      setSelectedDoc(null);
    } catch (error) {
      console.error('Error deleting document:', error);
      alert('Failed to delete document. Please try again.');
    }
  }

  const activeSenderLabel = catalog.senders.find((s) => s.id === filters.sender_id)?.label;
  const activeEventLabel = catalog.event_types.find((e) => e.id === filters.event_type_id)?.label;

  const showInitialLoadingScreen = !isLoaded;
  const showDocumentsLoading = loading && documents.length === 0;

  return (
    <div className="min-h-screen bg-gradient-to-br from-stone-100 via-slate-50 to-stone-100">
      <Navbar />

      <main className="mx-auto max-w-7xl px-4 py-8">
        {showInitialLoadingScreen ? (
          <div className="flex min-h-[60vh] items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-red-900" />
          </div>
        ) : null}
        <DocumentViewer
          isOpen={!!selectedDoc}
          onClose={() => setSelectedDoc(null)}
          document={selectedDoc}
          uploaderId={selectedDoc?.uploader_id}
          currentUserId={user?.id}
          onDelete={handleDelete}
          catalog={catalog}
          getAccessToken={() => getToken({ organizationId: orgId || undefined })}
          organizationId={orgId}
          onDocumentUpdated={(updated) => {
            setDocuments((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
            setSelectedDoc(updated);
            void loadDocuments();
          }}
        />

        <h1 className="mb-8 text-3xl font-bold text-gray-800">The Vault</h1>

        {loading && documents.length > 0 ? (
          <div className="mb-4 flex items-center gap-2 text-sm text-gray-600">
            <Loader2 className="h-4 w-4 animate-spin" />
            Updating…
          </div>
        ) : null}

        <div className="mb-8 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <div className="mb-4">
            <h2 className="mb-2 text-lg font-semibold text-gray-700">Filter by Sender/Poster</h2>
            <div className="flex flex-wrap gap-2">
              {catalog.senders.map((sender) => (
                <button
                  key={sender.id}
                  type="button"
                  onClick={() => updateFilter('sender_id', sender.id)}
                  className={`rounded-full px-4 py-2 text-sm transition-all ${
                    filters.sender_id === sender.id
                      ? 'bg-purple-600 text-white shadow-sm'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {sender.label}
                </button>
              ))}
            </div>
          </div>

          <div className="mb-4">
            <h2 className="mb-2 text-lg font-semibold text-gray-700">Filter by Event</h2>
            <div className="flex flex-wrap gap-2">
              {catalog.event_types.map((event) => (
                <button
                  key={event.id}
                  type="button"
                  onClick={() => updateFilter('event_type_id', event.id)}
                  className={`rounded-full px-4 py-2 text-sm transition-all ${
                    filters.event_type_id === event.id
                      ? 'bg-cyan-600 text-white shadow-sm'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {event.label}
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
                  type="button"
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

          {(filters.sender_id || filters.event_type_id || filters.year) && (
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <span className="text-sm text-gray-600">Active filters:</span>
              {filters.sender_id && (
                <span className="flex items-center gap-1 rounded-full bg-purple-600 px-3 py-1 text-sm text-white">
                  {activeSenderLabel || filters.sender_id}
                  <button type="button" onClick={() => clearFilter('sender_id')}>
                    <X className="h-4 w-4" />
                  </button>
                </span>
              )}
              {filters.event_type_id && (
                <span className="flex items-center gap-1 rounded-full bg-cyan-600 px-3 py-1 text-sm text-white">
                  {activeEventLabel || filters.event_type_id}
                  <button type="button" onClick={() => clearFilter('event_type_id')}>
                    <X className="h-4 w-4" />
                  </button>
                </span>
              )}
              {filters.year && (
                <span className="flex items-center gap-1 rounded-full bg-indigo-600 px-3 py-1 text-sm text-white">
                  {filters.year}
                  <button type="button" onClick={() => clearFilter('year')}>
                    <X className="h-4 w-4" />
                  </button>
                </span>
              )}
            </div>
          )}
        </div>

        <div className="rounded-xl bg-gradient-to-br from-amber-50/40 to-orange-50/40 p-6 border border-amber-100">
          {showDocumentsLoading ? (
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-6">
              {Array.from({ length: 12 }).map((_, i) => (
                <div
                  // eslint-disable-next-line react/no-array-index-key
                  key={i}
                  className="overflow-hidden rounded-lg bg-white shadow-sm border border-gray-100"
                >
                  <div className="h-48 w-full bg-gray-100 animate-pulse" />
                  <div className="p-3">
                    <div className="h-4 w-3/4 bg-gray-100 animate-pulse rounded" />
                    <div className="mt-2 h-3 w-1/2 bg-gray-100 animate-pulse rounded" />
                    <div className="mt-2 h-3 w-1/3 bg-gray-100 animate-pulse rounded" />
                  </div>
                </div>
              ))}
            </div>
          ) : documents.length === 0 ? (
            <div className="rounded-lg border border-dashed border-amber-200 bg-white/50 p-16 text-center">
              <p className="text-lg text-gray-600">No documents found. Try adjusting your filters.</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-6">
              {documents.map((doc) => {
                const s = doc.metadata.sender.label;
                const r = doc.metadata.recipient?.label;
                const ev = doc.metadata.event_type.label;
                return (
                  <div
                    key={doc.id}
                    className="group cursor-pointer overflow-hidden rounded-lg bg-white shadow-sm transition-all hover:shadow-md hover:-translate-y-0.5 border border-gray-100"
                    onClick={() => setSelectedDoc(doc)}
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={doc.s3_thumbnail_url}
                      alt={r ? `${s} to ${r}` : s || 'Document'}
                      className="h-48 w-full object-cover transition-transform group-hover:scale-105"
                    />
                    <div className="p-3">
                      <p className="text-sm font-medium text-gray-900">
                        {r ? `${s} to ${r}` : s}
                      </p>
                      <p className="text-xs text-gray-600">{ev}</p>
                      <p className="text-xs text-gray-500 mt-1">
                        {formatDocDate(doc.metadata?.doc_date ?? '')}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default function VaultPage() {
  // Next.js requires useSearchParams() consumers to be wrapped in Suspense.
  // Keep fallback lightweight to avoid a blank/black screen flash.
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-gradient-to-br from-stone-100 via-slate-50 to-stone-100">
          <Navbar />
          <main className="mx-auto max-w-7xl px-4 py-8">
            <div className="flex min-h-[60vh] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-red-900" />
            </div>
          </main>
        </div>
      }
    >
      <VaultContent />
    </Suspense>
  );
}
