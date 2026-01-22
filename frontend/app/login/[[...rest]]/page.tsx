import { SignIn } from '@clerk/nextjs';
import Link from 'next/link';

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-yellow-400 via-yellow-600 to-red-900">
      <div className="w-full max-w-md px-4">
        <div className="mb-8 text-center">
          <Link href="/" className="text-4xl font-bold text-white drop-shadow-lg">
            Pack
          </Link>
          <p className="mt-2 text-white/90">
            Sign in to your family archive
          </p>
        </div>
        <div className="rounded-lg bg-white p-8 shadow-xl">
          <SignIn 
            routing="path"
            path="/login"
            signUpUrl="/register"
            fallbackRedirectUrl="/dashboard"
            forceRedirectUrl="/dashboard"
          />
        </div>
        <p className="mt-4 text-center text-white/80">
          Don't have an account?{' '}
          <Link href="/register" className="font-semibold underline">
            Sign up
          </Link>
        </p>
      </div>
    </div>
  );
}

