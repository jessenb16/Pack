'use client';

import { useEffect, useState } from 'react';
import { useUser, useAuth } from '@clerk/nextjs';
import { useRouter } from 'next/navigation';
import Navbar from '@/components/Navbar';
import { apiClient } from '@/lib/api';
import { Upload as UploadIcon, Loader2 } from 'lucide-react';

export default function UploadPage() {
  const { user, isLoaded } = useUser();
  const { getToken } = useAuth();
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    sender_name: '',
    event_type: '',
    recipient_name: '',
    doc_date: new Date().toISOString().split('T')[0],
  });
  const [useCustomEventType, setUseCustomEventType] = useState(false);
  const [members, setMembers] = useState<Array<{id: string; name: string; role: string}>>([]);
  const [eventTypes, setEventTypes] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    if (!isLoaded) return;
    
    if (!user) {
      router.push('/login');
      return;
    }

    loadFamilyData();
  }, [user, isLoaded]);

  async function loadFamilyData() {
    try {
      const token = await getToken();
      const familyResponse = await apiClient.getFamily(token);
      
      if (familyResponse.data) {
        // Get members (would need a separate endpoint or include in family response)
        setMembers(familyResponse.data.members || []);
        setEventTypes(familyResponse.data.event_types || []);
      }
    } catch (error) {
      console.error('Error loading family data:', error);
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      
      // Create preview
      const reader = new FileReader();
      reader.onloadend = () => {
        setPreview(reader.result as string);
      };
      reader.readAsDataURL(selectedFile);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file || !formData.sender_name || !formData.event_type || !formData.doc_date) {
      alert('Please fill in all required fields and select a file');
      return;
    }

    setUploading(true);
    try {
      const token = await getToken();
      const response = await apiClient.uploadDocument(
        file, 
        {
          sender_name: formData.sender_name,
          event_type: formData.event_type,
          recipient_name: formData.recipient_name || undefined,
          doc_date: formData.doc_date
        }, 
        token
      );
      
      if (response.data) {
        alert('Document uploaded successfully!');
        router.push('/vault');
      } else {
        alert(response.error || 'Upload failed');
      }
    } catch (error) {
      console.error('Error uploading:', error);
      alert('Error uploading document');
    } finally {
      setUploading(false);
    }
  }

  if (!isLoaded) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-lg">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      
      <main className="mx-auto max-w-2xl px-4 py-8">
        <h1 className="mb-8 text-3xl font-bold text-gray-900">Upload Document</h1>
        
        <form onSubmit={handleSubmit} className="space-y-6 rounded-lg bg-white p-8 shadow">
          {/* File Upload */}
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              Select File
            </label>
            <div className="flex items-center justify-center rounded-lg border-2 border-dashed border-gray-300 p-8">
              <div className="text-center">
                <UploadIcon className="mx-auto h-12 w-12 text-gray-400" />
                <div className="mt-4">
                  <label className="cursor-pointer rounded-md bg-red-900 px-4 py-2 text-white hover:bg-red-800">
                    Choose File
                    <input
                      type="file"
                      className="hidden"
                      accept="image/*,.pdf"
                      onChange={handleFileChange}
                    />
                  </label>
                </div>
                {file && (
                  <p className="mt-2 text-sm text-gray-600">{file.name}</p>
                )}
              </div>
            </div>
            
            {preview && (
              <div className="mt-4">
                <img
                  src={preview}
                  alt="Preview"
                  className="mx-auto max-h-64 rounded-lg"
                />
              </div>
            )}
          </div>

          {/* Sender */}
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              Sender
            </label>
            <select
              value={formData.sender_name}
              onChange={(e) => setFormData({ ...formData, sender_name: e.target.value })}
              className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-red-900 focus:outline-none focus:ring-2 focus:ring-red-900"
              required
            >
              <option value="">Select sender...</option>
              {members.map((member) => (
                <option key={member.id} value={member.name}>
                  {member.name}
                </option>
              ))}
            </select>
          </div>

          {/* Event Type */}
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              Event Type <span className="text-red-600">*</span>
            </label>
            {!useCustomEventType ? (
              <>
                <select
                  value={formData.event_type}
                  onChange={(e) => setFormData({ ...formData, event_type: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-red-900 focus:outline-none focus:ring-2 focus:ring-red-900"
                  required
                >
                  <option value="">Select event type...</option>
                  {eventTypes.map((event) => (
                    <option key={event} value={event}>
                      {event}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => {
                    setUseCustomEventType(true);
                    setFormData({ ...formData, event_type: '' });
                  }}
                  className="mt-2 text-sm text-red-900 hover:underline"
                >
                  Or enter a new event type
                </button>
              </>
            ) : (
              <>
                <input
                  type="text"
                  placeholder="Enter event type..."
                  value={formData.event_type}
                  onChange={(e) => setFormData({ ...formData, event_type: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-red-900 focus:outline-none focus:ring-2 focus:ring-red-900"
                  required
                  autoFocus
                />
                <button
                  type="button"
                  onClick={() => {
                    setUseCustomEventType(false);
                    setFormData({ ...formData, event_type: '' });
                  }}
                  className="mt-2 text-sm text-red-900 hover:underline"
                >
                  Or select from existing types
                </button>
              </>
            )}
          </div>

          {/* Recipient (Optional) */}
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              Recipient <span className="text-gray-500 text-xs">(optional)</span>
            </label>
            <input
              type="text"
              placeholder="Who is this document for? (e.g., 'Mom', 'The Family')"
              value={formData.recipient_name}
              onChange={(e) => setFormData({ ...formData, recipient_name: e.target.value })}
              className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-red-900 focus:outline-none focus:ring-2 focus:ring-red-900"
            />
          </div>

          {/* Date */}
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              Date
            </label>
            <input
              type="date"
              value={formData.doc_date}
              onChange={(e) => setFormData({ ...formData, doc_date: e.target.value })}
              className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-red-900 focus:outline-none focus:ring-2 focus:ring-red-900"
              required
            />
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={uploading || !file}
            className="w-full rounded-lg bg-red-900 px-6 py-3 text-white transition-colors hover:bg-red-800 disabled:bg-gray-400"
          >
            {uploading ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 className="h-5 w-5 animate-spin" />
                Uploading...
              </span>
            ) : (
              'Upload Document'
            )}
          </button>
        </form>
      </main>
    </div>
  );
}

