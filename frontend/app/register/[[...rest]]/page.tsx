'use client';

import { SignUp } from '@clerk/nextjs';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect } from 'react';

function RegisterContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const ticket = searchParams.get('__clerk_ticket');
  const accountStatus = searchParams.get('__clerk_status');
  const hasInvitationParams = !!ticket && !!accountStatus;

  // If user arrived with invitation params (from an old invite link pointing to /register),
  // redirect to /accept-invitation which handles both new and existing users correctly.
  // Don't render SignUp here - it shows an error for existing users.
  useEffect(() => {
    if (hasInvitationParams) {
      const params = new URLSearchParams(searchParams.toString());
      router.replace(`/accept-invitation?${params.toString()}`);
    }
  }, [hasInvitationParams, searchParams, router]);

  if (hasInvitationParams) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-yellow-400 via-yellow-600 to-red-900">
        <p className="text-white">Redirecting to accept invitation...</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-yellow-400 via-yellow-600 to-red-900">
      <div className="w-full max-w-md px-4">
        <div className="mb-8 text-center">
          <Link href="/" className="text-4xl font-bold text-white drop-shadow-lg">
            Pack
          </Link>
          <p className="mt-2 text-white/90">
            Create your family archive account
          </p>
          <p className="mt-1 text-sm text-white/80">
            Please enter your first and last name so family members can identify you
          </p>
        </div>
        <SignUp
          routing="path"
          path="/register"
          signInUrl="/login"
          fallbackRedirectUrl="/dashboard"
          forceRedirectUrl="/dashboard"
          appearance={{
            elements: {
              formButtonPrimary: 'bg-red-900 hover:bg-red-800',
              card: 'shadow-xl',
            },
          }}
        />
        <p className="mt-4 text-center text-white/80">
          Already have an account?{' '}
          <Link href="/login" className="font-semibold underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function RegisterPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-yellow-400 via-yellow-600 to-red-900">
          <p className="text-white">Loading...</p>
        </div>
      }
    >
      <RegisterContent />
    </Suspense>
  );
}
