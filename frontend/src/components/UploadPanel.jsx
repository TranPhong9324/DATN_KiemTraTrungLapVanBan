import { useRef, useState } from 'react';
import { validateSelection } from '../api.js';
export default function UploadPanel({ health, ready, busy, onUpload, onError }) {
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const input = useRef(null);
  function chooseFile(selected) {
    try { validateSelection(selected, health?.max_upload_mb ?? 20); setFile(selected); }
    catch (error) { setFile(null); if (input.current) input.current.value = ''; onError(error.message); }
  }
  return <section className="panel check-panel">
    <div className="section-title"><span className="step">01</span><div><h2>Báo cáo cần kiểm tra</h2><p>Báo cáo này không tự thêm vào kho tham chiếu.</p></div></div>
    <form id="check-form" className={busy ? 'busy' : ''} onSubmit={event => { event.preventDefault(); onUpload(file); }}>
      <label className={`dropzone ${dragging ? 'dragging' : ''}`} htmlFor="check-file"
        onDragOver={event => { event.preventDefault(); if (!busy) setDragging(true); }}
        onDragLeave={() => setDragging(false)} onDrop={event => {
          event.preventDefault(); setDragging(false); if (busy) return;
          if (event.dataTransfer.files.length !== 1) return onError('Mỗi lần chỉ chọn một báo cáo.');
          chooseFile(event.dataTransfer.files[0]);
        }}>
        <span className="upload-symbol" aria-hidden="true">↑</span><strong>{file?.name || 'Kéo thả báo cáo vào đây'}</strong><span>hoặc bấm để chọn tệp</span>
        <span className="file-hint">PDF, DOCX · Tối đa {health?.max_upload_mb ?? 20} MB</span>
        <input ref={input} id="check-file" type="file" accept=".pdf,.docx" disabled={busy} onChange={event => chooseFile(event.target.files[0])} />
      </label>
      <button className="button primary" type="submit" disabled={busy || !ready || !file}>{busy ? 'Đang xử lý…' : 'Kiểm tra báo cáo'} <span aria-hidden="true">→</span></button>
    </form>
  </section>;
}
