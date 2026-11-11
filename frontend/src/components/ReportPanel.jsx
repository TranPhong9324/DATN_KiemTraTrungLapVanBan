import { useEffect, useRef, useState } from 'react';
import InternetProgress from './InternetProgress.jsx';
import { locationLabel, method, number, safeWebLink, severity } from '../format.js';

export function reportChunks(report, matches) {
  if (report.document_chunks?.length) return report.document_chunks;
  const chunks = new Map();
  matches.forEach((match, index) => {
    const id = match.query_chunk_id || `old-${index}`;
    if (!chunks.has(id)) chunks.set(id, { id, ordinal: match.query_ordinal ?? index, text: match.query_text, location: match.query_location, alert_numbers: [], max_score: 0 });
    const chunk = chunks.get(id);
    chunk.alert_numbers.push(match.alert_number);
    chunk.max_score = Math.max(chunk.max_score, match.score);
  });
  return [...chunks.values()].sort((a, b) => a.ordinal - b.ordinal);
}

function resultsFor(report) {
  const internal = (report.matches || []).map((match, index) => ({
    id: `internal-${match.alert_number || index + 1}`,
    originalNumber: match.alert_number || index + 1,
    title: match.source_filename, score: match.score, type: 'internal',
    queryIds: match.query_chunk_ids || [match.query_chunk_id || `old-${index}`],
    ordinal: match.query_ordinal ?? index, text: match.source_text || '',
    queryText: match.query_text || '', location: match.source_location,
    href: `/api/documents/${encodeURIComponent(match.source_document_id)}/file`,
    detail: locationLabel(match.source_location) || 'Kho tài liệu nội bộ',
    label: match.alert_label || report.alert_label || method(report.engine),
  }));
  const web = (report.internet_search?.matches || []).map((item, index) => ({
    id: `web-${index + 1}`, title: item.title || 'Nguồn Internet',
    score: item.web_score || 0, type: 'web', queryIds: [item.query_id],
    ordinal: item.query_ordinal ?? index, text: item.snippet || '',
    queryText: item.query_text || '', href: safeWebLink(item.link),
    detail: webDomain(item.link), label: 'Đối chiếu tiêu đề và mô tả tìm kiếm',
    candidate: item.candidate,
  }));
  return [...internal, ...web].sort((a, b) => a.ordinal - b.ordinal || (a.type === b.type ? 0 : a.type === 'internal' ? -1 : 1))
    .map((item, index) => ({ ...item, number: index + 1 }));
}

function webDomain(href) {
  try { return new URL(safeWebLink(href)).hostname.replace(/^www\./, ''); }
  catch { return 'Nguồn Internet'; }
}

function readExclusions(key) {
  try {
    const stored = JSON.parse(localStorage.getItem(key) || '[]');
    return new Set(Array.isArray(stored) ? stored.filter(id => typeof id === 'string') : []);
  } catch { return new Set(); }
}

function exportReport(report, excluded) {
  const reviewed = { ...report, review: { excluded_result_ids: [...excluded], scope: 'browser-local', original_report_unchanged: true } };
  const url = URL.createObjectURL(new Blob([JSON.stringify(reviewed, null, 2)], { type: 'application/json;charset=utf-8' }));
  const anchor = document.createElement('a');
  anchor.href = url; anchor.download = `ket-qua-${report.id}.json`; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const levelLabel = score => severity(score) === 'high' ? 'TRÙNG LẶP CAO' : severity(score) === 'medium' ? 'TRÙNG LẶP TRUNG BÌNH' : 'TRÙNG LẶP THẤP';
const wordKey = text => text.toLocaleLowerCase('vi').replace(/[^\p{L}\p{N}]/gu, '');
function ComparedText({ text, comparison }) {
  const shared = new Set((comparison || '').split(/\s+/).map(wordKey).filter(word => word.length > 2));
  return (text || '').split(/(\s+)/).map((part, index) => shared.has(wordKey(part)) ? <strong key={index}>{part}</strong> : part);
}

function ComparisonDialog({ result, queryText, excluded, onExclude, onClose }) {
  const dialog = useRef(null);
  useEffect(() => {
    const element = dialog.current;
    if (element.showModal) element.showModal();
    else element.setAttribute('open', '');
    return () => { if (element.open) element.close?.(); };
  }, []);
  return <dialog ref={dialog} className="comparison-dialog" aria-labelledby="comparison-title" onCancel={event => { event.preventDefault(); onClose(); }} onClose={onClose}>
    <header className="comparison-heading">
      <span className="comparison-number">{result.number}</span>
      <div><p>{levelLabel(result.score)} - {number(result.score * 100)}%</p><h3 id="comparison-title">{result.title}</h3></div>
      <button className="dialog-close" aria-label="Đóng đối chiếu" onClick={onClose} autoFocus>×</button>
    </header>
    <div className="comparison-content">
      <p className="comparison-caption">NỘI DUNG TRONG BÁO CÁO</p>
      <p className="comparison-query"><ComparedText text={queryText} comparison={result.text} /></p>
      <div className="comparison-source-heading"><span className="comparison-caption">NỘI DUNG NGUỒN ĐỐI CHIẾU</span>{result.href && <a href={result.href} target="_blank" rel="noopener noreferrer">Mở nguồn ↗</a>}</div>
      <p className="comparison-source"><ComparedText text={result.text || 'Nguồn này chưa có đoạn trích để hiển thị.'} comparison={queryText} /></p>
      <p className="comparison-location">{result.detail} · {result.label}</p>
      {result.type === 'web' && <p className="field-note">Đoạn trích từ kết quả tìm kiếm; cần mở nguồn để kiểm tra toàn văn.</p>}
    </div>
    <footer className="comparison-actions"><button onClick={() => onExclude(result.id)}>{excluded ? 'Khôi phục kết quả' : 'Loại trừ kết quả'}</button><button onClick={onClose}>Đóng</button></footer>
  </dialog>;
}

function Review({ report }) {
  const [mode, setMode] = useState('marked');
  const [selection, setSelection] = useState(null);
  const [dialogResult, setDialogResult] = useState(null);
  const [sort, setSort] = useState('appearance');
  const [bulk, setBulk] = useState(false);
  const [checked, setChecked] = useState(new Set());
  const [showExcluded, setShowExcluded] = useState(false);
  const storageKey = `document-review:${report.id || report.document_id}`;
  const [excluded, setExcluded] = useState(() => readExclusions(storageKey));
  const blocks = useRef(new Map());
  const cards = useRef(new Map());
  const results = resultsFor(report);
  const matches = (report.matches || []).map((item, index) => ({ ...item, alert_number: item.alert_number || index + 1 }));
  const chunks = reportChunks(report, matches);
  const activeResults = results.filter(item => !excluded.has(item.id));
  const excludedCount = results.length - activeResults.length;
  const visible = results.filter(item => showExcluded ? excluded.has(item.id) : !excluded.has(item.id))
    .sort((a, b) => sort === 'score' ? b.score - a.score || a.number - b.number : a.number - b.number);
  const currentResult = results.find(item => item.id === dialogResult);
  const queryFor = result => chunks.filter(chunk => result.queryIds.includes(chunk.id)).map(chunk => chunk.text).join('\n') || result.queryText;
  useEffect(() => {
    if (!selection) return;
    const target = selection.direction === 'card' ? cards.current.get(selection.id) : blocks.current.get(selection.queryId);
    target?.scrollIntoView?.({ behavior: 'smooth', block: 'center' });
  }, [selection, mode]);
  function persist(next) {
    setExcluded(next);
    try { localStorage.setItem(storageKey, JSON.stringify([...next])); } catch { /* Review still works when storage is unavailable. */ }
  }
  function toggleExclusion(id) {
    const next = new Set(excluded);
    if (next.has(id)) next.delete(id); else next.add(id);
    persist(next); setDialogResult(null); setSelection(null);
  }
  function excludeChecked() {
    persist(new Set([...excluded, ...checked]));
    setChecked(new Set()); setBulk(false); setDialogResult(null);
  }
  function focusResult(result, direction = 'document') {
    setMode('marked');
    setSelection({ id: result.id, queryId: result.queryIds[0], direction });
    if (!bulk) setDialogResult(result.id);
  }
  const setRef = (map, id) => element => { if (element) map.current.set(id, element); else map.current.delete(id); };
  return <div id="result">
    <div className="review-summary">
      <div><span className="review-percent">{number(report.coverage)}{report.coverage == null ? '' : '%'}</span><strong>Nội dung được cảnh báo <small>Kết quả gốc</small></strong></div>
      <div><strong>{number(report.matched_chunks)} / {number(report.eligible_chunks ?? report.total_chunks)} đoạn</strong><span>{report.alert_label || method(report.engine)}</span></div>
      <div><strong>{number(activeResults.length)} kết quả đang xem · {number(excludedCount)} đã loại trừ</strong><span>Đọc nội dung đối chiếu trước khi kết luận.</span></div>
    </div>
    {(report.warnings || []).map((warning, index) => <p className="warning" key={index}>{warning}</p>)}
    <div className="review-layout">
      <section className="document-view">
        <header className="review-toolbar"><div><span className="toolbar-kicker">BÁO CÁO ĐANG THẨM ĐỊNH</span><h3>{report.filename}</h3></div><div className="preview-switch" role="group" aria-label="Kiểu xem văn bản">{[['original', 'Bản gốc'], ['marked', 'Văn bản đánh dấu']].map(([value, label]) => <button key={value} className={`preview-toggle ${mode === value ? 'is-active' : ''}`} aria-pressed={mode === value} onClick={() => setMode(value)}>{label}</button>)}</div></header>
        <iframe className="document-preview" title={`Bản xem trước ${report.filename}`} hidden={mode !== 'original'} src={`/api/documents/${encodeURIComponent(report.document_id)}/preview#toolbar=0&navpanes=0`} />
        <div className="document-paper" hidden={mode !== 'marked'}>
          {chunks.length ? chunks.map(chunk => {
            const related = activeResults.filter(item => item.queryIds.includes(chunk.id) && (item.type === 'internal' || item.candidate));
            const score = Math.max(0, ...related.map(item => item.score));
            const active = related.some(item => selection?.id === item.id);
            return <section key={chunk.id} ref={setRef(blocks, chunk.id)} className={`document-block ${chunk.ignored ? 'is-ignored' : ''} ${active ? 'is-active' : ''}`}>
              <div className="document-location">{locationLabel(chunk.location)}{chunk.ignored ? ' · Đã loại khỏi đối chiếu' : ''}</div>
              {report.internet_search?.query_states && !chunk.ignored && <div className="chunk-web-status">Internet: {({
                searched: 'Đã tìm', skipped: 'Bỏ qua — đoạn quá ngắn', error: 'Bị gián đoạn — cần thử lại',
              })[report.internet_search.query_states[chunk.id]?.status] || 'Chưa kiểm tra'}</div>}
              <div className="document-text">
                {related.length > 0 && <span className="document-markers">{related.map(item => <button key={item.id} className="document-marker" aria-label={item.type === 'internal' ? `Mở cảnh báo ${item.originalNumber}` : `Mở nguồn Internet ${item.number}`} onClick={() => focusResult(item, 'card')}>{item.number}</button>)}</span>}
                {related.length ? <button className={`document-highlight severity-${severity(score)}`} aria-label={`Xem đối chiếu đoạn ${chunk.ordinal ?? chunk.id}`} onClick={() => focusResult(related[0], 'card')}>{chunk.text}</button> : <span>{chunk.text}</span>}
              </div>
            </section>;
          }) : <p className="empty">Không có nội dung văn bản trong báo cáo cũ.</p>}
        </div>
        <div className="document-status"><span>{chunks.length} đoạn · {new Set(chunks.map(chunk => chunk.location?.page).filter(Boolean)).size || '—'} trang có văn bản</span><span>{report.filename}</span></div>
      </section>
      <aside className="alerts-view" aria-label="Danh sách nguồn đối chiếu">
        <div className="review-tools">
          <label className="sort-control"><span aria-hidden="true">⇅</span><select aria-label="Sắp xếp kết quả" value={sort} onChange={event => setSort(event.target.value)}><option value="appearance">Thứ tự xuất hiện</option><option value="score">Điểm tương đồng cao nhất</option></select></label>
          <button className={`text-action ${bulk ? 'is-active' : ''}`} onClick={() => { setBulk(!bulk); setChecked(new Set()); }}>{bulk ? 'Hủy chọn' : 'Loại trừ nhiều câu'}</button>
        </div>
        <div className="review-list-status"><span>{visible.length} kết quả {showExcluded ? 'đã loại trừ' : 'đối chiếu'}</span>{(excludedCount > 0 || showExcluded) && <button className="text-action" onClick={() => { setShowExcluded(!showExcluded); setBulk(false); setChecked(new Set()); }}>{showExcluded ? 'Về kết quả' : `Đã loại trừ (${excludedCount})`}</button>}</div>
        {bulk && <div className="bulk-actions"><label><input type="checkbox" checked={visible.length > 0 && checked.size === visible.length} onChange={event => setChecked(new Set(event.target.checked ? visible.map(item => item.id) : []))} /> Chọn tất cả</label><button disabled={!checked.size || showExcluded} onClick={excludeChecked}>Loại trừ ({checked.size})</button></div>}
        <div className="alerts-list">
          {visible.map(item => <article key={item.id} ref={setRef(cards, item.id)} className={`alert-card severity-${severity(item.score)} ${selection?.id === item.id ? 'is-active' : ''} ${excluded.has(item.id) ? 'is-excluded' : ''}`}>
            <div className="alert-card-top">{bulk && <input type="checkbox" aria-label={`Chọn kết quả ${item.number}`} checked={checked.has(item.id)} onChange={event => { const next = new Set(checked); if (event.target.checked) next.add(item.id); else next.delete(item.id); setChecked(next); }} />}<span className="severity-dot" aria-hidden="true" /><span className="alert-number">{item.number}</span><span>{levelLabel(item.score)} - {number(item.score * 100)}%</span></div>
            <button className="alert-title" aria-label={item.type === 'internal' ? `Cảnh báo ${item.originalNumber}: ${item.title}` : `Nguồn Internet ${item.number}: ${item.title}`} onClick={() => focusResult(item)}>{item.title}</button>
            <div className="alert-domain">{item.href ? <a href={item.href} target="_blank" rel="noopener noreferrer">{item.detail}<span aria-hidden="true"> ↗</span></a> : <span>{item.detail}</span>}</div>
            <div className="alert-card-actions"><button className="icon-action" aria-label={`Chi tiết kết quả ${item.number}`} onClick={() => focusResult(item)}>ⓘ</button><span>{item.type === 'internal' ? 'Nguồn nội bộ' : 'Nguồn Internet · Đoạn trích'}</span><button className="icon-action" aria-label={`${excluded.has(item.id) ? 'Khôi phục' : 'Loại trừ'} kết quả ${item.number}`} title={excluded.has(item.id) ? 'Khôi phục kết quả' : 'Loại trừ kết quả'} onClick={() => toggleExclusion(item.id)}>{excluded.has(item.id) ? '↶' : <svg viewBox="0 0 24 24" width="21" height="21" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7M14 10v7" /></svg>}</button></div>
          </article>)}
          {!visible.length && <div className="result-empty"><h3>{showExcluded ? 'Chưa có kết quả bị loại trừ' : 'Không có kết quả cần hiển thị'}</h3><p>{excludedCount ? 'Bạn có thể khôi phục kết quả đã loại trừ.' : 'Không tìm thấy đoạn vượt ngưỡng trong kho nội bộ.'}</p></div>}
          {report.internet_search?.warning && <p className="field-note">{report.internet_search.warning}</p>}
        </div>
        <p className="review-storage-note">Loại trừ được lưu trên trình duyệt này, kèm trong JSON khi tải xuống. Điểm tổng của báo cáo gốc giữ nguyên.</p>
      </aside>
    </div>
    <div className="review-bottom-bar"><span><i className="legend low" /> Thấp <i className="legend medium" /> Trung bình <i className="legend high" /> Cao</span><button className="text-action" onClick={() => exportReport(report, excluded)}>↓ Tải kết quả thẩm định</button></div>
    {currentResult && <ComparisonDialog result={currentResult} queryText={queryFor(currentResult)} excluded={excluded.has(currentResult.id)} onExclude={toggleExclusion} onClose={() => setDialogResult(null)} />}
  </div>;
}

export default function ReportPanel({ report, sectionRef, busy = false, internetRunning = false, internetStopping = false, onContinueInternet, onStopInternet }) {
  return <section ref={sectionRef} className="panel result-panel" aria-labelledby="result-title">
    <div className="result-heading"><div className="section-title"><span className="step">03</span><div><h2 id="result-title">Kết quả đối chiếu</h2><p>{report?.filename || 'Các đoạn nghi vấn và nguồn tham chiếu sẽ xuất hiện tại đây.'}</p></div></div>{report && <button className="button secondary" onClick={() => exportReport(report, readExclusions(`document-review:${report.id || report.document_id}`))}>↓ Tải kết quả JSON</button>}</div>
    {report && <InternetProgress key={report.id} report={report} busy={busy} running={internetRunning} stopping={internetStopping} onContinue={onContinueInternet} onStop={onStopInternet} />}
    {report ? <Review key={report.id || report.document_id} report={report} /> : <div className="result-empty"><span aria-hidden="true">≍</span><h3>Sẵn sàng cho báo cáo đầu tiên</h3><p>Thêm tài liệu nguồn, sau đó tải báo cáo cần kiểm tra.</p></div>}
  </section>;
}
