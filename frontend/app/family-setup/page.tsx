'use client';

import { useEffect } from 'react';
import { useUser, useOrganizationList } from '@clerk/nextjs';
import { useRouter } from 'next/navigation';
import { CreateOrganization } from '@clerk/nextjs';
import Navbar from '@/components/Navbar';

export default function FamilySetupPage() {
  const { user, isLoaded } = useUser();
  const { userMemberships, isLoaded: orgListLoaded } = useOrganizationList({
    userMemberships: true,
  });
  const router = useRouter();

  const memberships = userMemberships?.data ?? [];
  const stillLoading = !isLoaded || !orgListLoaded || userMemberships?.isLoading;
  const shouldShowForm = !stillLoading && !!user && memberships.length === 0;

  useEffect(() => {
    if (stillLoading) return;
    if (!user) {
      router.push('/login');
      return;
    }
    if (memberships.length > 0) {
      router.push('/dashboard');
      return;
    }
  }, [stillLoading, user, memberships.length, router]);


  if (!isLoaded || !orgListLoaded || userMemberships?.isLoading || !shouldShowForm) {
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
            Create a family organization to start organizing your memories. After creating your family, you&apos;ll be able to:
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

