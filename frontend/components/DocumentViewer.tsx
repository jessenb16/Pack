'use client';

import { X, ZoomIn, Download, Trash2, Loader2 } from 'lucide-react';
import { formatDocDate } from '@/lib/date';
import { useCallback, useEffect, useState } from 'react';

export interface DocumentViewerDocument {
  id: string;
  s3_original_url: string;
  s3_thumbnail_url?: string;
  uploader_id?: string;
  metadata: {
    sender_name: string;
    event_type: string;
    doc_date: string;
    recipient_name?: string;
  };
  file_type: string;
}

interface DocumentViewerProps {
  isOpen: boolean;
  onClose: () => void;
  document: DocumentViewerDocument | null;
  uploaderId?: string;
  currentUserId?: string;
  onDelete?: (documentId: string) => void;
}

export default function DocumentViewer({
  isOpen,
  onClose,
  document: doc,
  uploaderId,
  currentUserId,
  onDelete,
}: DocumentViewerProps) {
  const [scale, setScale] = useState(1);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [contentLoaded, setContentLoaded] = useState(false);

  const canDelete = Boolean(
    uploaderId &&
      currentUserId &&
      String(uploaderId).trim() !== '' &&
      String(uploaderId) === String(currentUserId)
  );

  const handleEscape = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    },
    [onClose]
  );

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      window.addEventListener('keydown', handleEscape);
      setContentLoaded(false);
      queueMicrotask(() => {
        setScale(1);
        setShowDeleteConfirm(false);
      });
    }
    return () => {
      document.body.style.overflow = 'unset';
      window.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen, handleEscape, doc?.id]);

  const handleDelete = async () => {
    if (!doc || !onDelete) return;

    if (!showDeleteConfirm) {
      setShowDeleteConfirm(true);
      return;
    }

    setIsDeleting(true);
    try {
      await onDelete(doc.id);
    } catch (error) {
      console.error('Error deleting document:', error);
      setIsDeleting(false);
      setShowDeleteConfirm(false);
    }
  };

  if (!isOpen || !doc) return null;

  const isPdf =
    doc.file_type === 'application/pdf' ||
    doc.s3_original_url.toLowerCase().includes('.pdf');

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
        {/* Header with close button - always visible at top */}
        <div className="flex flex-shrink-0 flex-col gap-3 border-b bg-gray-50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div className="flex min-w-0 flex-1 items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <h2
                id="document-viewer-title"
                className="truncate text-lg font-bold text-gray-900 sm:text-xl"
              >
                {doc.metadata.sender_name}
                {doc.metadata.recipient_name && (
                  <span className="font-normal text-gray-600">
                    {' '}
                    to {doc.metadata.recipient_name}
                  </span>
                )}
              </h2>
              <div className="mt-1 flex flex-wrap gap-2 text-sm text-gray-600 sm:gap-3">
                <span className="rounded-full bg-gray-200 px-2 py-0.5 text-xs font-medium text-gray-700">
                  {doc.metadata.event_type}
                </span>
                <span>
                  {formatDocDate(doc.metadata.doc_date)}
                </span>
              </div>
            </div>
            {/* Close button - inside header, always visible, prominent on mobile */}
            <button
              onClick={onClose}
              className="flex flex-shrink-0 items-center justify-center rounded-full bg-gray-300 p-3 text-gray-800 transition-colors hover:bg-gray-400 active:bg-gray-500 min-w-[44px] min-h-[44px] md:bg-gray-200 md:p-2 md:min-w-0 md:min-h-0 md:hover:bg-gray-300"
              aria-label="Close document"
            >
              <X className="h-6 w-6" />
            </button>
          </div>

          <div className="flex flex-shrink-0 flex-wrap gap-2">
            {!isPdf && (
              <button
                onClick={() => setScale(scale > 1 ? 1 : 1.5)}
                className="flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200 transition-colors"
                title="Toggle Zoom"
              >
                <ZoomIn className="h-4 w-4" />
                {scale > 1 ? 'Reset' : 'Zoom'}
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

        {/* Content - scrollable */}
        <div className="relative min-h-0 flex-1 overflow-auto bg-gray-100 p-4">
          {isPdf ? (
            <>
              {/* Thumbnail placeholder - instant feedback while PDF loads */}
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
              <iframe
                src={doc.s3_original_url}
                className={`h-full min-h-[60vh] w-full rounded shadow-sm bg-white ${contentLoaded ? 'block' : 'absolute inset-0 opacity-0'}`}
                title="PDF Viewer"
                onLoad={() => setContentLoaded(true)}
              />
              {!contentLoaded && (
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-white/70">
                  <Loader2 className="h-10 w-10 animate-spin text-gray-600" aria-hidden />
                  <p className="text-sm font-medium text-gray-600">Loading document…</p>
                </div>
              )}
            </>
          ) : (
            <>
              {/* Thumbnail placeholder - instant feedback while full image loads */}
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
                className={`flex items-center justify-center ${contentLoaded ? '' : 'absolute inset-0 opacity-0'} ${scale > 1 ? 'cursor-zoom-out' : 'cursor-zoom-in'}`}
                onClick={() => setScale(scale > 1 ? 1 : 1.5)}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={doc.s3_original_url}
                  alt="Document"
                  className="max-h-[70vh] max-w-full w-auto object-contain rounded shadow-md"
                  style={{ transform: `scale(${scale})` }}
                  onLoad={() => setContentLoaded(true)}
                />
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
