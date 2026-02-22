'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useUser, useAuth } from '@clerk/nextjs';
import { useRouter } from 'next/navigation';
import Navbar from '@/components/Navbar';
import { apiClient } from '@/lib/api';
import { Loader2, Mail, X, Users } from 'lucide-react';

interface Invitation {
  id: string;
  email: string;
  status: string;
  created_at: string;
}

export default function FamilySettingsPage() {
  const { user, isLoaded } = useUser();
  const { getToken, orgId } = useAuth();
  const router = useRouter();
  const [family, setFamily] = useState<Record<string, unknown> | null>(null);
  const [members, setMembers] = useState<Record<string, unknown>[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [loading, setLoading] = useState(true);
  const [inviteEmail, setInviteEmail] = useState('');
  const [sending, setSending] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [bypassMembersCacheUntil, setBypassMembersCacheUntil] = useState(0);
  const lastImageUrlRef = useRef<string | null>(null);
  const profileInputRef = useRef<HTMLInputElement | null>(null);
  const [profileUploading, setProfileUploading] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const memberLimit = 5;
  const atMemberLimit = members.length >= memberLimit;

  const loadFamilyData = useCallback(async (bustMembersCache = false) => {
    try {
      setLoading(true);
      // Get token - backend will fetch org from Clerk API if not in token
      const token = await getToken({ organizationId: orgId || undefined });
      
      if (!token) {
        setMessage({ type: 'error', text: 'Failed to get authentication token' });
        setLoading(false);
        return;
      }
      
      // Make all API calls in parallel for better performance
      const shouldBust = bustMembersCache || Date.now() < bypassMembersCacheUntil;
      const [familyResponse, invitationsResponse] = await Promise.all([
        apiClient.getFamily(token, { bustMembersCache: shouldBust }),
        apiClient.getInvitations(token).catch(err => ({ error: err.message })) // Don't fail if invitations fail
      ]);
      
      // Handle family response (includes members already)
      if (familyResponse.data) {
        setFamily(familyResponse.data);
        // Members are already included in familyResponse.data.members
        setMembers(Array.isArray(familyResponse.data.members) ? (familyResponse.data.members as Record<string, unknown>[]) : []);
      } else if (familyResponse.error) {
        // If user doesn't have an organization, redirect to setup
        if (familyResponse.error.includes('not part of an organization') || 
            familyResponse.error.includes('404')) {
          router.push('/family-setup');
          return;
        }
        setMessage({ type: 'error', text: familyResponse.error });
        setLoading(false);
        return;
      }
      
      // Handle invitations response (catch returns { error } so narrow with 'data' in)
      if ('data' in invitationsResponse && invitationsResponse.data) {
        setInvitations(Array.isArray(invitationsResponse.data) ? (invitationsResponse.data as unknown as Invitation[]) : []);
      } else if ('error' in invitationsResponse && invitationsResponse.error) {
        // Invitations might fail if user doesn't have permission, that's okay
        console.warn('Could not load invitations:', invitationsResponse.error);
        setInvitations([]);
      }
    } catch (error) {
      console.error('Error loading family data:', error);
      setMessage({ type: 'error', text: 'Failed to load family data. Please try again.' });
    } finally {
      setLoading(false);
    }
  }, [getToken, orgId, bypassMembersCacheUntil]);

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
    loadFamilyData();
  }, [user, isLoaded, orgId, router, loadFamilyData]);

  useEffect(() => {
    if (!user) return;
    const currentImageUrl = user.imageUrl || null;
    const previousImageUrl = lastImageUrlRef.current;
    if (previousImageUrl && currentImageUrl && previousImageUrl !== currentImageUrl) {
      const until = Date.now() + 30_000;
      setBypassMembersCacheUntil(until);
      loadFamilyData(true);
    }
    lastImageUrlRef.current = currentImageUrl;
  }, [user, loadFamilyData]);

  useEffect(() => {
    if (!isLoaded || loading) return;
    const shouldScroll =
      typeof window !== 'undefined' &&
      window.sessionStorage.getItem('scrollToInvite') === '1';
    const targetId = 'invite-family';
    const el = document.getElementById(targetId);
    if (!shouldScroll || !el) return;
    const id = window.setTimeout(() => {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      window.sessionStorage.removeItem('scrollToInvite');
    }, 50);
    return () => window.clearTimeout(id);
  }, [isLoaded, loading]);

  async function handleProfileImageChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !user) return;
    setProfileError(null);
    setProfileUploading(true);
    try {
      await user.setProfileImage({ file });
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : 'Failed to update profile photo');
    } finally {
      setProfileUploading(false);
      if (profileInputRef.current) {
        profileInputRef.current.value = '';
      }
    }
  }

  async function handleSendInvitation(e: React.FormEvent) {
    e.preventDefault();
    if (!inviteEmail.trim()) return;

    setSending(true);
    setMessage(null);

    try {
      const token = await getToken({ organizationId: orgId || undefined });
      
      if (!token) {
        setMessage({ type: 'error', text: 'Failed to get authentication token' });
        setSending(false);
        return;
      }
      const response = await apiClient.sendInvitation(inviteEmail.trim(), token);
      
      if (response.data) {
        setMessage({ type: 'success', text: `Invitation sent to ${inviteEmail}!` });
        setInviteEmail('');
        // Reload invitations
        const invitationsResponse = await apiClient.getInvitations(token);
        if (invitationsResponse.data) {
          setInvitations(Array.isArray(invitationsResponse.data) ? (invitationsResponse.data as unknown as Invitation[]) : []);
        }
      } else {
        setMessage({ type: 'error', text: response.error || 'Failed to send invitation' });
      }
    } catch (error) {
      console.error('Error sending invitation:', error);
      setMessage({ type: 'error', text: 'Network error. Please try again.' });
    } finally {
      setSending(false);
    }
  }

  async function handleRevokeInvitation(invitationId: string) {
    if (!confirm('Are you sure you want to revoke this invitation?')) return;

    try {
      const token = await getToken({ organizationId: orgId || undefined });
      
      if (!token) {
        setMessage({ type: 'error', text: 'Failed to get authentication token' });
        return;
      }
      const response = await apiClient.revokeInvitation(invitationId, token);
      
      if (response.data) {
        setMessage({ type: 'success', text: 'Invitation revoked' });
        // Reload invitations
        const invitationsResponse = await apiClient.getInvitations(token);
        if (invitationsResponse.data) {
          setInvitations(Array.isArray(invitationsResponse.data) ? (invitationsResponse.data as unknown as Invitation[]) : []);
        }
      } else {
        setMessage({ type: 'error', text: response.error || 'Failed to revoke invitation' });
      }
    } catch (error) {
      console.error('Error revoking invitation:', error);
      setMessage({ type: 'error', text: 'Network error. Please try again.' });
    }
  }

  if (!isLoaded || loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-red-900" />
      </div>
    );
  }

  if (!family) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <main className="container mx-auto px-4 py-8">
          <p className="text-gray-600">You need to create a family first.</p>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-stone-100 via-slate-50 to-stone-100">
      <Navbar />
      
      <main className="container mx-auto max-w-4xl px-4 py-8">
        <h1 className="mb-8 text-3xl font-bold text-gray-800">Family Settings</h1>
        
        {loading && (
          <div className="mb-4 flex items-center justify-center">
            <Loader2 className="h-5 w-5 animate-spin text-red-900" />
            <span className="ml-2 text-gray-600">Loading...</span>
          </div>
        )}

        {/* Family Info */}
        <section className="mb-8 rounded-xl bg-white border border-gray-200 p-6 shadow-sm">
          <h2 className="mb-4 text-xl font-semibold text-gray-800">Family Information</h2>
          <div className="space-y-3 rounded-lg bg-blue-50/50 p-4">
            <p className="text-gray-700">
              <span className="font-semibold text-gray-900">Family Name:</span> {typeof family.name === 'string' ? family.name : String(family.name ?? '')}
            </p>
            <p className="text-gray-700">
              <span className="font-semibold text-gray-900">Created:</span>{' '}
              {(() => {
                const raw = family.created_at;
                if (raw == null) return '—';
                const d = typeof raw === 'string' || typeof raw === 'number' ? new Date(raw) : new Date(String(raw));
                return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString();
              })()}
            </p>
          </div>
        </section>

        {/* Profile */}
        <section className="mb-8 rounded-xl bg-white border border-gray-200 p-6 shadow-sm">
          <h2 className="mb-4 text-xl font-semibold text-gray-800">Your Profile Photo</h2>
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex h-16 w-16 items-center justify-center overflow-hidden rounded-full bg-gray-100 text-lg font-semibold text-gray-700">
              {user?.imageUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={user.imageUrl} alt="Profile" className="h-full w-full object-cover" />
              ) : (
                <span>{user?.firstName?.[0]?.toUpperCase() || '?'}</span>
              )}
            </div>
            <div>
              <input
                ref={profileInputRef}
                type="file"
                accept="image/*"
                onChange={handleProfileImageChange}
                className="hidden"
              />
              <button
                type="button"
                onClick={() => profileInputRef.current?.click()}
                disabled={profileUploading}
                className="rounded-lg bg-gray-900 px-4 py-2 text-sm text-white transition-colors hover:bg-gray-800 disabled:bg-gray-400"
              >
                {profileUploading ? 'Uploading...' : 'Update Photo'}
              </button>
              {profileError && (
                <p className="mt-2 text-sm text-red-600">{profileError}</p>
              )}
              <p className="mt-2 text-xs text-gray-500">
                Upload a square image for best results.
              </p>
            </div>
          </div>
        </section>

        {/* Family Members */}
        <section className="mb-8 rounded-xl bg-white border border-gray-200 p-6 shadow-sm">
          <div className="mb-4 flex items-center gap-2">
            <Users className="h-5 w-5 text-teal-600" />
            <h2 className="text-xl font-semibold text-gray-800">Family Members</h2>
          </div>
          {members.length === 0 ? (
            <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50 p-8 text-center">
              <p className="text-gray-600">No members yet.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {members.map((member, idx) => (
                <div key={typeof member.id === 'string' || typeof member.id === 'number' ? String(member.id) : `member-${idx}`} className="flex flex-col gap-2 rounded-lg border border-gray-200 bg-gray-50/50 p-3 transition-all hover:bg-gray-50 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <p className="truncate font-semibold text-gray-900">{typeof member.name === 'string' ? member.name : String(member.name ?? '')}</p>
                    {member.email != null && String(member.email).trim() !== '' && (
                      <p className="truncate text-sm text-gray-600">{String(member.email)}</p>
                    )}
                  </div>
                  <span className="flex-shrink-0 self-start rounded-full bg-teal-100 px-4 py-1.5 text-sm font-medium text-teal-700 sm:self-auto">
                    {typeof member.role === 'string' ? member.role : String(member.role ?? '')}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Send Invitation */}
        <section id="invite-family" className="mb-8 rounded-xl bg-white border border-gray-200 p-6 shadow-sm scroll-mt-24">
          <div className="mb-4 flex items-center gap-2">
            <Mail className="h-5 w-5 text-rose-600" />
            <h2 className="text-xl font-semibold text-gray-800">Invite Family Members</h2>
          </div>
          
          {message && (
            <div
              className={`mb-4 rounded-lg p-3 ${
                message.type === 'success' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
              }`}
            >
              {message.text}
            </div>
          )}
          {atMemberLimit && (
            <div className="mb-4 rounded-lg bg-amber-50 p-3 text-amber-800">
              Your plan allows up to {memberLimit} members. Remove a member to invite someone new.
            </div>
          )}

          <form onSubmit={handleSendInvitation} className="space-y-4">
            <div>
              <label htmlFor="invite_email" className="mb-2 block text-sm font-medium text-gray-700">
                Email Address
              </label>
              <input
                type="email"
                id="invite_email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="family.member@example.com"
                className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-red-900 focus:outline-none focus:ring-2 focus:ring-red-900"
                required
                disabled={sending || atMemberLimit}
              />
              <p className="mt-1 text-sm text-gray-500">
                The invitee will receive an email with a link to join. They&apos;ll create their account when they accept the invitation.
              </p>
            </div>
            <button
              type="submit"
              disabled={sending || !inviteEmail.trim() || atMemberLimit}
              className="rounded-lg bg-red-900 px-6 py-2 text-white transition-colors hover:bg-red-800 disabled:bg-gray-400"
            >
              {sending ? (
                <span className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Sending...
                </span>
              ) : (
                'Send Invitation'
              )}
            </button>
          </form>
        </section>

        {/* Pending Invitations */}
        {invitations.length > 0 && (
          <section className="rounded-lg bg-white p-6 shadow">
            <h2 className="mb-4 text-xl font-semibold text-gray-800">Pending Invitations</h2>
            <div className="space-y-2">
              {invitations.map((invitation) => (
                <div
                  key={invitation.id}
                  className="flex flex-col gap-2 rounded border p-3 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0">
                    <p className="truncate font-medium text-gray-900">{invitation.email}</p>
                    <p className="text-sm text-gray-600">
                      Sent {new Date(invitation.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <button
                    onClick={() => handleRevokeInvitation(invitation.id)}
                    className="flex flex-shrink-0 items-center gap-1 self-start rounded px-3 py-1 text-sm text-red-600 hover:bg-red-50 sm:self-auto"
                  >
                    <X className="h-4 w-4" />
                    Revoke
                  </button>
                </div>
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

