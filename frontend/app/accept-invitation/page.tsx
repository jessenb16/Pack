'use client';

import { Suspense, useCallback, useEffect, useState } from 'react';
import { useUser, useAuth, useSignIn, useSignUp } from '@clerk/nextjs';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import Navbar from '@/components/Navbar';
import { apiClient } from '@/lib/api';
import { Loader2, CheckCircle, XCircle } from 'lucide-react';

function AcceptInvitationContent() {
  const { user, isLoaded } = useUser();
  const { getToken, orgId } = useAuth();
  const { signIn, setActive: setActiveSignIn } = useSignIn();
  const { signUp, setActive: setActiveSignUp } = useSignUp();
  const router = useRouter();
  const searchParams = useSearchParams();

  const token = searchParams.get('__clerk_ticket');
  const accountStatus = searchParams.get('__clerk_status');

  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('');
  const [signInError, setSignInError] = useState<string | null>(null);
  const [signUpState, setSignUpState] = useState({ firstName: '', lastName: '', password: '' });
  const [signUpError, setSignUpError] = useState<string | null>(null);
  const [signUpSubmitting, setSignUpSubmitting] = useState(false);

  const handleInvitationAccepted = useCallback(async () => {
    try {
      const authToken = await getToken({ organizationId: orgId || undefined });

      const response = await apiClient.getFamily(authToken);

      if (response.data) {
        setStatus('success');
        setMessage('Welcome to the family! Redirecting to dashboard...');
        setTimeout(() => {
          router.push('/dashboard');
        }, 2000);
      } else {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        const retryResponse = await apiClient.getFamily(authToken);

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
  }, [getToken, orgId, router]);

  // No invitation ticket: redirect based on auth state
  useEffect(() => {
    if (!isLoaded) return;
    if (token) return;

    if (user) {
      router.push('/dashboard');
    } else {
      router.push('/login');
    }
  }, [isLoaded, user, token, router]);

  // sign_in: use ticket to sign in existing user
  useEffect(() => {
    if (!token || accountStatus !== 'sign_in' || !signIn || !setActiveSignIn || user) return;

    const runSignIn = async () => {
      try {
        setSignInError(null);
        const signInAttempt = await signIn.create({
          strategy: 'ticket',
          ticket: token,
        });

        if (signInAttempt.status === 'complete') {
          await setActiveSignIn({ session: signInAttempt.createdSessionId });
        } else {
          setSignInError('Sign-in could not be completed. Please try again.');
        }
      } catch (err) {
        console.error('Ticket sign-in error:', err);
        setSignInError('Failed to sign in. Please try the link again or sign in manually.');
      }
    };

    runSignIn();
  }, [token, accountStatus, signIn, setActiveSignIn, user]);

  // User is signed in with invitation context: sync and redirect
  useEffect(() => {
    if (!isLoaded || !token || !user) return;

    handleInvitationAccepted();
  }, [isLoaded, token, user, handleInvitationAccepted]);

  const handleSignUpSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!signUp || !setActiveSignUp || !token) return;

    setSignUpSubmitting(true);
    setSignUpError(null);

    try {
      const signUpAttempt = await signUp.create({
        strategy: 'ticket',
        ticket: token,
        firstName: signUpState.firstName.trim(),
        lastName: signUpState.lastName.trim() || undefined,
        password: signUpState.password,
      });

      if (signUpAttempt.status === 'complete') {
        await setActiveSignUp({ session: signUpAttempt.createdSessionId });
      } else {
        setSignUpError('Sign-up could not be completed. Please try again.');
      }
    } catch (err) {
      console.error('Ticket sign-up error:', err);
      setSignUpError(
        err instanceof Error ? err.message : 'Failed to create account. Please try again.'
      );
    } finally {
      setSignUpSubmitting(false);
    }
  };

  // sign_up: show form for new users (until they've signed up and we have user)
  if (token && accountStatus === 'sign_up' && !user) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <main className="container mx-auto flex min-h-[60vh] items-center justify-center px-4">
          <div className="w-full max-w-md rounded-lg bg-white p-8 shadow-lg">
            <h1 className="mb-2 text-2xl font-bold text-gray-900">Join the Family</h1>
            <p className="mb-6 text-gray-600">
              Create your account to accept this invitation.
            </p>
            <form onSubmit={handleSignUpSubmit} className="space-y-4">
              <div id="clerk-captcha" />
              <div>
                <label
                  htmlFor="firstName"
                  className="mb-1 block text-sm font-medium text-gray-700"
                >
                  First name
                </label>
                <input
                  id="firstName"
                  type="text"
                  value={signUpState.firstName}
                  onChange={(e) =>
                    setSignUpState((s) => ({ ...s, firstName: e.target.value }))
                  }
                  required
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:border-red-500 focus:outline-none focus:ring-1 focus:ring-red-500"
                />
              </div>
              <div>
                <label
                  htmlFor="lastName"
                  className="mb-1 block text-sm font-medium text-gray-700"
                >
                  Last name <span className="text-gray-400">(optional)</span>
                </label>
                <input
                  id="lastName"
                  type="text"
                  value={signUpState.lastName}
                  onChange={(e) =>
                    setSignUpState((s) => ({ ...s, lastName: e.target.value }))
                  }
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:border-red-500 focus:outline-none focus:ring-1 focus:ring-red-500"
                />
              </div>
              <div>
                <label
                  htmlFor="password"
                  className="mb-1 block text-sm font-medium text-gray-700"
                >
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  value={signUpState.password}
                  onChange={(e) =>
                    setSignUpState((s) => ({ ...s, password: e.target.value }))
                  }
                  required
                  minLength={8}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:border-red-500 focus:outline-none focus:ring-1 focus:ring-red-500"
                />
              </div>
              {signUpError && (
                <p className="text-sm text-red-600">{signUpError}</p>
              )}
              <button
                type="submit"
                disabled={signUpSubmitting}
                className="w-full rounded-lg bg-red-900 px-4 py-2 font-semibold text-white transition-colors hover:bg-red-800 disabled:opacity-50"
              >
                {signUpSubmitting ? 'Creating account...' : 'Create account'}
              </button>
            </form>
            <p className="mt-4 text-center text-sm text-gray-600">
              Already have an account?{' '}
              <Link href="/login" className="font-semibold text-red-900 underline">
                Sign in
              </Link>
            </p>
          </div>
        </main>
      </div>
    );
  }

  // sign_in: show loading or error while ticket sign-in runs
  if (token && accountStatus === 'sign_in' && !user) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <main className="container mx-auto flex min-h-[60vh] items-center justify-center px-4">
          <div className="w-full max-w-md rounded-lg bg-white p-8 shadow-lg text-center">
            {signInError ? (
              <>
                <XCircle className="mx-auto h-16 w-16 text-red-500" />
                <h1 className="mt-4 text-2xl font-bold text-gray-900">Sign in failed</h1>
                <p className="mt-2 text-gray-600">{signInError}</p>
                <Link
                  href="/login"
                  className="mt-6 inline-block rounded-lg bg-red-900 px-6 py-2 font-semibold text-white transition-colors hover:bg-red-800"
                >
                  Sign in manually
                </Link>
              </>
            ) : (
              <>
                <Loader2 className="mx-auto h-12 w-12 animate-spin text-red-900" />
                <p className="mt-4 text-gray-600">Signing you in...</p>
              </>
            )}
          </div>
        </main>
      </div>
    );
  }

  // Loading (no token yet, or processing)
  if (!isLoaded || (!user && accountStatus !== 'sign_up')) {
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

  // Success, error, or still syncing
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
          ) : status === 'error' ? (
            <>
              <XCircle className="mx-auto h-16 w-16 text-red-500" />
              <h1 className="mt-4 text-2xl font-bold text-gray-900">Error</h1>
              <p className="mt-2 text-gray-600">{message}</p>
              <Link
                href="/login"
                className="mt-6 inline-block rounded-lg bg-red-900 px-6 py-2 font-semibold text-white transition-colors hover:bg-red-800"
              >
                Go to Login
              </Link>
            </>
          ) : (
            <>
              <Loader2 className="mx-auto h-12 w-12 animate-spin text-red-900" />
              <p className="mt-4 text-gray-600">Processing your invitation...</p>
            </>
          )}
        </div>
      </main>
    </div>
  );
}

export default function AcceptInvitationPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-gray-50">
          <Navbar />
          <main className="container mx-auto flex min-h-[60vh] items-center justify-center px-4">
            <Loader2 className="h-12 w-12 animate-spin text-red-900" />
          </main>
        </div>
      }
    >
      <AcceptInvitationContent />
    </Suspense>
  );
}
