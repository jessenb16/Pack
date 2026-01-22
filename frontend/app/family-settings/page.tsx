'use client';

import { useEffect, useState } from 'react';
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
  const { getToken } = useAuth();
  const router = useRouter();
  const [family, setFamily] = useState<any>(null);
  const [members, setMembers] = useState<any[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [loading, setLoading] = useState(true);
  const [inviteEmail, setInviteEmail] = useState('');
  const [sending, setSending] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    if (!isLoaded) return;
    
    if (!user) {
      router.push('/login');
      return;
    }

    loadFamilyData();
  }, [user, isLoaded]);

  async function loadFamilyData() {
    try {
      setLoading(true);
      const token = await getToken();
      
      // Load family info
      const familyResponse = await apiClient.getFamily(token);
      if (familyResponse.data) {
        setFamily(familyResponse.data);
      } else if (familyResponse.error) {
        setMessage({ type: 'error', text: familyResponse.error });
        setLoading(false);
        return;
      }
      
      // Load members
      const membersResponse = await apiClient.getFamilyMembers(token);
      if (membersResponse.data) {
        setMembers(membersResponse.data);
      }
      
      // Load invitations
      const invitationsResponse = await apiClient.getInvitations(token);
      if (invitationsResponse.data) {
        setInvitations(invitationsResponse.data);
      } else if (invitationsResponse.error) {
        // Invitations might fail if user doesn't have permission, but that's okay
        console.warn('Could not load invitations:', invitationsResponse.error);
      }
    } catch (error) {
      console.error('Error loading family data:', error);
      setMessage({ type: 'error', text: 'Failed to load family data. Please try again.' });
    } finally {
      setLoading(false);
    }
  }

  async function handleSendInvitation(e: React.FormEvent) {
    e.preventDefault();
    if (!inviteEmail.trim()) return;

    setSending(true);
    setMessage(null);

    try {
      const token = await getToken();
      const response = await apiClient.sendInvitation(inviteEmail.trim(), token);
      
      if (response.data) {
        setMessage({ type: 'success', text: `Invitation sent to ${inviteEmail}!` });
        setInviteEmail('');
        // Reload invitations
        const invitationsResponse = await apiClient.getInvitations(token);
        if (invitationsResponse.data) {
          setInvitations(invitationsResponse.data);
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
      const token = await getToken();
      const response = await apiClient.revokeInvitation(invitationId, token);
      
      if (response.data) {
        setMessage({ type: 'success', text: 'Invitation revoked' });
        // Reload invitations
        const invitationsResponse = await apiClient.getInvitations(token);
        if (invitationsResponse.data) {
          setInvitations(invitationsResponse.data);
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
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      
      <main className="container mx-auto max-w-4xl px-4 py-8">
        <h1 className="mb-8 text-3xl font-bold text-gray-900">Family Settings</h1>

        {/* Family Info */}
        <section className="mb-8 rounded-lg bg-white p-6 shadow">
          <h2 className="mb-4 text-xl font-semibold text-gray-800">Family Information</h2>
          <div className="space-y-2">
            <p className="text-gray-600">
              <span className="font-medium">Family Name:</span> {family.name}
            </p>
            <p className="text-gray-600">
              <span className="font-medium">Created:</span>{' '}
              {new Date(family.created_at).toLocaleDateString()}
            </p>
          </div>
        </section>

        {/* Family Members */}
        <section className="mb-8 rounded-lg bg-white p-6 shadow">
          <div className="mb-4 flex items-center gap-2">
            <Users className="h-5 w-5 text-red-900" />
            <h2 className="text-xl font-semibold text-gray-800">Family Members</h2>
          </div>
          {members.length === 0 ? (
            <p className="text-gray-600">No members yet.</p>
          ) : (
            <div className="space-y-2">
              {members.map((member) => (
                <div key={member.id} className="flex items-center justify-between rounded border p-3">
                  <div>
                    <p className="font-medium text-gray-900">{member.name}</p>
                    <p className="text-sm text-gray-600">{member.email}</p>
                  </div>
                  <span className="rounded-full bg-gray-100 px-3 py-1 text-sm text-gray-700">
                    {member.role}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Send Invitation */}
        <section className="mb-8 rounded-lg bg-white p-6 shadow">
          <div className="mb-4 flex items-center gap-2">
            <Mail className="h-5 w-5 text-red-900" />
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
                disabled={sending}
              />
              <p className="mt-1 text-sm text-gray-500">
                The invitee will receive an email with a link to join. They'll create their account when they accept the invitation.
              </p>
            </div>
            <button
              type="submit"
              disabled={sending || !inviteEmail.trim()}
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
                  className="flex items-center justify-between rounded border p-3"
                >
                  <div>
                    <p className="font-medium text-gray-900">{invitation.email}</p>
                    <p className="text-sm text-gray-600">
                      Sent {new Date(invitation.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <button
                    onClick={() => handleRevokeInvitation(invitation.id)}
                    className="flex items-center gap-1 rounded px-3 py-1 text-sm text-red-600 hover:bg-red-50"
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

