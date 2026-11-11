
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import App from './App.jsx';
import InternetProgress from './components/InternetProgress.jsx';

const base = {
  id: 'internet-check', document_id: 'submission', filename: 'baocao.docx',
  engine: 'lexical', threshold: 0.08, coverage: 0, total_chunks: 6, eligible_chunks: 6, matched_chunks: 0,
  matches: [], sources: [],
  document_chunks: Array.from({ length: 6 }, (_, i) => ({ id: 'q' + i, ordinal: i, text: 'Nội dung đoạn ' + i, location: { label: 'Đoạn ' + (i + 1) }, alert_numbers: [] })),
};
function scanned(count, status = 'pending') {
  return { ...base, internet_search: {
    state_version: 1, enabled: true, total_chunks: 6, searched_chunks: count,
    skipped_chunks: 0, processed_chunks: count, pending_chunks: 6 - count,
    complete: count === 6, status: count === 6 ? 'complete' : status, batch_size: 2,
    warning: status === 'error' ? 'API hết hạn mức' : null,
    query_states: Object.fromEntries(Array.from({ length: count }, (_, i) => ['q' + i, { status: 'searched' }])),
    queries: [], matches: [],
  }};
}
const response = body => ({ ok: true, json: async () => body });
let calls;
function installFetch(batch) {
  vi.stubGlobal('fetch', vi.fn(async (url, options) => {
    if (url === '/api/health') return response({ database: 'ready', semantic_enabled: false, thresholds: { lexical: 0.08 }, max_upload_mb: 20 });
    if (url === '/api/stats') return response({ references: 1, reference_chunks: 1, checks: 1 });
    if (url.startsWith('/api/documents?')) return response([]);
    if (url === '/api/checks' && options?.method === 'POST') return response(scanned(0));
    if (url === '/api/checks') return response([{ id: base.id, filename: base.filename, engine: 'lexical', coverage: 0, created_at: '2026-11-08T00:00:00Z' }]);
    if (url === '/api/checks/internet-check') return response(scanned(0));
    if (url.endsWith('/internet/continue')) {
      calls.push(options);
      return batch(calls.length);
    }
    throw new Error('Unexpected URL ' + url);
  }));
}
beforeEach(() => { calls = []; localStorage.clear(); });

async function openAndStart() {
  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: 'Xem kết quả' }));
  const button = await screen.findByRole('button', { name: 'Kiểm tra Internet toàn báo cáo' });
  await waitFor(() => expect(button).toBeEnabled());
  expect(calls).toHaveLength(0);
  fireEvent.click(button);
}

it('automatically searches every batch after upload without confirmation', async () => {
  installFetch(index => response(scanned(index * 2)));
  const { container } = render(<App />);
  await screen.findByText('PostgreSQL đã kết nối');
  fireEvent.change(container.querySelector('#check-file'), { target: { files: [new File(['report'], 'baocao.docx')] } });
  fireEvent.click(screen.getByRole('button', { name: /Kiểm tra báo cáo/ }));
  await screen.findByText('Đã hoàn tất tìm Internet cho các đoạn đủ điều kiện.');
  expect(calls).toHaveLength(3);
  expect(calls.every(call => call.method === 'POST' && !call.body)).toBe(true);
  expect(screen.getByRole('progressbar')).toHaveAttribute('value', '6');
  expect(screen.queryByRole('checkbox', { name: /Tôi đồng ý/ })).toBeNull();
});
it('pauses after the in-flight batch without launching another', async () => {
  let finish;
  installFetch(() => new Promise(resolve => { finish = resolve; }));
  await openAndStart();
  await waitFor(() => expect(calls).toHaveLength(1));
  fireEvent.click(await screen.findByRole('button', { name: 'Tạm dừng sau đợt này' }));
  finish(response(scanned(2)));
  await screen.findByText('Đã tạm dừng. Tiến độ được lưu; bạn có thể tiếp tục sau.');
  expect(calls).toHaveLength(1);
  expect(screen.getByRole('button', { name: 'Tiếp tục kiểm tra Internet' })).toBeVisible();
  expect(screen.getByRole('progressbar')).toHaveAttribute('value', '2');
});
it('stops on quota errors instead of retrying indefinitely', async () => {
  installFetch(() => response(scanned(2, 'error')));
  await openAndStart();
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('API hết hạn mức'));
  expect(calls).toHaveLength(1);
  expect(screen.getByRole('button', { name: 'Tiếp tục kiểm tra Internet' })).toBeVisible();
});
it('distinguishes skipped paragraphs from searched paragraphs', () => {
  const report = scanned(5);
  report.internet_search = { ...report.internet_search, total_chunks: 6, skipped_chunks: 1, pending_chunks: 0, processed_chunks: 6, complete: true };
  render(<InternetProgress report={report} />);
  expect(screen.getByText(/Đã tìm 5 \/ 6 đoạn · Bỏ qua 1 đoạn quá ngắn/)).toBeVisible();
  expect(screen.queryByRole('checkbox')).toBeNull();
});
