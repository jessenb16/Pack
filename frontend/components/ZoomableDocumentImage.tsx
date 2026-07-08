'use client';

import { useCallback, useLayoutEffect, useRef } from 'react';

export const DOCUMENT_VIEWER_ZOOM = 1.5;

const FIT_MAX_HEIGHT_VH = 70;

interface ZoomableDocumentImageProps {
  src: string;
  alt: string;
  scale: number;
  onLoad?: () => void;
  onToggleZoom?: () => void;
}

type ZoomAnchor = {
  fx: number;
  fy: number;
  clientX: number;
  clientY: number;
};

function findVerticalScrollParent(el: HTMLElement | null): HTMLElement | null {
  let node = el?.parentElement ?? null;
  while (node) {
    if (node.dataset.documentViewerScroll !== undefined) {
      return node;
    }
    const { overflowY } = getComputedStyle(node);
    if (
      (overflowY === 'auto' || overflowY === 'scroll') &&
      node.scrollHeight > node.clientHeight + 1
    ) {
      return node;
    }
    node = node.parentElement;
  }
  return null;
}

function clampScroll(el: HTMLElement) {
  const maxLeft = Math.max(0, el.scrollWidth - el.clientWidth);
  const maxTop = Math.max(0, el.scrollHeight - el.clientHeight);
  el.scrollLeft = Math.min(maxLeft, Math.max(0, el.scrollLeft));
  el.scrollTop = Math.min(maxTop, Math.max(0, el.scrollTop));
}

/**
 * Fit-to-viewport by default; zoom enlarges max bounds (not CSS transform) so
 * layout grows and adjacent pages do not overlap. Click zoom keeps the pointer
 * position anchored on the image.
 */
export default function ZoomableDocumentImage({
  src,
  alt,
  scale,
  onLoad,
  onToggleZoom,
}: ZoomableDocumentImageProps) {
  const isZoomed = scale > 1;
  const scrollRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const pendingAnchorRef = useRef<ZoomAnchor | null>(null);

  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!onToggleZoom) return;

      const img = imgRef.current;
      if (img) {
        const imgRect = img.getBoundingClientRect();
        if (imgRect.width > 0 && imgRect.height > 0) {
          const onImage =
            e.clientX >= imgRect.left &&
            e.clientX <= imgRect.right &&
            e.clientY >= imgRect.top &&
            e.clientY <= imgRect.bottom;

          if (onImage) {
            pendingAnchorRef.current = {
              fx: (e.clientX - imgRect.left) / imgRect.width,
              fy: (e.clientY - imgRect.top) / imgRect.height,
              clientX: e.clientX,
              clientY: e.clientY,
            };
          }
        }
      }

      onToggleZoom();
    },
    [onToggleZoom],
  );

  useLayoutEffect(() => {
    const anchor = pendingAnchorRef.current;
    if (!anchor) return;

    const scroll = scrollRef.current;
    const img = imgRef.current;
    if (!scroll || !img) {
      pendingAnchorRef.current = null;
      return;
    }

    const containerRect = scroll.getBoundingClientRect();
    const imgRect = img.getBoundingClientRect();

    const imgLeftInContent =
      imgRect.left - containerRect.left + scroll.scrollLeft;

    scroll.scrollLeft =
      imgLeftInContent +
      anchor.fx * imgRect.width -
      (anchor.clientX - containerRect.left);
    clampScroll(scroll);

    const verticalParent = findVerticalScrollParent(scroll);
    if (verticalParent) {
      const anchorScreenY = imgRect.top + anchor.fy * imgRect.height;
      const deltaY = anchorScreenY - anchor.clientY;
      if (Math.abs(deltaY) > 0.5) {
        verticalParent.scrollTop += deltaY;
        clampScroll(verticalParent);
      }
    }

    pendingAnchorRef.current = null;
  }, [scale]);

  return (
    <div
      ref={scrollRef}
      className={`w-full overflow-x-auto overscroll-x-contain ${
        onToggleZoom ? (isZoomed ? 'cursor-zoom-out' : 'cursor-zoom-in') : ''
      }`}
      onClick={handleClick}
    >
      <div className="flex justify-center">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          ref={imgRef}
          src={src}
          alt={alt}
          onLoad={onLoad}
          draggable={false}
          className="block h-auto w-auto rounded shadow-md object-contain"
          style={{
            maxHeight: `${FIT_MAX_HEIGHT_VH * scale}vh`,
            maxWidth: `${scale * 100}%`,
          }}
        />
      </div>
    </div>
  );
}
