import { useCallback, useEffect, useRef, useState } from 'react';
import { api, validateSelection } from './api.js';
import { number } from './format.js';
import UploadPanel from './components/UploadPanel.jsx';
import ReferencePanel from './components/ReferencePanel.jsx';
import ReportPanel from './components/ReportPanel.jsx';
import HistoryPanel from './components/HistoryPanel.jsx';

const pages = {
  check: { title: 'Báo cáo cần kiểm tra', description: 'Tải báo cáo và đối chiếu với kho nội bộ cùng các nguồn Internet.' },
  history: { title: 'Lịch sử kiểm tra', description: 'Xem lại các báo cáo và kết quả đối chiếu đã lưu.' },
  references: { title: 'Kho tham chiếu', description: 'Quản lý tài liệu nguồn dùng để đối chiếu báo cáo.' },
};
const currentPage = () => Object.hasOwn(pages, window.location.hash.slice(1)) ? window.location.hash.slice(1) : 'check';

export default function App() {
  const [page, setPage] = useState(currentPage);
  useEffect(() => {
    const update = () => setPage(currentPage());
    window.addEventListener('hashchange', update);
    return () => window.removeEventListener('hashchange', update);
  }, []);
  function navigate(next) {
    setPage(next);
    window.location.hash = next;
  }
  const [health, setHealth] = useState(null);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);
  const [stats, setStats] = useState({});
  const [references, setReferences] = useState([]);
  const [checks, setChecks] = useState([]);
  const [report, setReport] = useState(null);
  const resultSection = useRef(null);
  const working = useRef(false);
  const internetRun = useRef(null);
  const [internetRunning, setInternetRunning] = useState(false);
  const [internetStopping, setInternetStopping] = useState(false);
  useEffect(() => () => {
    if (internetRun.current) { internetRun.current.stopped = true; internetRun.current.disposed = true; }
  }, []);
  const notify = (message, error = false) => setNotice({ message, error });
  const refresh = useCallback(async () => {
    try {
      const status = await api('/api/health');
      setHealth(status);
      if (status.database !== 'ready') { setReady(false); setStats({}); setReferences([]); setChecks([]); return; }
      const [newStats, documents, history] = await Promise.all([api('/api/stats'), api('/api/documents?role=reference'), api('/api/checks')]);
      setStats(newStats); setReferences(documents); setChecks(history); setReady(true);
    } catch (error) { setReady(false); notify(error.message, true); }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => { if (report && page === 'check') resultSection.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' }); }, [report?.id, page]);
  async function upload(file, role) {
    if (working.current) return false;
    try {
      validateSelection(file, health?.max_upload_mb ?? 20);
      working.current = true; setBusy(true);
      notify(role === 'reference' ? 'Đang trích xuất tài liệu và lưu vào kho tham chiếu…' : 'Đang trích xuất và đối chiếu báo cáo…');
      const body = new FormData(); body.append('file', file);
      const result = await api(role === 'reference' ? '/api/references' : '/api/checks', { method: 'POST', body });
      if (role === 'submission') { setReport(result); navigate('check'); }
      notify(role === 'reference' ? `Đã thêm ${result.filename}: ${result.chunks} đoạn. ${(result.warnings || []).join(' ')}` : 'Đã kiểm tra và lưu kết quả.');
      if (role === 'submission' && result.reference_archive) {
        const archiveMessage = {
          added: 'Báo cáo đã được thêm vào kho tham chiếu.',
          existing: 'Báo cáo đã có trong kho tham chiếu, không tạo bản trùng.',
          capacity_reached: 'Kho tham chiếu đã đầy, báo cáo chưa được thêm vào kho.',
        }[result.reference_archive.status];
        notify(`Đã kiểm tra và lưu kết quả. ${archiveMessage || ''}`);
      }
      await refresh();
      if (role === 'submission' && result.internet_search?.enabled && !result.internet_search.complete) {
        await continueInternet(result, true);
      }
      return true;
    } catch (error) { notify(error.message, true); return false; }
    finally { working.current = false; setBusy(false); }
  }
  async function openReport(id) {
    if (working.current) return;
    working.current = true; setBusy(true);
    try { setReport(await api(`/api/checks/${encodeURIComponent(id)}`)); navigate('check'); }
    catch (error) { notify(error.message, true); }
    finally { working.current = false; setBusy(false); }
  }
  async function continueInternet(initial, fromUpload = false) {
    if (working.current && !fromUpload) return;
    working.current = true; setBusy(true);
    const token = { stopped: false, disposed: false };
    internetRun.current = token; setInternetRunning(true); setInternetStopping(false);
    let current = initial;
    try {
      while (!token.stopped && current.internet_search?.enabled && !current.internet_search.complete) {
        const before = current.internet_search.pending_chunks;
        const next = await api('/api/checks/' + encodeURIComponent(initial.id) + '/internet/continue', {
          method: 'POST',
        });
        current = next;
        if (token.disposed) break;
        setReport(next);
        const state = next.internet_search;
        notify('Internet: đã tìm ' + state.searched_chunks + '/' + state.total_chunks + ' đoạn; còn ' + state.pending_chunks + ' đoạn.');
        if (state.status === 'error') { notify(state.warning || 'Tìm Internet bị gián đoạn. Có thể tiếp tục sau.', true); break; }
        if (!state.complete && state.pending_chunks >= before) { notify('Tiến độ chưa thay đổi. Hãy thử tiếp tục sau.', true); break; }
      }
      if (!token.disposed && current.internet_search?.complete) notify('Đã hoàn tất tìm Internet cho các đoạn đủ điều kiện.');
      else if (!token.disposed && token.stopped) notify('Đã tạm dừng. Tiến độ được lưu; bạn có thể tiếp tục sau.');
    } catch (error) {
      if (!token.disposed) notify(error.message + ' Mở lại kết quả để tiếp tục từ tiến độ đã lưu.', true);
    } finally {
      working.current = false;
      if (!token.disposed) { setBusy(false); setInternetRunning(false); setInternetStopping(false); }
    }
  }
  function stopInternet() {
    if (internetRun.current) { internetRun.current.stopped = true; setInternetStopping(true); }
  }
  async function manualRefresh() {
    if (working.current) return;
    working.current = true; setBusy(true);
    try { await refresh(); } finally { working.current = false; setBusy(false); }
  }
  return <>
    <header className="topbar"><a className="brand" href="/" aria-label="Đối chiếu — trang chủ"><span className="brand-mark" aria-hidden="true">Đ</span><span>đối chiếu<span className="brand-sub">BÁO CÁO ĐỒ ÁN</span></span></a><span className="environment">Bản thử nghiệm cục bộ</span><span className={`connection ${ready ? 'ready' : ''}`}><span className="dot" />{ready ? 'PostgreSQL đã kết nối' : health ? 'Chưa kết nối dữ liệu' : 'Đang kết nối…'}</span></header>
    <main>
      <section className="page-heading"><div><p className="eyebrow">KHÔNG GIAN KIỂM TRA</p><h1>{pages[page].title}</h1><p className="muted">{pages[page].description}</p></div><button className="button secondary" disabled={busy} onClick={manualRefresh}>↻ Làm mới dữ liệu</button></section>
      {health && health.database !== 'ready' && <div className="setup"><strong>Chưa kết nối dữ liệu</strong><p>{health.detail}</p><p>Kiểm tra kết nối máy chủ rồi bấm “Làm mới dữ liệu”.</p></div>}
      {notice && <div id="notice" className={notice.error ? 'error' : ''} role="status" aria-live="polite">{notice.message}</div>}
      <section className="stats" aria-label="Tổng quan kho dữ liệu">{[['references', 'Tài liệu tham chiếu'], ['reference_chunks', 'Đoạn trong kho'], ['checks', 'Lần kiểm tra đã lưu']].map(([key, label]) => <div key={key}><span className="stat-value">{number(stats[key])}</span><span>{label}</span></div>)}<div className="stat-note"><span className="small-label">QUY TRÌNH</span><p>Thêm nguồn <span>→</span> Tải báo cáo <span>→</span> Đối chiếu</p></div></section>
      <nav className="page-nav" aria-label="Điều hướng chính">{Object.entries(pages).map(([key, item]) => <a key={key} href={`#${key}`} aria-current={page === key ? 'page' : undefined} onClick={() => setPage(key)}>{item.title}</a>)}</nav>
      <div hidden={page !== 'check'} className="app-page">
        <UploadPanel health={health} ready={ready} busy={busy} onUpload={file => upload(file, 'submission')} onError={message => notify(message, true)} />
        <ReportPanel report={report} sectionRef={resultSection} busy={busy} internetRunning={internetRunning} internetStopping={internetStopping} onContinueInternet={continueInternet} onStopInternet={stopInternet} />
      </div>
      <div hidden={page !== 'history'} className="app-page"><HistoryPanel checks={checks} busy={busy} onOpen={openReport} /></div>
      <div hidden={page !== 'references'} className="app-page"><ReferencePanel references={references} ready={ready} busy={busy} onUpload={file => upload(file, 'reference')} /></div>
      <footer>Điểm tương đồng hỗ trợ giảng viên thẩm định, không tự kết luận đạo văn.</footer>
    </main>
  </>;
}
