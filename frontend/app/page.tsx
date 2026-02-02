import Link from "next/link";
import { currentUser } from '@clerk/nextjs/server';
import { redirect } from 'next/navigation';

export default async function Home() {
  const user = await currentUser();
  
  if (user) {
    redirect('/dashboard');
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-yellow-400 via-yellow-600 to-red-900">
      <main className="flex flex-col items-center gap-8 text-center px-8">
        <h1 className="text-5xl font-bold text-white drop-shadow-lg">
          Pack
        </h1>
        <p className="text-xl text-white/90 max-w-md">
          Your family's digital memory archive. Preserve cards, letters, and photos with AI-powered search.
        </p>
        <div className="flex gap-4 mt-4">
          <Link
            href="/login"
            className="px-6 py-3 bg-white text-red-900 font-semibold rounded-lg hover:bg-gray-100 transition-colors"
          >
            Sign In
          </Link>
          <Link
            href="/register"
            className="px-6 py-3 bg-red-900 text-white font-semibold rounded-lg hover:bg-red-800 transition-colors border-2 border-white"
          >
            Sign Up
          </Link>
        </div>
      </main>
    </div>
  );
}
