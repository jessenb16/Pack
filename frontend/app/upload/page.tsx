'use client';

import { useCallback, useEffect, useState } from 'react';
import { useUser, useAuth } from '@clerk/nextjs';
import { useRouter } from 'next/navigation';
import Navbar from '@/components/Navbar';
import { apiClient } from '@/lib/api';
import type { LabelCatalog } from '@/components/DocumentViewer';
import { Upload as UploadIcon, Loader2, FileText, GripVertical, X, ChevronUp, ChevronDown } from 'lucide-react';
import { getTodayLocalDateString } from '@/lib/date';

/** Mirror backend MAX_MULTI_IMAGE_PAGES */
const MAX_MULTI_IMAGE_PAGES = 5;

type OrderedFile = {
  id: string;
  file: File;
  preview: string | null;
};

function isPdfFile(file: File): boolean {
  return (
    file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
  );
}

function isImageFile(file: File): boolean {
  if (file.type.startsWith('image/')) return true;
  return /\.(png|jpe?g|gif|webp|jfif)$/i.test(file.name);
}

function validateFileList(files: File[]): string | null {
  if (files.length === 0) {
    return 'Please select at least one file to upload';
  }
  if (files.length > MAX_MULTI_IMAGE_PAGES) {
    return `You can upload at most ${MAX_MULTI_IMAGE_PAGES} images in one document`;
  }
  const hasPdf = files.some(isPdfFile);
  if (hasPdf && files.length > 1) {
    return 'PDFs must be uploaded alone. Remove extra images or upload images without a PDF.';
  }
  if (files.length >= 2) {
    const nonImage = files.find((f) => !isImageFile(f));
    if (nonImage) {
      return 'Multi-image uploads must be images only (no PDFs).';
    }
  }
  if (files.length === 1 && !isImageFile(files[0]) && !isPdfFile(files[0])) {
    return 'Please select an image or PDF file';
  }
  return null;
}

export default function UploadPage() {
  const { user, isLoaded } = useUser();
  const { getToken, orgId } = useAuth();
  const router = useRouter();
  const [uploadMode, setUploadMode] = useState<'file' | 'text'>('file');
  const [orderedFiles, setOrderedFiles] = useState<OrderedFile[]>([]);
  const [textContent, setTextContent] = useState('');
  const [customFilename, setCustomFilename] = useState('');
  const [dragIndex, setDragIndex] = useState<number | null>(null);
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
  const [enableDragReorder, setEnableDragReorder] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia('(hover: hover) and (pointer: fine)');
    const update = () => setEnableDragReorder(mq.matches);
    update();
    mq.addEventListener('change', update);
    return () => mq.removeEventListener('change', update);
  }, []);

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
    setOrderedFiles([]);
    setTextContent('');
    setCustomFilename('');
    loadFamilyData();
  }, [orgId, loadFamilyData]);

  function loadPreviewForItem(item: OrderedFile) {
    if (!isImageFile(item.file)) return;
    const reader = new FileReader();
    reader.onloadend = () => {
      setOrderedFiles((prev) =>
        prev.map((p) =>
          p.id === item.id ? { ...p, preview: reader.result as string } : p
        )
      );
    };
    reader.readAsDataURL(item.file);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(e.target.files || []);
    e.target.value = '';
    if (!selected.length) return;

    const combined = [...orderedFiles.map((o) => o.file), ...selected];
    const err = validateFileList(combined);
    if (err) {
      alert(err);
      return;
    }

    const newItems: OrderedFile[] = selected.map((file) => ({
      id: `${file.name}-${file.size}-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      file,
      preview: null,
    }));

    setOrderedFiles((prev) => [...prev, ...newItems].slice(0, MAX_MULTI_IMAGE_PAGES));
    newItems.forEach(loadPreviewForItem);
  }

  function removeFile(id: string) {
    setOrderedFiles((prev) => prev.filter((o) => o.id !== id));
  }

  function reorderFiles(fromIndex: number, toIndex: number) {
    if (fromIndex === toIndex) return;
    setOrderedFiles((prev) => {
      const next = [...prev];
      const [moved] = next.splice(fromIndex, 1);
      next.splice(toIndex, 0, moved);
      return next;
    });
  }

  function moveFileEarlier(index: number) {
    if (index <= 0) return;
    reorderFiles(index, index - 1);
  }

  function moveFileLater(index: number) {
    if (index >= orderedFiles.length - 1) return;
    reorderFiles(index, index + 1);
  }

  function handleDragStart(index: number) {
    setDragIndex(index);
  }

  function handleDragOver(e: React.DragEvent, index: number) {
    e.preventDefault();
    if (dragIndex === null || dragIndex === index) return;
    reorderFiles(dragIndex, index);
    setDragIndex(index);
  }

  function handleDragEnd() {
    setDragIndex(null);
  }

  function switchMode(mode: 'file' | 'text') {
    setUploadMode(mode);
    if (mode === 'file') {
      setTextContent('');
      setCustomFilename('');
    } else {
      setOrderedFiles([]);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const files = orderedFiles.map((o) => o.file);
    const hasFiles = files.length > 0;
    const hasText = textContent.trim().length > 0;

    if (!hasFiles && !hasText) {
      alert(
        uploadMode === 'file'
          ? 'Please select a file to upload'
          : 'Please enter or paste some text'
      );
      return;
    }

    if (hasFiles) {
      const err = validateFileList(files);
      if (err) {
        alert(err);
        return;
      }
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
          ...(files.length >= 2 && { files }),
          ...(files.length === 1 && { file: files[0] }),
          ...(hasText && { text: textContent.trim() }),
          ...(hasText && customFilename.trim() && { custom_filename: customFilename.trim() }),
          sender_id: senderMode === 'pick' ? senderId : undefined,
          sender_label: senderMode === 'new' ? senderNew.trim() : undefined,
          event_type_id: eventMode === 'pick' ? eventId : undefined,
          event_type_label: eventMode === 'new' ? eventNew.trim() : undefined,
          recipient_id: recipientMode === 'pick' ? recipientId || undefined : undefined,
          recipient_label: recipientMode === 'new' ? recipientNew.trim() : undefined,
          doc_date: formData.doc_date,
          caption: formData.caption.trim(),
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

  const isMultiImage = orderedFiles.length >= 2;

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
            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700">
                Select file{orderedFiles.length === 0 ? 's' : ''}
              </label>
              <p className="mb-3 text-xs text-gray-500">
                Upload one PDF or image, or select multiple images (up to {MAX_MULTI_IMAGE_PAGES}) for a
                multi-page document. Drag to reorder on desktop, or use the arrows on mobile.
              </p>
              <div className="flex items-center justify-center rounded-lg border-2 border-dashed border-purple-200 bg-purple-50/30 p-6">
                <div className="w-full text-center">
                  <UploadIcon className="mx-auto h-10 w-10 text-purple-400" />
                  <div className="mt-4">
                    <label className="cursor-pointer rounded-lg bg-purple-600 px-4 py-2 text-white transition-colors shadow-sm hover:bg-purple-700">
                      {orderedFiles.length ? 'Add more images' : 'Choose files'}
                      <input
                        type="file"
                        className="hidden"
                        accept="image/*,.pdf"
                        multiple
                        onChange={handleFileChange}
                      />
                    </label>
                  </div>
                </div>
              </div>

              {orderedFiles.length > 0 && (
                <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
                  {orderedFiles.map((item, index) => (
                    <div
                      key={item.id}
                      draggable={enableDragReorder}
                      onDragStart={
                        enableDragReorder ? () => handleDragStart(index) : undefined
                      }
                      onDragOver={
                        enableDragReorder ? (e) => handleDragOver(e, index) : undefined
                      }
                      onDragEnd={enableDragReorder ? handleDragEnd : undefined}
                      className={`relative rounded-lg border bg-gray-50 p-2 ${
                        enableDragReorder && dragIndex === index
                          ? 'border-purple-500 ring-2 ring-purple-200'
                          : 'border-gray-200'
                      }`}
                    >
                      <span className="absolute left-2 top-2 z-10 rounded bg-purple-600 px-1.5 py-0.5 text-xs font-semibold text-white">
                        {index + 1}
                      </span>
                      <button
                        type="button"
                        onClick={() => removeFile(item.id)}
                        className="absolute right-2 top-2 z-10 rounded-full bg-gray-800/70 p-1 text-white hover:bg-gray-900"
                        aria-label={`Remove page ${index + 1}`}
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                      <div className="flex aspect-square items-center justify-center overflow-hidden rounded-md bg-white">
                        {item.preview ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={item.preview}
                            alt={`Page ${index + 1}`}
                            className="max-h-full max-w-full object-contain"
                          />
                        ) : (
                          <FileText className="h-10 w-10 text-gray-400" />
                        )}
                      </div>
                      {orderedFiles.length > 1 && (
                        <div className="mt-2 flex justify-center gap-1 sm:hidden">
                          <button
                            type="button"
                            onClick={() => moveFileEarlier(index)}
                            disabled={index === 0}
                            className="rounded-md border border-gray-300 bg-white p-2 text-gray-700 disabled:cursor-not-allowed disabled:opacity-40"
                            aria-label={`Move page ${index + 1} earlier`}
                          >
                            <ChevronUp className="h-4 w-4" />
                          </button>
                          <button
                            type="button"
                            onClick={() => moveFileLater(index)}
                            disabled={index === orderedFiles.length - 1}
                            className="rounded-md border border-gray-300 bg-white p-2 text-gray-700 disabled:cursor-not-allowed disabled:opacity-40"
                            aria-label={`Move page ${index + 1} later`}
                          >
                            <ChevronDown className="h-4 w-4" />
                          </button>
                        </div>
                      )}
                      <div className="mt-2 flex items-center gap-1 text-xs text-gray-600">
                        <GripVertical
                          className="hidden h-3.5 w-3.5 flex-shrink-0 text-gray-400 sm:block"
                          aria-hidden
                        />
                        <span className="truncate" title={item.file.name}>
                          {item.file.name}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {isMultiImage && (
                <p className="mt-2 text-sm text-purple-800">
                  {orderedFiles.length} pages — will be saved as one document
                </p>
              )}
            </div>
          ) : (
            <>
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">
                  Your text
                </label>
                <textarea
                  placeholder="Write or paste your text here. It will be saved as a PDF."
                  value={textContent}
                  onChange={(e) => setTextContent(e.target.value)}
                  className="min-h-[120px] w-full resize-y rounded-lg border border-gray-300 px-4 py-2 font-mono text-sm focus:border-red-900 focus:outline-none focus:ring-2 focus:ring-red-900"
                  rows={6}
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">
                  File name <span className="text-xs text-gray-500">(optional)</span>
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
                    <option key={s.id} value={s.id}>
                      {s.label}
                    </option>
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
                    <option key={s.id} value={s.id}>
                      {s.label}
                    </option>
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

          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              Caption <span className="text-red-600">*</span>
            </label>
            <textarea
              placeholder="Describe your document in one or two sentences. This helps your Pack find it later."
              value={formData.caption}
              onChange={(e) => setFormData({ ...formData, caption: e.target.value })}
              className="min-h-[80px] w-full resize-y rounded-lg border border-gray-300 px-4 py-2 focus:border-red-900 focus:outline-none focus:ring-2 focus:ring-red-900"
              required
              rows={3}
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              Recipient <span className="text-xs text-gray-500">(optional)</span>
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
                    <option key={s.id} value={s.id}>
                      {s.label}
                    </option>
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

          <button
            type="submit"
            disabled={
              uploading ||
              (uploadMode === 'file' ? orderedFiles.length === 0 : !textContent.trim()) ||
              !formData.caption?.trim() ||
              (senderMode === 'pick' && !senderId) ||
              (senderMode === 'new' && !senderNew.trim()) ||
              (eventMode === 'pick' && !eventId) ||
              (eventMode === 'new' && !eventNew.trim()) ||
              (recipientMode === 'pick' && !recipientId) ||
              (recipientMode === 'new' && !recipientNew.trim())
            }
            className="w-full rounded-lg bg-purple-600 px-6 py-3 text-white shadow-sm transition-colors hover:bg-purple-700 disabled:bg-gray-400"
          >
            {uploading ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 className="h-5 w-5 animate-spin" />
                {isMultiImage
                  ? `Processing ${orderedFiles.length} pages…`
                  : 'Uploading...'}
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
