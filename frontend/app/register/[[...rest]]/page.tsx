import { SignUp } from '@clerk/nextjs';
import Link from 'next/link';

export default function RegisterPage() {
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
        <div className="rounded-lg bg-white p-8 shadow-xl">
          <SignUp 
            routing="path"
            path="/register"
            signInUrl="/login"
            fallbackRedirectUrl="/dashboard"
            forceRedirectUrl="/dashboard"
            appearance={{
              elements: {
                formButtonPrimary: "bg-red-900 hover:bg-red-800",
                card: "shadow-none",
              }
            }}
            // Ensure first name and last name fields are shown
            additionalOAuthScopes={{
              google: "profile email",
            }}
          />
        </div>
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

