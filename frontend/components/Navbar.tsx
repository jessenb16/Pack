'use client';

import Link from 'next/link';
import { useUser, SignOutButton } from '@clerk/nextjs';
import { Home, Archive, MessageCircle, Upload, Settings } from 'lucide-react';

export default function Navbar() {
  const { user, isLoaded } = useUser();

  if (!isLoaded) {
    return null;
  }

  return (
    <nav className="border-b bg-white shadow-sm">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4">
        <Link href="/dashboard" className="text-2xl font-bold text-red-900">
          Pack
        </Link>
        
        <div className="flex items-center gap-6">
          <Link 
            href="/dashboard" 
            className="flex items-center gap-2 text-gray-700 hover:text-red-900 transition-colors"
          >
            <Home className="h-5 w-5" />
            <span>Dashboard</span>
          </Link>
          <Link 
            href="/vault" 
            className="flex items-center gap-2 text-gray-700 hover:text-red-900 transition-colors"
          >
            <Archive className="h-5 w-5" />
            <span>Vault</span>
          </Link>
          <Link 
            href="/chat" 
            className="flex items-center gap-2 text-gray-700 hover:text-red-900 transition-colors"
          >
            <MessageCircle className="h-5 w-5" />
            <span>Ask Pack</span>
          </Link>
          <Link 
            href="/upload" 
            className="flex items-center gap-2 text-gray-700 hover:text-red-900 transition-colors"
          >
            <Upload className="h-5 w-5" />
            <span>Upload</span>
          </Link>
          <Link 
            href="/family-settings" 
            className="flex items-center gap-2 text-gray-700 hover:text-red-900 transition-colors"
          >
            <Settings className="h-5 w-5" />
            <span>Settings</span>
          </Link>
          
          {user && (
            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-600">
                {user.firstName || user.emailAddresses[0]?.emailAddress}
              </span>
              <SignOutButton>
                <button className="rounded bg-red-900 px-4 py-2 text-sm text-white hover:bg-red-800 transition-colors">
                  Sign Out
                </button>
              </SignOutButton>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}

