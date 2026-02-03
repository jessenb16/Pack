'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useUser, SignOutButton } from '@clerk/nextjs';
import { Home, Archive, MessageCircle, Upload, Settings, Menu, X } from 'lucide-react';

const navLinks = [
  { href: '/dashboard', icon: Home, label: 'Dashboard', hoverClass: 'hover:text-purple-600' },
  { href: '/vault', icon: Archive, label: 'Vault', hoverClass: 'hover:text-cyan-600' },
  { href: '/chat', icon: MessageCircle, label: 'Ask Pack', hoverClass: 'hover:text-purple-600' },
  { href: '/upload', icon: Upload, label: 'Upload', hoverClass: 'hover:text-cyan-600' },
  { href: '/family-settings', icon: Settings, label: 'Settings', hoverClass: 'hover:text-purple-600' },
];

export default function Navbar() {
  const { user, isLoaded } = useUser();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  if (!isLoaded) {
    return null;
  }

  return (
    <nav className="border-b bg-gradient-to-r from-purple-50 via-white to-cyan-50 shadow-md backdrop-blur-sm">
      <div className="mx-auto max-w-7xl px-4 py-4">
        <div className="flex items-center justify-between">
          <Link href="/dashboard" className="text-2xl font-bold text-red-900 drop-shadow-sm">
            Pack
          </Link>

          {/* Desktop nav - hidden on mobile */}
          <div className="hidden items-center gap-6 md:flex">
            {navLinks.map(({ href, icon: Icon, label, hoverClass }) => (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-2 text-gray-700 transition-colors ${hoverClass}`}
              >
                <Icon className="h-5 w-5" />
                <span>{label}</span>
              </Link>
            ))}
            {user && (
              <div className="flex items-center gap-4">
                <span className="text-sm text-gray-600">
                  {user.firstName || user.emailAddresses[0]?.emailAddress}
                </span>
                <SignOutButton>
                  <button className="rounded-lg bg-gradient-to-r from-purple-600 to-cyan-600 px-4 py-2 text-sm text-white transition-all shadow-sm hover:from-purple-700 hover:to-cyan-700">
                    Sign Out
                  </button>
                </SignOutButton>
              </div>
            )}
          </div>

          {/* Mobile menu button */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="rounded-lg p-2 text-gray-700 hover:bg-gray-100 md:hidden"
            aria-expanded={mobileMenuOpen}
            aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
          >
            {mobileMenuOpen ? (
              <X className="h-6 w-6" />
            ) : (
              <Menu className="h-6 w-6" />
            )}
          </button>
        </div>

        {/* Mobile dropdown menu */}
        {mobileMenuOpen && (
          <div className="mt-4 flex flex-col gap-2 border-t border-gray-200 pt-4 md:hidden">
            {navLinks.map(({ href, icon: Icon, label, hoverClass }) => (
              <Link
                key={href}
                href={href}
                onClick={() => setMobileMenuOpen(false)}
                className={`flex items-center gap-2 rounded-lg px-3 py-2 text-gray-700 transition-colors ${hoverClass} hover:bg-gray-50`}
              >
                <Icon className="h-5 w-5" />
                <span>{label}</span>
              </Link>
            ))}
            {user && (
              <div className="mt-2 flex flex-col gap-2 border-t border-gray-200 pt-4">
                <span className="px-3 py-1 text-sm text-gray-600">
                  {user.firstName || user.emailAddresses[0]?.emailAddress}
                </span>
                <SignOutButton>
                  <button
                    onClick={() => setMobileMenuOpen(false)}
                    className="flex w-full justify-center rounded-lg bg-gradient-to-r from-purple-600 to-cyan-600 px-4 py-2 text-sm text-white shadow-sm hover:from-purple-700 hover:to-cyan-700"
                  >
                    Sign Out
                  </button>
                </SignOutButton>
              </div>
            )}
          </div>
        )}
      </div>
    </nav>
  );
}
