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

    checkFamily();
  }, [user, isLoaded, orgListLoaded, organizationList]);

  async function checkFamily() {
    try {
      // With "Membership required", Clerk will force org creation during signup
      // So if user reaches here, they should already have an organization
      if (organizationList && organizationList.length > 0) {
        // User has a Clerk organization, sync it to MongoDB
        await syncOrganizationToMongoDB();
        return;
      }
      
      // Check if family already exists in MongoDB (might be synced already)
      const token = await getToken();
      const response = await apiClient.getFamily(token);
      
      if (response.data) {
        // User already has a family, redirect to dashboard
        router.push('/dashboard');
        return;
      }
      
      // If we're here and user has no organization, they might have:
      // 1. Signed up before "Membership required" was enabled
      // 2. Or there's an issue - redirect to dashboard and let backend handle it
      // The backend will sync on first API call, so just redirect
      router.push('/dashboard');
    } catch (error) {
      console.error('Error checking family:', error);
      // On error, redirect to dashboard - backend will handle sync
      router.push('/dashboard');
    }
  }

  async function syncOrganizationToMongoDB() {
    if (!organizationList || organizationList.length === 0) {
      setChecking(false);
      return;
    }
    
    setSyncing(true);
    try {
      // Make an API call to trigger automatic sync in get_current_user
      // The backend will detect the organization and sync it to MongoDB
      const token = await getToken();
      
      // Try multiple times with delays to allow sync to complete
      for (let i = 0; i < 3; i++) {
        await new Promise(resolve => setTimeout(resolve, 1000));
        const response = await apiClient.getFamily(token);
        
        if (response.data) {
          // Family synced successfully, redirect to dashboard
          router.push('/dashboard');
          return;
        }
      }
      
      // If still not synced after retries, show error or allow manual retry
      console.warn('Organization not synced after retries');
      setChecking(false);
    } catch (error) {
      console.error('Error syncing organization:', error);
      setChecking(false);
    } finally {
      setSyncing(false);
    }
  }

  // Handle organization creation completion
  const handleOrganizationCreated = async () => {
    // Wait a moment for Clerk to process, then check for family
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    const token = await getToken();
    const response = await apiClient.getFamily(token);
    
    if (response.data) {
      router.push('/dashboard');
    } else {
      // Organization created but not synced yet, wait a bit more
      await new Promise(resolve => setTimeout(resolve, 2000));
      const retryResponse = await apiClient.getFamily(token);
      if (retryResponse.data) {
        router.push('/dashboard');
      }
    }
  };

  if (!isLoaded || checking || syncing) {
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

