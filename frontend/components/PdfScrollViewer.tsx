'use client';

import { useEffect, useRef, useState } from 'react';
import ZoomableDocumentImage from '@/components/ZoomableDocumentImage';

type PdfPageImage = {
  pageNumber: number;
  src: string;
};

interface PdfScrollViewerProps {
  /** Authenticated API URL that streams the PDF (avoids S3 CORS). */
  contentUrl: string;
  /** Presigned URL for download / open-in-new-tab fallback. */
  downloadUrl: string;
  getAuthToken?: () => Promise<string | null>;
  scale?: number;
  onLoaded?: () => void;
  onError?: (message: string) => void;
  onToggleZoom?: () => void;
}

export default function PdfScrollViewer({
  contentUrl,
  downloadUrl,
  getAuthToken,
  scale = 1,
  onLoaded,
  onError,
  onToggleZoom,
}: PdfScrollViewerProps) {
  const [pages, setPages] = useState<PdfPageImage[]>([]);
  const [totalPages, setTotalPages] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const cancelledRef = useRef(false);
  const loadingTaskRef = useRef<{ destroy: () => Promise<void> } | null>(null);
  const onLoadedRef = useRef(onLoaded);
  const onErrorRef = useRef(onError);
  const getAuthTokenRef = useRef(getAuthToken);

  onLoadedRef.current = onLoaded;
  onErrorRef.current = onError;
  getAuthTokenRef.current = getAuthToken;

  useEffect(() => {
    cancelledRef.current = false;
    setPages([]);
    setTotalPages(0);
    setError(null);

    async function load() {
      try {
        const pdfjs = await import('pdfjs-dist/webpack.mjs');
        const token = getAuthTokenRef.current
          ? await getAuthTokenRef.current()
          : null;
        const httpHeaders: Record<string, string> = {};
        if (token) {
          httpHeaders.Authorization = `Bearer ${token}`;
        }

        const loadingTask = pdfjs.getDocument({
          url: contentUrl,
          httpHeaders,
          withCredentials: false,
        });
        loadingTaskRef.current = loadingTask;
        const pdf = await loadingTask.promise;

        if (cancelledRef.current) {
          void loadingTask.destroy();
          return;
        }

        const numPages = pdf.numPages;
        setTotalPages(numPages);

        const containerWidth = containerRef.current?.clientWidth ?? 800;
        const maxWidth = Math.min(containerWidth - 32, 896);

        const rendered: PdfPageImage[] = [];
        let firstPageNotified = false;

        for (let pageNum = 1; pageNum <= numPages; pageNum++) {
          if (cancelledRef.current) break;

          const page = await pdf.getPage(pageNum);
          const baseViewport = page.getViewport({ scale: 1 });
          const fitScale = Math.min(maxWidth / baseViewport.width, 2);
          const viewport = page.getViewport({ scale: fitScale });

          const canvas = document.createElement('canvas');
          const context = canvas.getContext('2d');
          if (!context) {
            throw new Error('Canvas not supported');
          }

          canvas.width = viewport.width;
          canvas.height = viewport.height;

          await page.render({ canvasContext: context, viewport, canvas }).promise;

          rendered.push({
            pageNumber: pageNum,
            src: canvas.toDataURL('image/jpeg', 0.92),
          });

          if (!cancelledRef.current) {
            setPages([...rendered]);
          }

          if (!firstPageNotified) {
            firstPageNotified = true;
            onLoadedRef.current?.();
          }
        }
      } catch (err) {
        if (cancelledRef.current) return;
        const message =
          err instanceof Error ? err.message : 'Failed to load PDF';
        setError(message);
        onErrorRef.current?.(message);
      }
    }

    void load();

    return () => {
      cancelledRef.current = true;
      void loadingTaskRef.current?.destroy();
      loadingTaskRef.current = null;
    };
  }, [contentUrl]);

  if (error) {
    return (
      <div className="flex min-h-[40vh] flex-col items-center justify-center gap-3 p-6 text-center">
        <p className="text-sm font-medium text-red-600">Could not load PDF</p>
        <p className="text-xs text-gray-500">{error}</p>
        <a
          href={downloadUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm font-medium text-blue-600 hover:underline"
        >
          Open PDF in new tab
        </a>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="flex w-full flex-col items-center gap-10 py-2">
      {pages.map((page) => (
        <div key={page.pageNumber} className="w-full max-w-4xl">
          <p className="mb-2 text-center text-sm font-medium text-gray-600">
            Page {page.pageNumber} of {totalPages || pages.length}
          </p>
          <div className="flex justify-center">
            <ZoomableDocumentImage
              src={page.src}
              alt={`Page ${page.pageNumber}`}
              scale={scale}
              onToggleZoom={onToggleZoom}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
