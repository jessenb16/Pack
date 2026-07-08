'use client';

import { X, ZoomIn, Download, Trash2, Loader2, Pencil } from 'lucide-react';
import { formatDocDate } from '@/lib/date';
import { useCallback, useEffect, useRef, useState } from 'react';
import { apiClient, type DocumentApiRecord } from '@/lib/api';
import PdfScrollViewer from '@/components/PdfScrollViewer';
import ZoomableDocumentImage, {
  DOCUMENT_VIEWER_ZOOM,
} from '@/components/ZoomableDocumentImage';

export type DocumentViewerDocument = DocumentApiRecord;

export interface LabelCatalog {
  senders: { id: string; label: string }[];
  event_types: { id: string; label: string }[];
  recipients: { id: string; label: string }[];
}

interface DocumentViewerProps {
  isOpen: boolean;
  onClose: () => void;
  document: DocumentViewerDocument | null;
  uploaderId?: string;
  currentUserId?: string;
  onDelete?: (documentId: string) => void;
  catalog?: LabelCatalog;
  getAccessToken?: () => Promise<string | null>;
  organizationId?: string | null;
  onDocumentUpdated?: (doc: DocumentViewerDocument) => void;
}

export default function DocumentViewer({
  isOpen,
  onClose,
  document: doc,
  uploaderId,
  currentUserId,
  onDelete,
  catalog,
  getAccessToken,
  organizationId,
  onDocumentUpdated,
}: DocumentViewerProps) {
  const [scale, setScale] = useState(1);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [contentLoaded, setContentLoaded] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  const [senderMode, setSenderMode] = useState<'pick' | 'new'>('pick');
  const [senderId, setSenderId] = useState('');
  const [senderNew, setSenderNew] = useState('');
  const [eventMode, setEventMode] = useState<'pick' | 'new'>('pick');
  const [eventId, setEventId] = useState('');
  const [eventNew, setEventNew] = useState('');
  const [recipientMode, setRecipientMode] = useState<'none' | 'pick' | 'new'>('none');
  const [recipientId, setRecipientId] = useState('');
  const [recipientNew, setRecipientNew] = useState('');
  const [docDate, setDocDate] = useState('');
  const [caption, setCaption] = useState('');

  const canDelete = Boolean(
    uploaderId &&
      currentUserId &&
      String(uploaderId).trim() !== '' &&
      String(uploaderId) === String(currentUserId)
  );

  const canEdit = Boolean(
    canDelete &&
      catalog &&
      getAccessToken &&
      organizationId &&
      onDocumentUpdated
  );

  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  const resetEditForm = useCallback(() => {
    if (!doc) return;
    const m = doc.metadata;
    setSenderMode('pick');
    setSenderId(m.sender?.id || '');
    setSenderNew('');
    setEventMode('pick');
    setEventId(m.event_type?.id || '');
    setEventNew('');
    if (m.recipient?.id) {
      setRecipientMode('pick');
      setRecipientId(m.recipient.id);
      setRecipientNew('');
    } else if (m.recipient?.label) {
      setRecipientMode('new');
      setRecipientId('');
      setRecipientNew(m.recipient.label);
    } else {
      setRecipientMode('none');
      setRecipientId('');
      setRecipientNew('');
    }
    setDocDate(m.doc_date || '');
    setCaption(m.caption || '');
    setEditError(null);
  }, [doc]);

  useEffect(() => {
    if (showEdit && doc) resetEditForm();
  }, [showEdit, doc, resetEditForm]);

  const handleEscape = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape') onCloseRef.current();
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', handleEscape);
    return () => {
      document.body.style.overflow = 'unset';
      window.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen, handleEscape]);

  useEffect(() => {
    if (!isOpen) return;
    setContentLoaded(false);
    setScale(1);
    setShowDeleteConfirm(false);
    setIsDeleting(false);
    setShowEdit(false);
  }, [isOpen, doc?.id]);

  const handleDelete = async () => {
    if (!doc || !onDelete) return;

    if (!showDeleteConfirm) {
      setShowDeleteConfirm(true);
      return;
    }

    setIsDeleting(true);
    try {
      await onDelete(doc.id);
      // Parent typically clears the selected doc after deletion; ensure our
      // local delete state doesn't leak to the next opened document.
      setIsDeleting(false);
      setShowDeleteConfirm(false);
      onClose();
    } catch (error) {
      console.error('Error deleting document:', error);
      setIsDeleting(false);
      setShowDeleteConfirm(false);
    }
  };

  async function handleSaveMetadata(e: React.FormEvent) {
    e.preventDefault();
    if (!doc || !getAccessToken || !organizationId || !onDocumentUpdated) return;

    if (senderMode === 'pick' && !senderId) {
      setEditError('Select a sender/poster or add a new one.');
      return;
    }
    if (senderMode === 'new' && !senderNew.trim()) {
      setEditError('Enter a sender/poster name.');
      return;
    }
    if (eventMode === 'pick' && !eventId) {
      setEditError('Select an event or add a new one.');
      return;
    }
    if (eventMode === 'new' && !eventNew.trim()) {
      setEditError('Enter an event type.');
      return;
    }
    if (recipientMode === 'pick' && !recipientId) {
      setEditError('Select a recipient or switch to add new / none.');
      return;
    }
    if (recipientMode === 'new' && !recipientNew.trim()) {
      setEditError('Enter a recipient name or choose none.');
      return;
    }
    if (!caption.trim()) {
      setEditError('Caption is required.');
      return;
    }

    setEditSaving(true);
    setEditError(null);
    try {
      const token = await getAccessToken();
      const payload = {
        doc_date: docDate,
        caption: caption.trim(),
        sender_id: senderMode === 'pick' ? senderId : undefined,
        sender_label: senderMode === 'new' ? senderNew.trim() : undefined,
        event_type_id: eventMode === 'pick' ? eventId : undefined,
        event_type_label: eventMode === 'new' ? eventNew.trim() : undefined,
        recipient_id:
          recipientMode === 'pick' ? recipientId || undefined : undefined,
        recipient_label:
          recipientMode === 'new' ? recipientNew.trim() : undefined,
      };
      const res = await apiClient.patchDocumentMetadata(doc.id, payload, token);
      if (res.error || !res.data) {
        setEditError(typeof res.error === 'string' ? res.error : 'Save failed');
        return;
      }
      onDocumentUpdated(res.data);
      setShowEdit(false);
    } catch (err) {
      setEditError(err instanceof Error ? err.message : 'Save failed');
    } finally {
      setEditSaving(false);
    }
  }

  if (!isOpen || !doc) return null;

  const senderLabel = doc.metadata.sender?.label ?? '';
  const eventLabel = doc.metadata.event_type?.label ?? '';
  const recipientLabel = doc.metadata.recipient?.label;

  const isPdf =
    doc.file_type === 'application/pdf' ||
    doc.s3_original_url.toLowerCase().includes('.pdf');

  const sortedPages = doc.pages?.length
    ? [...doc.pages].sort((a, b) => a.page_number - b.page_number)
    : [];
  const isMultiImage =
    doc.file_type === 'image/multi' && sortedPages.length > 1;

  const handleMultiPageImageLoad = () => {
    setContentLoaded(true);
  };

  const handleToggleZoom = () =>
    setScale(scale > 1 ? 1 : DOCUMENT_VIEWER_ZOOM);

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/80 p-2 backdrop-blur-sm md:items-center md:p-8"
      role="dialog"
      aria-modal="true"
      aria-labelledby="document-viewer-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="relative my-auto flex min-h-0 max-h-[min(95dvh,100%)] w-full max-w-6xl flex-col rounded-lg bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex flex-shrink-0 flex-col gap-3 border-b bg-gray-50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div className="flex min-w-0 flex-1 items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <h2
                id="document-viewer-title"
                className="truncate text-lg font-bold text-gray-900 sm:text-xl"
              >
                {senderLabel}
                {recipientLabel && (
                  <span className="font-normal text-gray-600">
                    {' '}
                    to {recipientLabel}
                  </span>
                )}
              </h2>
              <div className="mt-1 flex flex-wrap gap-2 text-sm text-gray-600 sm:gap-3">
                <span className="rounded-full bg-gray-200 px-2 py-0.5 text-xs font-medium text-gray-700">
                  {eventLabel}
                </span>
                <span>
                  {formatDocDate(doc.metadata.doc_date)}
                </span>
              </div>
              {doc.metadata.caption && (
                <p className="mt-2 text-sm text-gray-700">{doc.metadata.caption}</p>
              )}
            </div>
            <button
              onClick={onClose}
              className="flex flex-shrink-0 items-center justify-center rounded-full bg-gray-300 p-3 text-gray-800 transition-colors hover:bg-gray-400 active:bg-gray-500 min-w-[44px] min-h-[44px] md:bg-gray-200 md:p-2 md:min-w-0 md:min-h-0 md:hover:bg-gray-300"
              aria-label="Close document"
            >
              <X className="h-6 w-6" />
            </button>
          </div>

          <div className="flex flex-shrink-0 flex-wrap gap-2">
            <button
              onClick={handleToggleZoom}
              className="flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200 transition-colors"
              title="Toggle Zoom"
            >
              <ZoomIn className="h-4 w-4" />
              {scale > 1 ? 'Reset' : 'Zoom'}
            </button>
            {canEdit && (
              <button
                type="button"
                onClick={() => setShowEdit(true)}
                className="flex items-center gap-1 rounded-lg bg-gray-200 px-4 py-2 text-sm font-medium text-gray-800 hover:bg-gray-300 transition-colors"
              >
                <Pencil className="h-4 w-4" />
                Edit metadata
              </button>
            )}
            {canDelete && (
              <button
                onClick={handleDelete}
                disabled={isDeleting}
                className={`flex items-center gap-1 rounded-lg px-4 py-2 text-sm font-medium text-white transition-colors ${
                  showDeleteConfirm
                    ? 'bg-red-600 hover:bg-red-700'
                    : 'bg-red-600 hover:bg-red-700'
                } ${isDeleting ? 'cursor-not-allowed opacity-50' : ''}`}
                title={
                  showDeleteConfirm ? 'Confirm deletion' : 'Delete document'
                }
              >
                <Trash2 className="h-4 w-4" />
                {isDeleting
                  ? 'Deleting...'
                  : showDeleteConfirm
                    ? 'Confirm Delete'
                    : 'Delete'}
              </button>
            )}
            <a
              href={doc.s3_original_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 rounded-lg bg-red-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-800"
            >
              <Download className="h-4 w-4" />
              Download
            </a>
          </div>
        </div>

        {showEdit && catalog && (
          <div className="border-b border-amber-200 bg-amber-50/80 px-4 py-4 sm:px-6">
            <h3 className="mb-3 text-sm font-semibold text-gray-800">Edit metadata</h3>
            {editError && (
              <p className="mb-3 rounded-lg bg-red-100 px-3 py-2 text-sm text-red-800">{editError}</p>
            )}
            <form onSubmit={handleSaveMetadata} className="grid gap-3 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <label className="mb-1 block text-xs font-medium text-gray-700">Sender / poster</label>
                <div className="flex flex-wrap gap-2">
                  <select
                    value={senderMode}
                    onChange={(e) => setSenderMode(e.target.value as 'pick' | 'new')}
                    className="rounded border border-gray-300 px-2 py-1.5 text-sm"
                  >
                    <option value="pick">Existing</option>
                    <option value="new">New</option>
                  </select>
                  {senderMode === 'pick' ? (
                    <select
                      value={senderId}
                      onChange={(e) => setSenderId(e.target.value)}
                      className="min-w-[12rem] flex-1 rounded border border-gray-300 px-2 py-1.5 text-sm"
                    >
                      <option value="">Select…</option>
                      {catalog.senders.map((s) => (
                        <option key={s.id} value={s.id}>{s.label}</option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      value={senderNew}
                      onChange={(e) => setSenderNew(e.target.value)}
                      className="min-w-[12rem] flex-1 rounded border border-gray-300 px-2 py-1.5 text-sm"
                      placeholder="Name"
                    />
                  )}
                </div>
              </div>
              <div className="sm:col-span-2">
                <label className="mb-1 block text-xs font-medium text-gray-700">Event</label>
                <div className="flex flex-wrap gap-2">
                  <select
                    value={eventMode}
                    onChange={(e) => setEventMode(e.target.value as 'pick' | 'new')}
                    className="rounded border border-gray-300 px-2 py-1.5 text-sm"
                  >
                    <option value="pick">Existing</option>
                    <option value="new">New</option>
                  </select>
                  {eventMode === 'pick' ? (
                    <select
                      value={eventId}
                      onChange={(e) => setEventId(e.target.value)}
                      className="min-w-[12rem] flex-1 rounded border border-gray-300 px-2 py-1.5 text-sm"
                    >
                      <option value="">Select…</option>
                      {catalog.event_types.map((s) => (
                        <option key={s.id} value={s.id}>{s.label}</option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      value={eventNew}
                      onChange={(e) => setEventNew(e.target.value)}
                      className="min-w-[12rem] flex-1 rounded border border-gray-300 px-2 py-1.5 text-sm"
                      placeholder="Event type"
                    />
                  )}
                </div>
              </div>
              <div className="sm:col-span-2">
                <label className="mb-1 block text-xs font-medium text-gray-700">Recipient (optional)</label>
                <div className="flex flex-wrap gap-2">
                  <select
                    value={recipientMode}
                    onChange={(e) =>
                      setRecipientMode(e.target.value as 'none' | 'pick' | 'new')
                    }
                    className="rounded border border-gray-300 px-2 py-1.5 text-sm"
                  >
                    <option value="none">None</option>
                    <option value="pick">Existing</option>
                    <option value="new">New</option>
                  </select>
                  {recipientMode === 'pick' && (
                    <select
                      value={recipientId}
                      onChange={(e) => setRecipientId(e.target.value)}
                      className="min-w-[12rem] flex-1 rounded border border-gray-300 px-2 py-1.5 text-sm"
                    >
                      <option value="">Select…</option>
                      {catalog.recipients.map((s) => (
                        <option key={s.id} value={s.id}>{s.label}</option>
                      ))}
                    </select>
                  )}
                  {recipientMode === 'new' && (
                    <input
                      type="text"
                      value={recipientNew}
                      onChange={(e) => setRecipientNew(e.target.value)}
                      className="min-w-[12rem] flex-1 rounded border border-gray-300 px-2 py-1.5 text-sm"
                      placeholder="Recipient"
                    />
                  )}
                </div>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-700">Document date</label>
                <input
                  type="date"
                  value={docDate}
                  onChange={(e) => setDocDate(e.target.value)}
                  className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm"
                  required
                />
              </div>
              <div className="sm:col-span-2">
                <label className="mb-1 block text-xs font-medium text-gray-700">Caption</label>
                <textarea
                  value={caption}
                  onChange={(e) => setCaption(e.target.value)}
                  className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm min-h-[72px]"
                  required
                  rows={2}
                />
              </div>
              <div className="flex flex-wrap gap-2 sm:col-span-2">
                <button
                  type="submit"
                  disabled={editSaving}
                  className="rounded-lg bg-red-900 px-4 py-2 text-sm font-medium text-white hover:bg-red-800 disabled:opacity-50"
                >
                  {editSaving ? 'Saving…' : 'Save'}
                </button>
                <button
                  type="button"
                  onClick={() => setShowEdit(false)}
                  className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}

        <div
          data-document-viewer-scroll
          className="relative min-h-0 flex-1 overflow-auto overscroll-contain bg-gray-100 p-4"
          style={{ touchAction: 'pan-x pan-y pinch-zoom' }}
        >
          {isPdf ? (
            <>
              {!contentLoaded && doc.s3_thumbnail_url && (
                <div className="flex min-h-[60vh] items-center justify-center">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={doc.s3_thumbnail_url}
                    alt="Loading preview"
                    className="max-h-[60vh] max-w-full object-contain rounded shadow-md opacity-80"
                  />
                </div>
              )}
              <div
                className={`${contentLoaded ? '' : 'absolute inset-0 opacity-0'}`}
              >
                <PdfScrollViewer
                  url={doc.s3_original_url}
                  scale={scale}
                  onLoaded={() => setContentLoaded(true)}
                  onError={() => setContentLoaded(true)}
                  onToggleZoom={handleToggleZoom}
                />
              </div>
              {!contentLoaded && (
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-white/70">
                  <Loader2 className="h-10 w-10 animate-spin text-gray-600" aria-hidden />
                  <p className="text-sm font-medium text-gray-600">Loading document…</p>
                </div>
              )}
            </>
          ) : isMultiImage ? (
            <>
              {!contentLoaded && doc.s3_thumbnail_url && (
                <div className="flex min-h-[40vh] items-center justify-center">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={doc.s3_thumbnail_url}
                    alt="Loading preview"
                    className="max-h-[50vh] max-w-full object-contain rounded shadow-md opacity-80"
                  />
                </div>
              )}
              <div
                className={`flex flex-col items-center gap-10 py-2 ${
                  contentLoaded ? '' : 'absolute inset-0 opacity-0'
                }`}
              >
                {sortedPages.map((page) => (
                  <div key={page.page_number} className="w-full max-w-4xl">
                    <p className="mb-2 text-center text-sm font-medium text-gray-600">
                      Page {page.page_number} of {sortedPages.length}
                    </p>
                    <div className="flex justify-center">
                      <ZoomableDocumentImage
                        src={page.s3_original_url}
                        alt={`Document page ${page.page_number}`}
                        scale={scale}
                        onLoad={handleMultiPageImageLoad}
                        onToggleZoom={handleToggleZoom}
                      />
                    </div>
                  </div>
                ))}
              </div>
              {!contentLoaded && (
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-white/70">
                  <Loader2 className="h-10 w-10 animate-spin text-gray-600" aria-hidden />
                  <p className="text-sm font-medium text-gray-600">Loading pages…</p>
                </div>
              )}
            </>
          ) : (
            <>
              {!contentLoaded && doc.s3_thumbnail_url && (
                <div className="flex min-h-[50vh] items-center justify-center">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={doc.s3_thumbnail_url}
                    alt="Loading preview"
                    className="max-h-[60vh] max-w-full object-contain rounded shadow-md opacity-80"
                  />
                </div>
              )}
              <div
                className={`flex items-center justify-center ${contentLoaded ? '' : 'absolute inset-0 opacity-0'}`}
              >
                <div className="w-full max-w-4xl">
                  <ZoomableDocumentImage
                    src={doc.s3_original_url}
                    alt="Document"
                    scale={scale}
                    onLoad={() => setContentLoaded(true)}
                    onToggleZoom={handleToggleZoom}
                  />
                </div>
              </div>
              {!contentLoaded && (
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-white/70">
                  <Loader2 className="h-10 w-10 animate-spin text-gray-600" aria-hidden />
                  <p className="text-sm font-medium text-gray-600">Loading full size…</p>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
