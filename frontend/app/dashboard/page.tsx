'use client';

import { useEffect, useState } from 'react';
import { useUser, useAuth } from '@clerk/nextjs';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import Navbar from '@/components/Navbar';
import DocumentViewer, { type DocumentViewerDocument, type LabelCatalog } from '@/components/DocumentViewer';
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
  const [labelCatalog, setLabelCatalog] = useState<LabelCatalog>({
    senders: [],
    event_types: [],
    recipients: [],
  });
  const [nameForm, setNameForm] = useState({ firstName: '', lastName: '' });
  const [nameSaving, setNameSaving] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);

  const memberLimit = 5;
  const atMemberLimit = members.length >= memberLimit;

  const needsName = isLoaded && user && !(user.firstName?.trim());

  function getMemberInitials(name: string) {
    const parts = name.split(' ').filter(Boolean);
    if (parts.length === 0) return '?';
    return parts.slice(0, 2).map((part) => part[0]).join('').toUpperCase();
  }

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
      const last = nameForm.lastName.trim();
      await user.update({
        firstName: nameForm.firstName.trim(),
        lastName: last || null,
        unsafeMetadata: {
          ...(user.unsafeMetadata ?? {}),
          packLastNameSet: Boolean(last),
        },
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

    if (!orgId) {
      setLoading(false);
      return;
    }
    loadDashboard();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, isLoaded, orgId]);

  useEffect(() => {
    if (!orgId) return;
    setLabelCatalog({ senders: [], event_types: [], recipients: [] });
  }, [orgId]);

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
        const fd = familyResponse.data as Record<string, unknown>;
        setLabelCatalog({
          senders: Array.isArray(fd.senders) ? (fd.senders as LabelCatalog['senders']) : [],
          event_types: Array.isArray(fd.event_types) ? (fd.event_types as LabelCatalog['event_types']) : [],
          recipients: Array.isArray(fd.recipients) ? (fd.recipients as LabelCatalog['recipients']) : [],
        });
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
        const docs = documentsResponse.data;
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

        // If we were linked here with ?focus=<document_id>, open that doc.
        if (typeof window !== 'undefined') {
          const focusId = new URLSearchParams(window.location.search).get('focus');
          if (focusId) {
            const focused = docs.find((d) => d.id === focusId);
            if (focused) {
              setSelectedDoc(focused);
              // Best-effort: bring the user to the top of the page content.
              window.scrollTo({ top: 0, behavior: 'smooth' });
            } else {
              // Fallback: if the focused doc isn't in the recent list, fetch it by id.
              try {
                const focusedRes = await apiClient.getDocument(focusId, token);
                if (focusedRes.data) {
                  setSelectedDoc(focusedRes.data);
                  window.scrollTo({ top: 0, behavior: 'smooth' });
                } else if (focusedRes.error) {
                  console.error('Error loading focused document:', focusedRes.error);
                }
              } catch (err) {
                console.error('Error loading focused document:', err);
              }
            }
          }
        }
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

  const showInitialLoadingScreen = !isLoaded;

  return (
    <div className="min-h-screen bg-gradient-to-br from-stone-100 via-slate-50 to-stone-100">
      <Navbar />
      
      <main className="mx-auto max-w-7xl px-4 py-8">
        {showInitialLoadingScreen ? (
          <div className="flex min-h-[60vh] items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-red-900" />
          </div>
        ) : null}
        {/* Document Viewer Modal */}
        <DocumentViewer
          isOpen={!!selectedDoc}
          onClose={() => setSelectedDoc(null)}
          document={selectedDoc}
          uploaderId={selectedDoc?.uploader_id}
          currentUserId={user?.id}
          onDelete={handleDelete}
          catalog={labelCatalog}
          getAccessToken={() => getToken({ organizationId: orgId || undefined })}
          organizationId={orgId}
          onDocumentUpdated={(updated) => {
            setRecentDocs((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
            setOnThisDay((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
            setSelectedDoc(updated);
          }}
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

        {/* No Organization Message */}
        {!loading && !family && (
          <section className="mb-8 rounded-xl border border-amber-200 bg-gradient-to-r from-amber-50/80 to-orange-50/80 p-6 shadow-md">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-4">
                <div className="rounded-full bg-amber-100 p-3">
                  <Users className="h-6 w-6 text-amber-700" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-gray-900">Create Your Pack</h2>
                  <p className="text-gray-600">
                    Create a Pack to start organizing your memories and inviting members.
                  </p>
                </div>
              </div>
              <Link
                href="/family-setup"
                className="flex items-center gap-2 rounded-lg bg-red-900 px-6 py-3 text-white transition-all hover:bg-red-800 shadow-sm"
              >
                <span>Create Pack</span>
                <ArrowRight className="h-5 w-5" />
              </Link>
            </div>
          </section>
        )}

        {/* People in Your Pack */}
        {!loading && members.length > 0 && (
          <section className="mb-8 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Users className="h-5 w-5 text-teal-600" />
                <h2 className="text-xl font-semibold text-gray-800">People in Your Pack</h2>
              </div>
              {family && (
                <div className="flex items-center gap-3 text-sm text-gray-600">
                  <span>
                    {members.length === 1
                      ? "You're the only member."
                      : `${members.length} pack members`}
                  </span>
                  {atMemberLimit && (
                    <span className="text-xs text-gray-500">Member limit reached</span>
                  )}
                  <Link
                    href="/family-settings#invite-family"
                    className={`inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-xs font-semibold shadow-sm transition-colors ${
                      atMemberLimit
                        ? 'cursor-not-allowed bg-gray-300 text-gray-500'
                        : 'bg-red-900 text-white hover:bg-red-800'
                    }`}
                    onClick={(event) => {
                      if (atMemberLimit) {
                        event.preventDefault();
                        return;
                      }
                      if (typeof window !== 'undefined') {
                        window.sessionStorage.setItem('scrollToInvite', '1');
                      }
                    }}
                  >
                    Invite
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </div>
              )}
            </div>
            <div className="flex gap-4 overflow-x-auto pb-2">
              {members.map((member, idx) => {
                const memberName = typeof member.name === 'string' ? member.name : String(member.name ?? '');
                const imageUrl = typeof member.image_url === 'string' ? member.image_url : '';
                const initials = getMemberInitials(memberName);
                const key = typeof member.id === 'string' || typeof member.id === 'number'
                  ? String(member.id)
                  : `member-${idx}`;
                return (
                  <div key={key} className="flex w-28 flex-shrink-0 flex-col items-center text-center">
                    <div className="flex h-14 w-14 items-center justify-center overflow-hidden rounded-full bg-gray-100 text-base font-semibold text-gray-700">
                      {imageUrl ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={imageUrl} alt={memberName || 'Member'} className="h-full w-full object-cover" />
                      ) : (
                        <span>{initials}</span>
                      )}
                    </div>
                    <p className="mt-2 w-full truncate text-sm text-gray-700">
                      {memberName || 'Unknown'}
                    </p>
                  </div>
                );
              })}
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
              {recentDocs.map((doc) => {
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
                    </div>
                  </div>
                );
              })}
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
              {onThisDay.map((doc) => {
                const s = doc.metadata.sender.label;
                const r = doc.metadata.recipient?.label;
                const ev = doc.metadata.event_type.label;
                return (
                  <div
                    key={doc.id}
                    className="group cursor-pointer overflow-hidden rounded-lg bg-white shadow-sm transition-all hover:shadow-md hover:scale-105 border border-gray-100"
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
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

