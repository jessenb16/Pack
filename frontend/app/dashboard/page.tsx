'use client';

import { useEffect, useState } from 'react';
import { useUser, useAuth } from '@clerk/nextjs';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import Navbar from '@/components/Navbar';
import DocumentViewer, { type DocumentViewerDocument } from '@/components/DocumentViewer';
import { apiClient } from '@/lib/api';
import { parseLocalDate } from '@/lib/date';
import { Calendar, Image as ImageIcon, Loader2, Mail, Users, ArrowRight } from 'lucide-react';

export default function DashboardPage() {
  const { user, isLoaded } = useUser();
  const { getToken, orgId } = useAuth();
  const router = useRouter();
  const [recentDocs, setRecentDocs] = useState<DocumentViewerDocument[]>([]);
  const [onThisDay, setOnThisDay] = useState<DocumentViewerDocument[]>([]);
  const [family, setFamily] = useState<Record<string, unknown> | null>(null);
  const [members, setMembers] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDoc, setSelectedDoc] = useState<DocumentViewerDocument | null>(null);
  const [nameForm, setNameForm] = useState({ firstName: '', lastName: '' });
  const [nameSaving, setNameSaving] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);

  const needsName = isLoaded && user && !(user.firstName?.trim());

  useEffect(() => {
    if (user && needsName && !nameForm.firstName && !nameForm.lastName) {
      setNameForm({
        firstName: user.firstName?.trim() ?? '',
        lastName: user.lastName?.trim() ?? '',
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only prefill once; including nameForm would reset on every keystroke
  }, [user, needsName]);

  async function handleSaveName(e: React.FormEvent) {
    e.preventDefault();
    if (!user || !nameForm.firstName.trim()) return;
    setNameError(null);
    setNameSaving(true);
    try {
      await user.update({
        firstName: nameForm.firstName.trim(),
        lastName: nameForm.lastName.trim() || undefined,
      });
    } catch (err) {
      setNameError(err instanceof Error ? err.message : 'Failed to save name');
    } finally {
      setNameSaving(false);
    }
  }

  useEffect(() => {
    if (!isLoaded) return;
    
    if (!user) {
      router.push('/login');
      return;
    }

    if (!orgId) return;
    loadDashboard();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, isLoaded, orgId]);

  async function loadDashboard() {
    try {
      // Get token - backend will fetch org from Clerk API if not in token
      const token = await getToken({ organizationId: orgId || undefined });
      
      if (!token) {
        console.error('Failed to get token from Clerk');
        setLoading(false);
        return;
      }
      
      // Make all API calls in parallel for better performance
      const [familyResponse, documentsResponse] = await Promise.all([
        apiClient.getFamily(token),
        apiClient.getDocuments(undefined, token)
      ]);
      
      // Handle family response (includes members already)
      if (familyResponse.data) {
        setFamily(familyResponse.data);
        // Members are already included in familyResponse.data.members
        setMembers(Array.isArray(familyResponse.data.members) ? (familyResponse.data.members as Record<string, unknown>[]) : []);
      } else if (familyResponse.error) {
        // If error is about no organization, that's okay - user just needs to create one
        if (familyResponse.error.includes('not part of an organization') || 
            familyResponse.error.includes('404') ||
            familyResponse.error.includes('403')) {
          setFamily(null);
          setMembers([]);
        } else {
          console.error('Error loading family:', familyResponse.error);
        }
      }
      
      // Handle documents response
      if (documentsResponse.data) {
        const docs = documentsResponse.data as unknown as DocumentViewerDocument[];
        setRecentDocs(docs.slice(0, 20));
        
        // Get "On This Day" documents
        const today = new Date();
        const todayStr = `${today.getMonth() + 1}-${today.getDate()}`;
        const onThisDayDocs = docs.filter((doc) => {
          const docDate = doc.metadata?.doc_date;
          if (!docDate) return false;
          const date = parseLocalDate(docDate);
          if (!date) return false;
          const dateStr = `${date.getMonth() + 1}-${date.getDate()}`;
          return dateStr === todayStr;
        });
        setOnThisDay(onThisDayDocs);
      }
    } catch (error) {
      console.error('Error loading dashboard:', error);
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(documentId: string) {
    try {
      const token = await getToken({ organizationId: orgId || undefined });
      const response = await apiClient.deleteDocument(documentId, token);
      
      if (response.error) {
        alert(`Error deleting document: ${response.error}`);
        return;
      }

      // Remove document from local state
      setRecentDocs(recentDocs.filter(doc => doc.id !== documentId));
      setOnThisDay(onThisDay.filter(doc => doc.id !== documentId));
      
      // Close the modal
      setSelectedDoc(null);
    } catch (error) {
      console.error('Error deleting document:', error);
      alert('Failed to delete document. Please try again.');
    }
  }

  if (!isLoaded) {
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

        {/* Ask invited users (or anyone without a name) to set their display name */}
        {needsName && (
          <section className="mb-8 rounded-xl border border-purple-200 bg-gradient-to-r from-purple-50/80 to-indigo-50/80 p-6 shadow-md">
            <h2 className="mb-2 text-xl font-bold text-gray-900">What should we call you?</h2>
            <p className="mb-4 text-gray-600">
              Enter your first and last name so your family can recognize you in Pack.
            </p>
            <form onSubmit={handleSaveName} className="flex flex-wrap items-end gap-4">
              <div>
                <label htmlFor="firstName" className="mb-1 block text-sm font-medium text-gray-700">
                  First name
                </label>
                <input
                  id="firstName"
                  type="text"
                  required
                  value={nameForm.firstName}
                  onChange={(e) => setNameForm((f) => ({ ...f, firstName: e.target.value }))}
                  placeholder="First name"
                  className="rounded-lg border border-gray-300 px-3 py-2 focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500"
                  autoComplete="given-name"
                />
              </div>
              <div>
                <label htmlFor="lastName" className="mb-1 block text-sm font-medium text-gray-700">
                  Last name
                </label>
                <input
                  id="lastName"
                  type="text"
                  value={nameForm.lastName}
                  onChange={(e) => setNameForm((f) => ({ ...f, lastName: e.target.value }))}
                  placeholder="Last name"
                  className="rounded-lg border border-gray-300 px-3 py-2 focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500"
                  autoComplete="family-name"
                />
              </div>
              <button
                type="submit"
                disabled={nameSaving || !nameForm.firstName.trim()}
                className="rounded-lg bg-purple-600 px-4 py-2 text-white transition-colors hover:bg-purple-700 disabled:opacity-50"
              >
                {nameSaving ? 'Saving…' : 'Save'}
              </button>
            </form>
            {nameError && (
              <p className="mt-2 text-sm text-red-600">{nameError}</p>
            )}
          </section>
        )}

        <h1 className="mb-8 text-3xl font-bold text-gray-800">Dashboard</h1>
        
        {loading && (
          <div className="mb-4 flex items-center justify-center">
            <Loader2 className="h-5 w-5 animate-spin text-purple-600" />
            <span className="ml-2 text-gray-600">Loading...</span>
          </div>
        )}
        
        {/* No Organization Message */}
        {!loading && !family && (
          <section className="mb-8 rounded-xl border border-amber-200 bg-gradient-to-r from-amber-50/80 to-orange-50/80 p-6 shadow-md">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-4">
                <div className="rounded-full bg-amber-100 p-3">
                  <Users className="h-6 w-6 text-amber-700" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-gray-900">Create Your Family Organization</h2>
                  <p className="text-gray-600">
                    Create a family organization to start organizing your memories and inviting family members.
                  </p>
                </div>
              </div>
              <Link
                href="/family-setup"
                className="flex items-center gap-2 rounded-lg bg-red-900 px-6 py-3 text-white transition-all hover:bg-red-800 shadow-sm"
              >
                <span>Create Family</span>
                <ArrowRight className="h-5 w-5" />
              </Link>
            </div>
          </section>
        )}

        {/* Invite Family Members - Prominent Section */}
        {!loading && family && (
          <section className="mb-8 rounded-xl border border-blue-200 bg-gradient-to-r from-blue-50/80 to-indigo-50/80 p-6 shadow-md">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-4">
                <div className="rounded-full bg-blue-100 p-3">
                  <Mail className="h-6 w-6 text-blue-700" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-gray-900">Invite Family Members</h2>
                  <p className="text-gray-600">
                    {members.length === 1 
                      ? "You're the only member. Invite others to start sharing memories!"
                      : `${members.length} family member${members.length > 1 ? 's' : ''} in ${family.name}`
                    }
                  </p>
                </div>
              </div>
              <Link
                href="/family-settings"
                className="flex items-center gap-2 rounded-lg bg-red-900 px-6 py-3 text-white transition-all hover:bg-red-800 shadow-sm"
              >
                <span>Invite Now</span>
                <ArrowRight className="h-5 w-5" />
              </Link>
            </div>
          </section>
        )}
        
        {/* Recent Uploads */}
        <section className="mb-12 rounded-xl bg-gradient-to-br from-amber-50/60 to-orange-50/60 p-6 shadow-md border border-amber-100">
          <div className="mb-4 flex items-center gap-2">
            <h2 className="text-2xl font-semibold text-gray-800">Recent Uploads</h2>
            <ImageIcon className="h-6 w-6 text-amber-600" />
          </div>
          {loading ? (
            <div className="flex h-48 items-center justify-center rounded-lg border border-dashed border-amber-200 bg-white/50">
              <Loader2 className="h-8 w-8 animate-spin text-amber-500" />
            </div>
          ) : recentDocs.length === 0 ? (
            <div className="rounded-lg border border-dashed border-amber-200 bg-white/50 p-12 text-center">
              <p className="text-gray-600">No documents yet. Upload your first memory!</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-6">
              {recentDocs.map((doc) => (
                <div
                  key={doc.id}
                  className="group cursor-pointer overflow-hidden rounded-lg bg-white shadow-sm transition-all hover:shadow-md hover:-translate-y-0.5 border border-gray-100"
                  onClick={() => setSelectedDoc(doc)}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={doc.s3_thumbnail_url}
                    alt={doc.metadata?.recipient_name ? `${doc.metadata.sender_name} to ${doc.metadata.recipient_name}` : doc.metadata?.sender_name || 'Document'}
                    className="h-48 w-full object-cover transition-transform group-hover:scale-105"
                  />
                  <div className="p-3">
                    <p className="text-sm font-medium text-gray-900">
                      {doc.metadata?.recipient_name
                        ? `${doc.metadata.sender_name} to ${doc.metadata.recipient_name}`
                        : doc.metadata?.sender_name}
                    </p>
                    <p className="text-xs text-gray-600">{doc.metadata?.event_type}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* On This Day */}
        {!loading && onThisDay.length > 0 && (
          <section className="rounded-xl border border-purple-200 bg-gradient-to-br from-purple-50/60 to-blue-50/60 p-6 shadow-md">
            <div className="mb-4 flex items-center gap-3">
              <div className="rounded-full bg-purple-100 p-2.5">
                <Calendar className="h-5 w-5 text-purple-700" />
              </div>
              <h2 className="text-2xl font-semibold text-gray-800">On This Day</h2>
            </div>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-6">
              {onThisDay.map((doc) => (
                <div
                  key={doc.id}
                  className="group cursor-pointer overflow-hidden rounded-lg bg-white shadow-sm transition-all hover:shadow-md hover:scale-105 border border-gray-100"
                  onClick={() => setSelectedDoc(doc)}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={doc.s3_thumbnail_url}
                    alt={doc.metadata?.recipient_name ? `${doc.metadata.sender_name} to ${doc.metadata.recipient_name}` : doc.metadata?.sender_name || 'Document'}
                    className="h-48 w-full object-cover transition-transform group-hover:scale-105"
                  />
                  <div className="p-3">
                    <p className="text-sm font-medium text-gray-900">
                      {doc.metadata?.recipient_name
                        ? `${doc.metadata.sender_name} to ${doc.metadata.recipient_name}`
                        : doc.metadata?.sender_name}
                    </p>
                    <p className="text-xs text-gray-600">{doc.metadata?.event_type}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

