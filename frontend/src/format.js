export const number = value => value == null ? '—' : Number(value).toLocaleString('vi-VN', { maximumFractionDigits: 2 });
export const method = engine => engine === 'semantic' ? 'Ngữ nghĩa SBERT' : 'So khớp từ vựng';
export const date = value => new Date(value).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' });
export function locationLabel(location = {}) {
  const start = [location.label, location.section].filter(Boolean).join(' · ');
  const range = location.end_label && location.end_label !== location.label ? `${start} → ${location.end_label}` : start;
  return location.extraction_method === 'ocr' ? `${range} · OCR` : range;
}
export const severity = score => score >= 0.8 ? 'high' : score >= 0.65 ? 'medium' : 'low';
export function safeWebLink(value) {
  try { const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) ? url.href : undefined; }
  catch { return undefined; }
}
