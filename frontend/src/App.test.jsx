import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App.jsx';
import ReportPanel from './components/ReportPanel.jsx';
const report = {
  id: 'check-1', document_id: 'submission-1', filename: 'baocao.docx', engine: 'lexical',
  threshold: 0.08, coverage: 100, matched_chunks: 1, total_chunks: 1, sources: [],
  document_chunks: [{ id: 'q1', text: 'Nội dung báo cáo', location: { label: 'Đoạn 1' }, alert_numbers: [1], max_score: 1 }],
  matches: [{ alert_number: 1, query_chunk_id: 'q1', source_document_id: 's1', source_filename: 'nguon.docx', source_text: 'Văn bản nguồn', score: 1, source_location: { label: 'Trang 2' } }],
  internet_search: { matches: [{ query_id: 'q1', candidate: true, web_score: 0.5, title: 'Nguồn web', link: 'javascript:alert(1)' }], queries: [] },
};
let semantic, uploads;
beforeEach(() => {
  localStorage.clear();
  semantic = false; uploads = [];
  vi.stubGlobal('fetch', vi.fn(async (url, options) => {
    let body;
    if (url === '/api/health') body = { database: 'ready', semantic_enabled: semantic, max_upload_mb: 20, thresholds: { lexical: 0.08, semantic: 0.68 } };
    else if (url === '/api/stats') body = { references: 1, reference_chunks: 2, checks: 1 };
    else if (url.includes('/api/documents?')) body = [];
    else if (url === '/api/checks' && options?.method === 'POST') { uploads.push(options.body); body = report; }
    else if (url === '/api/checks') body = [{ id: 'check-1', filename: 'lichsu.docx', engine: 'lexical', coverage: 100, created_at: '2026-11-08T00:00:00Z' }];
    else if (url === '/api/checks/check-1') body = report;
    else throw new Error('Unexpected URL: ' + url);
    return { ok: true, json: async () => body };
  }));
});
describe('React workflows', () => {
  it.each([false, true])('uses backend defaults without method/threshold controls (semantic enabled: %s)', async enabled => {
    semantic = enabled;
    const { container } = render(<App />);
    await screen.findByText('PostgreSQL đã kết nối');
    expect(screen.queryByLabelText('Phương pháp kiểm tra')).toBeNull();
    expect(screen.queryByText('NGƯỠNG CẢNH BÁO')).toBeNull();
    fireEvent.change(container.querySelector('#check-file'), { target: { files: [new File(['report'], 'baocao.docx')] } });
    fireEvent.click(screen.getByRole('button', { name: /Kiểm tra báo cáo/ }));
    await screen.findByText('Đã kiểm tra và lưu kết quả.');
    expect(uploads[0].has('engine')).toBe(false);
    expect(uploads[0].has('threshold')).toBe(false);
    expect(uploads[0].get('file').name).toBe('baocao.docx');
    expect(screen.getByTitle('Bản xem trước baocao.docx')).toHaveAttribute('src', expect.stringContaining('/api/documents/submission-1/preview'));
  });
  it('opens persisted history', async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: 'Xem kết quả' }));
    await screen.findByTitle('Bản xem trước baocao.docx');
    expect(screen.getByRole('button', { name: /Tải kết quả JSON/ })).toBeVisible();
  });
  it('shows connection errors and disables upload when offline', async () => {
    fetch.mockRejectedValue(new Error('offline')); render(<App />);
    expect(await screen.findByRole('status')).toHaveTextContent('Không liên lạc được');
    expect(screen.getByRole('button', { name: /Kiểm tra báo cáo/ })).toBeDisabled();
  });
  it('opens comparison dialogs from markers and rejects unsafe web links', async () => {
    render(<ReportPanel report={report} />);
    expect(screen.getByText('Nội dung báo cáo')).toBeVisible();
    expect(screen.queryByRole('link', { name: /Mở nguồn/ })).toBeNull();
    fireEvent.click(screen.getByLabelText('Cảnh báo 1: nguon.docx'));
    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveTextContent('Văn bản nguồn');
    expect(dialog).toHaveTextContent('Nội dung báo cáo');
    fireEvent.click(screen.getByRole('button', { name: 'Đóng đối chiếu' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Mở cảnh báo 1' }));
    expect(await screen.findByRole('dialog')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Đóng đối chiếu' }));
    fireEvent.click(screen.getByRole('button', { name: 'Bản gốc' }));
    expect(screen.getByTitle('Bản xem trước baocao.docx')).toBeVisible();
  });
  it('supports legacy reports without document_chunks', () => {
    render(<ReportPanel report={{ ...report, document_chunks: undefined, matches: [{ ...report.matches[0], query_text: 'Văn bản lịch sử cũ' }] }} />);
    fireEvent.click(screen.getByRole('button', { name: 'Văn bản đánh dấu' }));
    expect(screen.getByText('Văn bản lịch sử cũ')).toBeVisible();
  });
});

describe('Review actions', () => {
  it('excludes, persists and restores results without changing original coverage', () => {
    const view = render(<ReportPanel report={report} />);
    fireEvent.click(screen.getByRole('button', { name: 'Loại trừ kết quả 1' }));
    expect(screen.queryByLabelText('Cảnh báo 1: nguon.docx')).toBeNull();
    expect(JSON.parse(localStorage.getItem('document-review:check-1'))).toContain('internal-1');
    expect(screen.getByText('100%')).toBeVisible();
    view.unmount();
    render(<ReportPanel report={report} />);
    expect(screen.queryByLabelText('Cảnh báo 1: nguon.docx')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Đã loại trừ (1)' }));
    fireEvent.click(screen.getByRole('button', { name: 'Khôi phục kết quả 1' }));
    fireEvent.click(screen.getByRole('button', { name: 'Về kết quả' }));
    expect(screen.getByLabelText('Cảnh báo 1: nguon.docx')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Mở cảnh báo 1' })).toBeVisible();
  });
  it('bulk excludes checked sources', () => {
    render(<ReportPanel report={report} />);
    fireEvent.click(screen.getByRole('button', { name: 'Loại trừ nhiều câu' }));
    fireEvent.click(screen.getByLabelText('Chọn tất cả'));
    fireEvent.click(screen.getByRole('button', { name: 'Loại trừ (2)' }));
    expect(screen.queryByLabelText('Cảnh báo 1: nguon.docx')).toBeNull();
    expect(screen.queryByLabelText('Mở cảnh báo 1')).toBeNull();
    expect(screen.getByRole('button', { name: 'Đã loại trừ (2)' })).toBeVisible();
  });
  it('sorts by score while retaining source numbers', () => {
    render(<ReportPanel report={{ ...report, matches: [{ ...report.matches[0], score: 0.2 }] }} />);
    fireEvent.change(screen.getByLabelText('Sắp xếp kết quả'), { target: { value: 'score' } });
    const titles = document.querySelectorAll('.alert-title');
    expect(titles[0]).toHaveTextContent('Nguồn web');
    expect(titles[1]).toHaveTextContent('nguon.docx');
  });
});

it('uses the same visible STT on markers, source cards and comparison dialogs', () => {
  const { container } = render(<ReportPanel report={report} />);
  expect([...container.querySelectorAll('.document-marker')].map(item => item.textContent)).toEqual(['1', '2']);
  expect([...container.querySelectorAll('.alert-number')].map(item => item.textContent)).toEqual(['1', '2']);
  fireEvent.click(screen.getByRole('button', { name: 'Mở cảnh báo 1' }));
  expect(container.querySelector('.comparison-number')).toHaveTextContent('1');
  fireEvent.click(screen.getByRole('button', { name: 'Đóng đối chiếu' }));
  fireEvent.click(screen.getByRole('button', { name: 'Mở nguồn Internet 2' }));
  expect(container.querySelector('.comparison-number')).toHaveTextContent('2');
  fireEvent.click(screen.getByRole('button', { name: 'Đóng đối chiếu' }));
  fireEvent.change(screen.getByLabelText('Sắp xếp kết quả'), { target: { value: 'score' } });
  expect([...container.querySelectorAll('.document-marker')].map(item => item.textContent)).toEqual(['1', '2']);
});
