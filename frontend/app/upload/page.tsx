'use client';

import { useCallback, useEffect, useState } from 'react';
import { useUser, useAuth } from '@clerk/nextjs';
import { useRouter } from 'next/navigation';
import Navbar from '@/components/Navbar';
import { apiClient } from '@/lib/api';
import type { LabelCatalog } from '@/components/DocumentViewer';
import { Upload as UploadIcon, Loader2, FileText } from 'lucide-react';
import { getTodayLocalDateString } from '@/lib/date';

export default function UploadPage() {
  const { user, isLoaded } = useUser();
  const { getToken, orgId } = useAuth();
  const router = useRouter();
  const [uploadMode, setUploadMode] = useState<'file' | 'text'>('file');
  const [file, setFile] = useState<File | null>(null);
  const [textContent, setTextContent] = useState('');
  const [customFilename, setCustomFilename] = useState('');
  const [preview, setPreview] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    doc_date: getTodayLocalDateString(),
    caption: '',
  });
  const [catalog, setCatalog] = useState<LabelCatalog>({
    senders: [],
    event_types: [],
    recipients: [],
  });
  const [senderMode, setSenderMode] = useState<'pick' | 'new'>('pick');
  const [senderId, setSenderId] = useState('');
  const [senderNew, setSenderNew] = useState('');
  const [eventMode, setEventMode] = useState<'pick' | 'new'>('pick');
  const [eventId, setEventId] = useState('');
  const [eventNew, setEventNew] = useState('');
  const [recipientMode, setRecipientMode] = useState<'none' | 'pick' | 'new'>('none');
  const [recipientId, setRecipientId] = useState('');
  const [recipientNew, setRecipientNew] = useState('');
  const [uploading, setUploading] = useState(false);

  const loadFamilyData = useCallback(async () => {
    try {
      const token = await getToken({ organizationId: orgId || undefined });
      const familyResponse = await apiClient.getFamily(token);
      
      if (familyResponse.data) {
        const d = familyResponse.data as Record<string, unknown>;
        setCatalog({
          senders: Array.isArray(d.senders) ? (d.senders as LabelCatalog['senders']) : [],
          event_types: Array.isArray(d.event_types) ? (d.event_types as LabelCatalog['event_types']) : [],
          recipients: Array.isArray(d.recipients) ? (d.recipients as LabelCatalog['recipients']) : [],
        });
      }
    } catch (error) {
      console.error('Error loading family data:', error);
    }
  }, [getToken, orgId]);

  useEffect(() => {
    if (!isLoaded) return;
    
    if (!user) {
      router.push('/login');
      return;
    }

    if (!orgId) return;
    loadFamilyData();
  }, [user, isLoaded, router, orgId, loadFamilyData]);

  useEffect(() => {
    if (!orgId) return;
    setCatalog({ senders: [], event_types: [], recipients: [] });
    setFormData((prev) => ({
      ...prev,
      caption: '',
      doc_date: getTodayLocalDateString(),
    }));
    setSenderMode('pick');
    setSenderId('');
    setSenderNew('');
    setEventMode('pick');
    setEventId('');
    setEventNew('');
    setRecipientMode('none');
    setRecipientId('');
    setRecipientNew('');
    setUploadMode('file');
    setFile(null);
    setTextContent('');
    setCustomFilename('');
    setPreview(null);
    loadFamilyData();
  }, [orgId, loadFamilyData]);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      setPreview(null);
      const reader = new FileReader();
      reader.onloadend = () => {
        setPreview(reader.result as string);
      };
      reader.readAsDataURL(selectedFile);
    }
  }

  function switchMode(mode: 'file' | 'text') {
    setUploadMode(mode);
    if (mode === 'file') {
      setTextContent('');
      setCustomFilename('');
    } else {
      setFile(null);
      setPreview(null);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const hasFile = file && file.size > 0;
    const hasText = textContent.trim().length > 0;
    if (!hasFile && !hasText) {
      alert(uploadMode === 'file'
        ? 'Please select a file to upload'
        : 'Please enter or paste some text');
      return;
    }
    if (senderMode === 'pick' && !senderId) {
      alert('Select a sender/poster or add a new one');
      return;
    }
    if (senderMode === 'new' && !senderNew.trim()) {
      alert('Enter a sender/poster name');
      return;
    }
    if (eventMode === 'pick' && !eventId) {
      alert('Select an event or add a new one');
      return;
    }
    if (eventMode === 'new' && !eventNew.trim()) {
      alert('Enter an event type');
      return;
    }
    if (recipientMode === 'pick' && !recipientId) {
      alert('Select a recipient, add a new one, or choose none');
      return;
    }
    if (recipientMode === 'new' && !recipientNew.trim()) {
      alert('Enter a recipient name or choose none');
      return;
    }
    if (!formData.doc_date || !formData.caption?.trim()) {
      alert('Please fill in all required fields');
      return;
    }

    setUploading(true);
    try {
      const token = await getToken({ organizationId: orgId || undefined });
      const response = await apiClient.uploadDocument(
        {
          ...(hasFile && { file }),
          ...(hasText && { text: textContent.trim() }),
          ...(hasText && customFilename.trim() && { custom_filename: customFilename.trim() }),
          sender_id: senderMode === 'pick' ? senderId : undefined,
          sender_label: senderMode === 'new' ? senderNew.trim() : undefined,
          event_type_id: eventMode === 'pick' ? eventId : undefined,
          event_type_label: eventMode === 'new' ? eventNew.trim() : undefined,
          recipient_id: recipientMode === 'pick' ? recipientId || undefined : undefined,
          recipient_label: recipientMode === 'new' ? recipientNew.trim() : undefined,
          doc_date: formData.doc_date,
          caption: formData.caption.trim()
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
    <div className="min-h-screen bg-gradient-to-br from-stone-100 via-slate-50 to-stone-100">
      <Navbar />
      
      <main className="mx-auto max-w-2xl px-4 py-8">
        <h1 className="mb-8 text-3xl font-bold text-gray-800">Upload Document</h1>
        
        <form onSubmit={handleSubmit} className="space-y-6 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          {/* Upload mode toggle */}
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              Add document
            </label>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => switchMode('file')}
                className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                  uploadMode === 'file'
                    ? 'bg-purple-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                <UploadIcon className="h-4 w-4" />
                Upload file
              </button>
              <button
                type="button"
                onClick={() => switchMode('text')}
                className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                  uploadMode === 'text'
                    ? 'bg-purple-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                <FileText className="h-4 w-4" />
                Write or paste text
              </button>
            </div>
          </div>

          {uploadMode === 'file' ? (
            <>
              {/* File Upload */}
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">
                  Select File
                </label>
                <div className="flex items-center justify-center rounded-lg border-2 border-dashed border-purple-200 bg-purple-50/30 p-8">
                  <div className="text-center">
                    <UploadIcon className="mx-auto h-12 w-12 text-purple-400" />
                    <div className="mt-4">
                      <label className="cursor-pointer rounded-lg bg-purple-600 px-4 py-2 text-white hover:bg-purple-700 transition-colors shadow-sm">
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
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={preview}
                      alt="Preview"
                      className="mx-auto max-h-64 rounded-lg"
                    />
                  </div>
                )}
              </div>
            </>
          ) : (
            <>
              {/* Text input */}
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">
                  Your text
                </label>
                <textarea
                  placeholder="Write or paste your text here. It will be saved as a PDF."
                  value={textContent}
                  onChange={(e) => setTextContent(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-red-900 focus:outline-none focus:ring-2 focus:ring-red-900 min-h-[120px] resize-y font-mono text-sm"
                  rows={6}
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">
                  File name <span className="text-gray-500 text-xs">(optional)</span>
                </label>
                <input
                  type="text"
                  placeholder="e.g. Mom's recipe, Vacation notes"
                  value={customFilename}
                  onChange={(e) => setCustomFilename(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-red-900 focus:outline-none focus:ring-2 focus:ring-red-900"
                />
                <p className="mt-1 text-xs text-gray-500">
                  Leave blank to use an automatic name
                </p>
              </div>
            </>
          )}

          {/* Sender/Poster */}
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              Sender/Poster <span className="text-red-600">*</span>
            </label>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <select
                value={senderMode}
                onChange={(e) => setSenderMode(e.target.value as 'pick' | 'new')}
                className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
              >
                <option value="pick">Choose existing</option>
                <option value="new">Add new</option>
              </select>
              {senderMode === 'pick' ? (
                <select
                  value={senderId}
                  onChange={(e) => setSenderId(e.target.value)}
                  className="w-full flex-1 rounded-lg border border-gray-300 px-4 py-2 focus:border-red-900 focus:outline-none focus:ring-2 focus:ring-red-900"
                  required
                >
                  <option value="">Select sender/poster...</option>
                  {catalog.senders.map((s) => (
                    <option key={s.id} value={s.id}>{s.label}</option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  value={senderNew}
                  onChange={(e) => setSenderNew(e.target.value)}
                  className="w-full flex-1 rounded-lg border border-gray-300 px-4 py-2 focus:border-red-900 focus:outline-none focus:ring-2 focus:ring-red-900"
                  placeholder="Name"
                  required
                />
              )}
            </div>
          </div>

          {/* Event Type */}
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              Event Type <span className="text-red-600">*</span>
            </label>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <select
                value={eventMode}
                onChange={(e) => setEventMode(e.target.value as 'pick' | 'new')}
                className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
              >
                <option value="pick">Choose existing</option>
                <option value="new">Add new</option>
              </select>
              {eventMode === 'pick' ? (
                <select
                  value={eventId}
                  onChange={(e) => setEventId(e.target.value)}
                  className="w-full flex-1 rounded-lg border border-gray-300 px-4 py-2 focus:border-red-900 focus:outline-none focus:ring-2 focus:ring-red-900"
                  required
                >
                  <option value="">Select event type...</option>
                  {catalog.event_types.map((s) => (
                    <option key={s.id} value={s.id}>{s.label}</option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  placeholder="Enter event type..."
                  value={eventNew}
                  onChange={(e) => setEventNew(e.target.value)}
                  className="w-full flex-1 rounded-lg border border-gray-300 px-4 py-2 focus:border-red-900 focus:outline-none focus:ring-2 focus:ring-red-900"
                  required
                />
              )}
            </div>
          </div>

          {/* Caption (Required) */}
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              Caption <span className="text-red-600">*</span>
            </label>
            <textarea
              placeholder="Describe your document in one or two sentences. This helps the family find it later."
              value={formData.caption}
              onChange={(e) => setFormData({ ...formData, caption: e.target.value })}
              className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-red-900 focus:outline-none focus:ring-2 focus:ring-red-900 min-h-[80px] resize-y"
              required
              rows={3}
            />
          </div>

          {/* Recipient (Optional) */}
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              Recipient <span className="text-gray-500 text-xs">(optional)</span>
            </label>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <select
                value={recipientMode}
                onChange={(e) =>
                  setRecipientMode(e.target.value as 'none' | 'pick' | 'new')
                }
                className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
              >
                <option value="none">None</option>
                <option value="pick">Choose existing</option>
                <option value="new">Add new</option>
              </select>
              {recipientMode === 'pick' && (
                <select
                  value={recipientId}
                  onChange={(e) => setRecipientId(e.target.value)}
                  className="w-full flex-1 rounded-lg border border-gray-300 px-4 py-2 focus:border-red-900 focus:outline-none focus:ring-2 focus:ring-red-900"
                >
                  <option value="">Select recipient...</option>
                  {catalog.recipients.map((s) => (
                    <option key={s.id} value={s.id}>{s.label}</option>
                  ))}
                </select>
              )}
              {recipientMode === 'new' && (
                <input
                  type="text"
                  placeholder="Who is this for?"
                  value={recipientNew}
                  onChange={(e) => setRecipientNew(e.target.value)}
                  className="w-full flex-1 rounded-lg border border-gray-300 px-4 py-2 focus:border-red-900 focus:outline-none focus:ring-2 focus:ring-red-900"
                />
              )}
            </div>
          </div>

          {/* Date of document */}
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              Date of document
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
            disabled={
              uploading ||
              (uploadMode === 'file' ? !file : !textContent.trim()) ||
              !formData.caption?.trim() ||
              (senderMode === 'pick' && !senderId) ||
              (senderMode === 'new' && !senderNew.trim()) ||
              (eventMode === 'pick' && !eventId) ||
              (eventMode === 'new' && !eventNew.trim()) ||
              (recipientMode === 'pick' && !recipientId) ||
              (recipientMode === 'new' && !recipientNew.trim())
            }
            className="w-full rounded-lg bg-purple-600 px-6 py-3 text-white transition-colors hover:bg-purple-700 disabled:bg-gray-400 shadow-sm"
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

