'use client';

import { useEffect, useState } from 'react';
import { useUser, useAuth } from '@clerk/nextjs';
import { useRouter, useSearchParams } from 'next/navigation';
import Navbar from '@/components/Navbar';
import { apiClient } from '@/lib/api';
import { Loader2, CheckCircle, XCircle } from 'lucide-react';

export default function AcceptInvitationPage() {
  const { user, isLoaded } = useUser();
  const { getToken } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!isLoaded) return;

    // Clerk handles invitation acceptance, so if user is here and authenticated,
    // they've already accepted the invitation
    // We just need to sync them to MongoDB and redirect
    if (user) {
      handleInvitationAccepted();
    } else {
      // User not authenticated - redirect to login
      router.push('/login');
    }
  }, [user, isLoaded]);

  async function handleInvitationAccepted() {
    try {
      const token = await getToken();
      
      // Make an API call to trigger sync in get_current_user
      // This will automatically sync the user and their organization to MongoDB
      const response = await apiClient.getFamily(token);
      
      if (response.data) {
        // Successfully synced - redirect to dashboard
        setStatus('success');
        setMessage('Welcome to the family! Redirecting to dashboard...');
        setTimeout(() => {
          router.push('/dashboard');
        }, 2000);
      } else {
        // Might need to wait a moment for sync
        await new Promise(resolve => setTimeout(resolve, 2000));
        const retryResponse = await apiClient.getFamily(token);
        
        if (retryResponse.data) {
          setStatus('success');
          setMessage('Welcome to the family! Redirecting to dashboard...');
          setTimeout(() => {
            router.push('/dashboard');
          }, 2000);
        } else {
          setStatus('error');
          setMessage('Failed to sync your account. Please try logging in again.');
        }
      }
    } catch (error) {
      console.error('Error handling invitation:', error);
      setStatus('error');
      setMessage('An error occurred. Please try logging in again.');
    }
  }

  if (!isLoaded || status === 'loading') {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <main className="container mx-auto flex min-h-[60vh] items-center justify-center px-4">
          <div className="text-center">
            <Loader2 className="mx-auto h-12 w-12 animate-spin text-red-900" />
            <p className="mt-4 text-gray-600">Processing your invitation...</p>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <main className="container mx-auto flex min-h-[60vh] items-center justify-center px-4">
        <div className="w-full max-w-md rounded-lg bg-white p-8 shadow-lg text-center">
          {status === 'success' ? (
            <>
              <CheckCircle className="mx-auto h-16 w-16 text-green-500" />
              <h1 className="mt-4 text-2xl font-bold text-gray-900">Welcome to the Family!</h1>
              <p className="mt-2 text-gray-600">{message}</p>
            </>
          ) : (
            <>
              <XCircle className="mx-auto h-16 w-16 text-red-500" />
              <h1 className="mt-4 text-2xl font-bold text-gray-900">Error</h1>
              <p className="mt-2 text-gray-600">{message}</p>
              <button
                onClick={() => router.push('/login')}
                className="mt-6 rounded-lg bg-red-900 px-6 py-2 text-white transition-colors hover:bg-red-800"
              >
                Go to Login
              </button>
            </>
          )}
        </div>
      </main>
    </div>
  );
}

