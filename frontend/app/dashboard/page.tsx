'use client';

import { useEffect, useState } from 'react';
import { useUser, useAuth } from '@clerk/nextjs';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import Navbar from '@/components/Navbar';
import { apiClient } from '@/lib/api';
import { Calendar, Image as ImageIcon, Loader2, Mail, Users, ArrowRight } from 'lucide-react';

export default function DashboardPage() {
  const { user, isLoaded } = useUser();
  const { getToken } = useAuth();
  const router = useRouter();
  const [recentDocs, setRecentDocs] = useState<any[]>([]);
  const [onThisDay, setOnThisDay] = useState<any[]>([]);
  const [family, setFamily] = useState<any>(null);
  const [members, setMembers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isLoaded) return;
    
    if (!user) {
      router.push('/login');
      return;
    }

    loadDashboard();
  }, [user, isLoaded]);

  async function loadDashboard() {
    try {
      const token = await getToken();
      
      // Load family info
      const familyResponse = await apiClient.getFamily(token);
      if (familyResponse.data) {
        setFamily(familyResponse.data);
        
        // Load members
        const membersResponse = await apiClient.getFamilyMembers(token);
        if (membersResponse.data) {
          setMembers(membersResponse.data);
        }
      }
      
      // Load documents
      const response = await apiClient.getDocuments(undefined, token);
      
      if (response.data) {
        setRecentDocs(response.data.slice(0, 20));
        
        // Get "On This Day" documents
        const today = new Date();
        const todayStr = `${today.getMonth() + 1}-${today.getDate()}`;
        const onThisDayDocs = response.data.filter((doc: any) => {
          const docDate = doc.metadata?.doc_date;
          if (!docDate) return false;
          const date = new Date(docDate);
          const dateStr = `${date.getMonth() + 1}-${date.getDate()}`;
          return dateStr === todayStr;
        });
        setOnThisDay(onThisDayDocs);
      }
    } catch (error) {
      console.error('Error loading dashboard:', error);
    } finally {
      setLoading(false);
    }
  }

  if (!isLoaded || loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-red-900" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      
      <main className="mx-auto max-w-7xl px-4 py-8">
        <h1 className="mb-8 text-3xl font-bold text-gray-900">Dashboard</h1>
        
        {/* Invite Family Members - Prominent Section */}
        {family && (
          <section className="mb-8 rounded-lg border-2 border-red-900 bg-gradient-to-r from-red-50 to-yellow-50 p-6 shadow-lg">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="rounded-full bg-red-900 p-3">
                  <Mail className="h-6 w-6 text-white" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-gray-900">Invite Family Members</h2>
                  <p className="text-gray-600">
                    {members.length === 1 
                      ? "You're the only member. Invite others to start sharing memories!"
                      : `${members.length} family member${members.length > 1 ? 's' : ''} in ${family.name}`
                    }
                  </p>
                </div>
              </div>
              <Link
                href="/family-settings"
                className="flex items-center gap-2 rounded-lg bg-red-900 px-6 py-3 text-white transition-colors hover:bg-red-800"
              >
                <span>Invite Now</span>
                <ArrowRight className="h-5 w-5" />
              </Link>
            </div>
          </section>
        )}
        
        {/* Recent Uploads */}
        <section className="mb-12">
          <h2 className="mb-4 text-2xl font-semibold text-gray-800">Recent Uploads</h2>
          {recentDocs.length === 0 ? (
            <p className="text-gray-600">No documents yet. Upload your first memory!</p>
          ) : (
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-6">
              {recentDocs.map((doc) => (
                <div
                  key={doc.id}
                  className="group cursor-pointer overflow-hidden rounded-lg bg-white shadow transition-shadow hover:shadow-lg"
                >
                  <img
                    src={doc.s3_thumbnail_url}
                    alt={doc.metadata?.sender_name || 'Document'}
                    className="h-48 w-full object-cover"
                  />
                  <div className="p-3">
                    <p className="text-sm font-medium text-gray-900">
                      {doc.metadata?.sender_name}
                    </p>
                    <p className="text-xs text-gray-500">{doc.metadata?.event_type}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* On This Day */}
        {onThisDay.length > 0 && (
          <section>
            <div className="mb-4 flex items-center gap-2">
              <Calendar className="h-6 w-6 text-red-900" />
              <h2 className="text-2xl font-semibold text-gray-800">On This Day</h2>
            </div>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-6">
              {onThisDay.map((doc) => (
                <div
                  key={doc.id}
                  className="group cursor-pointer overflow-hidden rounded-lg bg-white shadow transition-shadow hover:shadow-lg"
                >
                  <img
                    src={doc.s3_thumbnail_url}
                    alt={doc.metadata?.sender_name || 'Document'}
                    className="h-48 w-full object-cover"
                  />
                  <div className="p-3">
                    <p className="text-sm font-medium text-gray-900">
                      {doc.metadata?.sender_name}
                    </p>
                    <p className="text-xs text-gray-500">{doc.metadata?.event_type}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

