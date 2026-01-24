'use client';

import { useEffect, useState } from 'react';
import { useUser, useAuth, useOrganizationList } from '@clerk/nextjs';
import { useRouter } from 'next/navigation';
import { CreateOrganization } from '@clerk/nextjs';
import Navbar from '@/components/Navbar';
import { apiClient } from '@/lib/api';
import { Loader2 } from 'lucide-react';

export default function FamilySetupPage() {
  const { user, isLoaded } = useUser();
  const { getToken } = useAuth();
  const { organizationList, isLoaded: orgListLoaded } = useOrganizationList();
  const router = useRouter();
  const [checking, setChecking] = useState(true);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    if (!isLoaded || !orgListLoaded) return;
    
    if (!user) {
      router.push('/login');
      return;
    }

    // If user already has an organization, redirect to dashboard
    if (organizationList && organizationList.length > 0) {
      router.push('/dashboard');
      return;
    }

    // User doesn't have an organization, show the create form
    setChecking(false);
  }, [user, isLoaded, orgListLoaded, organizationList, router]);


  if (!isLoaded || !orgListLoaded || checking) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-lg">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      
      <main className="mx-auto max-w-2xl px-4 py-16">
        <div className="rounded-lg bg-white p-8 shadow">
          <h1 className="mb-4 text-3xl font-bold text-gray-900">Set Up Your Family</h1>
          <p className="mb-8 text-gray-600">
            Create a family organization to start organizing your memories. After creating your family, you'll be able to:
          </p>
          
          <ul className="mb-8 list-disc space-y-2 pl-6 text-gray-600">
            <li>Upload cards, letters, and photos</li>
            <li>Invite other family members to join</li>
            <li>Organize memories by person, event, and date</li>
            <li>Ask Pack AI questions about your family history</li>
          </ul>

          {/* Use Clerk's CreateOrganization component */}
          <div className="flex justify-center">
            <CreateOrganization 
              routing="path"
              path="/family-setup"
              afterCreateOrganizationUrl="/dashboard"
              skipInvitationScreen={true}
              appearance={{
                elements: {
                  rootBox: "mx-auto",
                  card: "shadow-none",
                  headerTitle: "text-2xl font-bold text-gray-900",
                  headerSubtitle: "text-gray-600",
                  formButtonPrimary: "bg-red-900 hover:bg-red-800",
                }
              }}
            />
          </div>
        </div>
      </main>
    </div>
  );
}

