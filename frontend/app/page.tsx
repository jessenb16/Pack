import Link from "next/link";
import { currentUser } from '@clerk/nextjs/server';
import { redirect } from 'next/navigation';
import { Upload, Tag, Calendar, Users, MessageCircle, ShieldCheck, ChevronDown, ChevronUp, Layers } from 'lucide-react';

export default async function Home() {
  const user = await currentUser();
  
  if (user) {
    redirect('/dashboard');
  }

  return (
    <div className="bg-gradient-to-r from-yellow-400 via-yellow-600 to-red-900">
      {/* Hero - sleek, centered, original style */}
      <div id="top" className="flex min-h-screen flex-col items-center justify-center px-6 text-center">
        <h1 className="text-5xl font-bold text-white drop-shadow-lg">
          Pack
        </h1>
        <p className="mt-4 max-w-md text-xl text-white/90">
          Your family&apos;s digital memory archive. Preserve letters, handwritten cards, and photos—then find anything with AI.
        </p>
        <div className="mt-6 flex gap-4">
          <Link
            href="/login"
            className="rounded-lg bg-white px-6 py-3 font-semibold text-red-900 transition-colors hover:bg-gray-100"
          >
            Sign In
          </Link>
          <Link
            href="/register"
            className="rounded-lg border-2 border-white bg-red-900 px-6 py-3 font-semibold text-white transition-colors hover:bg-red-800"
          >
            Sign Up
          </Link>
        </div>
        <div className="mt-10 flex flex-col items-center gap-4">
          <p className="max-w-xs text-sm leading-relaxed text-white/85">
            Sign up to start a family, or use the link from your invitation email to join.
          </p>
          <a
            href="#learn-more"
            className="inline-flex items-center gap-1.5 rounded-full border border-white/40 bg-white/10 px-5 py-2.5 text-sm font-medium text-white backdrop-blur-sm transition-all hover:border-white/60 hover:bg-white/20"
          >
            Learn more
            <ChevronDown className="h-4 w-4" aria-hidden />
          </a>
        </div>
      </div>

      {/* Learn more - scroll target */}
      <section
        id="learn-more"
        className="flex min-h-[75vh] flex-col items-center justify-center px-6 py-20 scroll-mt-8"
      >
        <div className="mx-auto w-full max-w-2xl space-y-6">
          {/* What Pack Does */}
          <div className="rounded-xl bg-white/95 p-6 text-left shadow-lg backdrop-blur-sm">
            <h2 className="mb-4 text-xl font-semibold text-gray-900">What Pack Does</h2>
            <ul className="space-y-3 text-base text-gray-700 leading-relaxed">
              <li className="flex gap-3">
                <Upload className="h-5 w-5 shrink-0 mt-0.5 text-red-700" />
                <span><span className="font-medium text-gray-900">Store family memories</span> — letters, handwritten cards, photos. Upload files or paste text.</span>
              </li>
              <li className="flex gap-3">
                <Tag className="h-5 w-5 shrink-0 mt-0.5 text-red-700" />
                <span><span className="font-medium text-gray-900">Tag and organize</span> — add sender, event, date, and recipient so you can find anything later.</span>
              </li>
              <li className="flex gap-3">
                <Calendar className="h-5 w-5 shrink-0 mt-0.5 text-red-700" />
                <span><span className="font-medium text-gray-900">Browse the vault</span> — filter your documents by sender, event type, and year.</span>
              </li>
              <li className="flex gap-3">
                <MessageCircle className="h-5 w-5 shrink-0 mt-0.5 text-red-700" />
                <span><span className="font-medium text-gray-900">Ask Pack AI</span> — find specific documents (&quot;letters from Grandma&quot;) or ask questions about your family history. Pack searches the content of your documents to answer.</span>
              </li>
              <li className="flex gap-3">
                <Users className="h-5 w-5 shrink-0 mt-0.5 text-red-700" />
                <span><span className="font-medium text-gray-900">Family sharing</span> — invite members to your family. Everyone can upload, browse, and ask Pack together.</span>
              </li>
              <li className="flex gap-3">
                <Layers className="h-5 w-5 shrink-0 mt-0.5 text-red-700" />
                <span><span className="font-medium text-gray-900">Multiple Packs</span> — be part of more than one family archive and switch between them seamlessly.</span>
              </li>
            </ul>
            <div className="mt-4 rounded-lg border border-gray-100 bg-gray-50 p-4 text-gray-700">
              <p className="mb-2 text-sm font-medium text-gray-900">Example questions for Pack AI:</p>
              <div className="space-y-1 text-sm italic text-gray-600">
                <p>&quot;Show me letters from Grandma&quot;</p>
                <p>&quot;What did we do for Christmas 1985?&quot;</p>
              </div>
            </div>
          </div>

          {/* Privacy */}
          <div className="rounded-xl border-2 border-red-100 bg-white/95 p-6 text-left shadow-lg backdrop-blur-sm">
            <div className="flex items-start gap-3">
              <ShieldCheck className="h-6 w-6 shrink-0 text-green-600 mt-0.5" />
              <div>
                <h2 className="text-xl font-semibold text-gray-900">Your memories stay private</h2>
                <p className="mt-2 text-base text-gray-700 leading-relaxed">
                  Pack is built for families, not the public. Your documents and conversations are only visible to you and the family members you invite. We don&apos;t sell your data or use it for advertising.
                </p>
              </div>
            </div>
          </div>
        </div>
        <a
          href="#top"
          className="mt-12 inline-flex items-center gap-1.5 rounded-full border border-white/40 bg-white/10 px-5 py-2.5 text-sm font-medium text-white backdrop-blur-sm transition-all hover:border-white/60 hover:bg-white/20"
        >
          Back to top
          <ChevronUp className="h-4 w-4" aria-hidden />
        </a>
      </section>
    </div>
  );
}
