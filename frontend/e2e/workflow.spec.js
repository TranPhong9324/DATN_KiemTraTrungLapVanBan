import { test, expect } from '@playwright/test';
const report = {
  id: 'browser-check', document_id: 'browser-document', filename: 'baocao.docx',
  engine: 'lexical', threshold: 0.08, coverage: 100, eligible_chunks: 1, matched_chunks: 1,
  document_chunks: [{ id: 'q1', text: 'Đây là nội dung báo cáo được đánh dấu.', alert_numbers: [1], max_score: 1, location: { label: 'Đoạn 1' } }],
  sources: [{ document_id: 's1', filename: 'nguon.docx', rank: 1, coverage: 100 }],
  matches: [{ alert_number: 1, query_chunk_id: 'q1', source_document_id: 's1', source_filename: 'nguon.docx', source_text: 'Nội dung nguồn đối chiếu.', score: 1, source_location: { label: 'Trang 1' } }],
};

test('production React renders Vietnamese, uploads, navigates alerts and exports history', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  let posted = false;
  await page.route('**/api/**', async route => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname.endsWith('/preview')) return route.fulfill({ contentType: 'text/html', body: '<p>Document preview</p>' });
    let body;
    if (url.pathname === '/api/health') body = { database: 'ready', max_upload_mb: 20, semantic_enabled: false, thresholds: { lexical: 0.08, semantic: 0.68 } };
    else if (url.pathname === '/api/stats') body = { references: 1, reference_chunks: 1, checks: 1 };
    else if (url.pathname === '/api/documents') body = [{ id: 's1', filename: 'nguon.docx', file_type: 'docx', chunks: 1, size_bytes: 100, warnings: [] }];
    else if (url.pathname === '/api/checks' && request.method() === 'POST') {
      expect(request.postDataBuffer().toString()).not.toContain('name="engine"');
      expect(request.postDataBuffer().toString()).not.toContain('name="threshold"');
      expect(request.postDataBuffer().toString()).toContain('baocao.docx');
      posted = true; body = report;
    } else if (url.pathname === '/api/checks') body = [{ id: report.id, filename: report.filename, engine: 'lexical', coverage: 100, created_at: '2026-11-08T00:00:00Z' }];
    else if (url.pathname === '/api/checks/browser-check') body = report;
    else throw new Error('Unexpected API request: ' + url.pathname);
    await route.fulfill({ json: body });
  });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Báo cáo cần kiểm tra', level: 1 })).toBeVisible();
  await expect(page.getByText('PostgreSQL đã kết nối')).toBeVisible();
  await expect(page.getByLabel('Phương pháp kiểm tra')).toHaveCount(0);
  await page.locator('#check-file').setInputFiles({ name: 'baocao.docx', mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', buffer: Buffer.from('synthetic browser test') });
  await page.getByRole('button', { name: /Kiểm tra báo cáo/ }).click();
  await expect(page.getByText('Đã kiểm tra và lưu kết quả.')).toBeVisible();
  expect(posted).toBe(true);
  await page.getByLabel('Cảnh báo 1: nguon.docx').click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByRole('dialog')).toContainText('Nội dung nguồn đối chiếu.');
  await page.screenshot({ path: 'test-results/review-dialog-desktop.png' });
  await page.getByRole('button', { name: 'Đóng đối chiếu' }).click();
  await page.getByRole('button', { name: 'Mở cảnh báo 1' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toBeHidden();
  await page.getByRole('button', { name: 'Bản gốc' }).click();
  await expect(page.getByTitle('Bản xem trước baocao.docx')).toBeVisible();
  const downloadPromise = page.waitForEvent('download');
  await expect(page.getByRole('button', { name: /Tải kết quả JSON/ })).toHaveCount(0);
  await page.getByRole('button', { name: /Tải kết quả thẩm định/ }).click();
  expect((await downloadPromise).suggestedFilename()).toBe('ket-qua-browser-check.json');
  await page.getByRole('link', { name: 'Kho tham chiếu', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Kho tham chiếu', level: 1 })).toBeVisible();
  await expect(page.getByLabel('Chọn tài liệu nguồn')).toBeVisible();
  await expect(page.getByRole('button', { name: /Kiểm tra báo cáo/ })).toBeHidden();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Kho tham chiếu', level: 1 })).toBeVisible();
  await page.getByRole('link', { name: 'Lịch sử kiểm tra', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Lịch sử kiểm tra', level: 1 })).toBeVisible();
  await page.getByRole('button', { name: 'Xem kết quả' }).click();
  await expect(page.getByRole('link', { name: 'Báo cáo cần kiểm tra', exact: true })).toHaveAttribute('aria-current', 'page');
  await page.getByRole('button', { name: 'Bản gốc' }).click();
  await expect(page.getByTitle('Bản xem trước baocao.docx')).toBeVisible();
  await page.getByRole('button', { name: 'Văn bản đánh dấu' }).click();
  await page.getByRole('button', { name: 'Loại trừ kết quả 1', exact: true }).click();
  await expect(page.getByLabel('Cảnh báo 1: nguon.docx')).toHaveCount(0);
  await page.getByRole('button', { name: 'Đã loại trừ (1)' }).click();
  await page.getByRole('button', { name: 'Khôi phục kết quả 1' }).click();
  await page.getByRole('button', { name: 'Về kết quả' }).click();
  await page.screenshot({ path: 'test-results/react-desktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('heading', { name: 'Báo cáo cần kiểm tra', level: 1 }).scrollIntoViewIfNeeded();
  await expect(page.getByRole('heading', { name: 'Báo cáo cần kiểm tra', level: 1 })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: 'test-results/react-mobile.png', fullPage: true });
  await page.getByLabel('Cảnh báo 1: nguon.docx').click();
  const mobileDialog = page.getByRole('dialog');
  await expect(mobileDialog).toBeVisible();
  const bounds = await mobileDialog.boundingBox();
  expect(bounds.x).toBeGreaterThanOrEqual(0);
  expect(bounds.x + bounds.width).toBeLessThanOrEqual(390);
  await page.screenshot({ path: 'test-results/review-dialog-mobile.png' });
  await page.keyboard.press('Escape');
  await expect(mobileDialog).toBeHidden();
  expect(errors).toEqual([]);
});

test('Internet search starts automatically after upload, pauses and resumes to the end', async ({ page }) => {
  let calls = 0, releaseSecond;
  const total = 6;
  const snapshot = count => ({
    ...report, id: 'batch-report', total_chunks: total, eligible_chunks: total, matched_chunks: 0, coverage: 0, matches: [], sources: [],
    document_chunks: Array.from({ length: total }, (_, index) => ({ id: 'q' + index, ordinal: index, text: 'Nội dung đoạn báo cáo ' + index, location: { label: 'Đoạn ' + (index + 1) }, alert_numbers: [] })),
    internet_search: { state_version: 1, enabled: true, total_chunks: total, searched_chunks: count, skipped_chunks: 0, processed_chunks: count, pending_chunks: total - count, complete: count === total, status: count === total ? 'complete' : 'pending', batch_size: 2, warning: null, queries: [], matches: [], query_states: Object.fromEntries(Array.from({ length: count }, (_, index) => ['q' + index, { status: 'searched' }])) },
  });
  await page.route('**/api/**', async route => {
    const request = route.request(), pathname = new URL(request.url()).pathname;
    if (pathname.endsWith('/preview')) return route.fulfill({ contentType: 'text/html', body: '<p>Preview</p>' });
    let body;
    if (pathname === '/api/health') body = { database: 'ready', semantic_enabled: false, thresholds: { lexical: 0.08 }, max_upload_mb: 20 };
    else if (pathname === '/api/stats') body = { references: 1, reference_chunks: 1, checks: 1 };
    else if (pathname === '/api/documents') body = [];
    else if (pathname === '/api/checks' && request.method() === 'POST') body = snapshot(0);
    else if (pathname === '/api/checks') body = [{ id: 'batch-report', filename: 'baocao.docx', engine: 'lexical', coverage: 0, created_at: '2026-11-08T00:00:00Z' }];
    else if (pathname === '/api/checks/batch-report') body = snapshot(0);
    else if (pathname.endsWith('/internet/continue')) {
      expect(request.postData()).toBeFalsy();
      calls++;
      if (calls === 2) await new Promise(resolve => { releaseSecond = resolve; });
      body = snapshot(calls * 2);
    } else throw new Error('Unexpected URL ' + pathname);
    await route.fulfill({ json: body });
  });
  await page.goto('/');
  await expect(page.getByText('PostgreSQL đã kết nối')).toBeVisible();
  expect(calls).toBe(0);
  await page.locator('#check-file').setInputFiles({ name: 'baocao.docx', mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', buffer: Buffer.from('synthetic automatic Internet test') });
  await page.getByRole('button', { name: /Kiểm tra báo cáo/ }).click();
  await expect.poll(() => calls).toBe(2);
  await page.getByRole('button', { name: 'Tạm dừng sau đợt này' }).click();
  releaseSecond();
  await expect(page.getByRole('status')).toContainText('Đã tạm dừng');
  expect(calls).toBe(2);
  await expect(page.getByRole('progressbar')).toHaveAttribute('value', '4');
  await page.locator('.internet-progress').screenshot({ path: 'test-results/internet-progress-paused.png' });
  await page.getByRole('button', { name: 'Tiếp tục kiểm tra Internet' }).click();
  await expect(page.getByRole('status')).toContainText('Đã hoàn tất tìm Internet');
  expect(calls).toBe(3);
  await expect(page.getByRole('progressbar')).toHaveAttribute('value', '6');
  await expect(page.getByText('Internet: Chưa kiểm tra', { exact: true })).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
