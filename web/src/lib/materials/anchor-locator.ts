import type {DocumentAnchor} from '@/lib/api/types';

export function formatAnchorLocator(anchor: DocumentAnchor): string {
  if (anchor.sheet_name || anchor.cell_range) {
    const parts = [
      anchor.sheet_name ? `Sheet: ${anchor.sheet_name}` : null,
      anchor.cell_range ? `Cell: ${anchor.cell_range}` : null,
    ].filter(Boolean);
    return parts.join(' · ');
  }

  if (anchor.page_start != null) {
    if (
      anchor.page_end != null &&
      anchor.page_end !== anchor.page_start
    ) {
      return `Pages ${anchor.page_start}–${anchor.page_end}`;
    }
    return `Page ${anchor.page_start}`;
  }

  if (anchor.slide_number != null) {
    return `Slide ${anchor.slide_number}`;
  }

  if (anchor.heading_path?.length) {
    return anchor.heading_path.join(' › ');
  }

  if (anchor.paragraph_start != null) {
    if (
      anchor.paragraph_end != null &&
      anchor.paragraph_end !== anchor.paragraph_start
    ) {
      return `Paragraphs ${anchor.paragraph_start}–${anchor.paragraph_end}`;
    }
    return `Paragraph ${anchor.paragraph_start}`;
  }

  return anchor.anchor_type.replaceAll('_', ' ');
}

export function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
