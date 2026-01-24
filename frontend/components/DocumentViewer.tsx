'use client';

import { X, ZoomIn, Download, ExternalLink } from 'lucide-react';
import { useEffect, useState } from 'react';

interface DocumentViewerProps {
  isOpen: boolean;
  onClose: () => void;
  document: {
    id: string;
    s3_original_url: string;
    metadata: {
      sender_name: string;
      event_type: string;
      doc_date: string;
      recipient_name?: string;
    };
    file_type: string;
  } | null;
}

export default function DocumentViewer({ isOpen, onClose, document: doc }: DocumentViewerProps) {
  const [scale, setScale] = useState(1);

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
      setScale(1); // Reset zoom on close
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isOpen]);

  if (!isOpen || !doc) return null;

  const isPdf = doc.file_type === 'application/pdf' || doc.s3_original_url.toLowerCase().includes('.pdf');

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 md:p-8">
      {/* Close button - top right */}
      <button 
        onClick={onClose}
        className="absolute right-4 top-4 z-50 rounded-full bg-white/10 p-2 text-white hover:bg-white/20 transition-colors"
      >
        <X className="h-6 w-6" />
      </button>

      <div className="relative flex h-full w-full max-w-6xl flex-col rounded-lg bg-white shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b bg-gray-50 px-6 py-4">
          <div>
            <h2 className="text-xl font-bold text-gray-900">
              {doc.metadata.sender_name}
              {doc.metadata.recipient_name && (
                <span className="font-normal text-gray-600"> to {doc.metadata.recipient_name}</span>
              )}
            </h2>
            <div className="flex gap-3 text-sm text-gray-600 mt-1">
              <span className="rounded-full bg-gray-200 px-2 py-0.5 text-xs font-medium text-gray-700">
                {doc.metadata.event_type}
              </span>
              <span>{new Date(doc.metadata.doc_date).toLocaleDateString()}</span>
            </div>
          </div>
          
          <div className="flex gap-2">
            {!isPdf && (
              <button 
                onClick={() => setScale(scale > 1 ? 1 : 1.5)}
                className="flex items-center gap-1 rounded px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-200 transition-colors"
                title="Toggle Zoom"
              >
                <ZoomIn className="h-4 w-4" />
                {scale > 1 ? 'Reset' : 'Zoom'}
              </button>
            )}
            <a 
              href={doc.s3_original_url} 
              target="_blank" 
              rel="noopener noreferrer"
              className="flex items-center gap-1 rounded bg-red-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-red-800 transition-colors"
            >
              <Download className="h-4 w-4" />
              Download
            </a>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto bg-gray-100 p-4 flex items-center justify-center">
          {isPdf ? (
            <iframe 
              src={doc.s3_original_url} 
              className="h-full w-full rounded shadow-sm bg-white"
              title="PDF Viewer"
            />
          ) : (
            <div className={`transition-transform duration-300 ${scale > 1 ? 'cursor-zoom-out' : 'cursor-zoom-in'}`} onClick={() => setScale(scale > 1 ? 1 : 1.5)}>
              <img 
                src={doc.s3_original_url} 
                alt="Document" 
                className="max-h-[80vh] w-auto object-contain rounded shadow-md"
                style={{ transform: `scale(${scale})` }}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

