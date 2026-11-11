import { useRef, useState } from 'react';
import { number } from '../format.js';
export default function ReferencePanel({ references, busy, ready, onUpload }) {
  const [file, setFile] = useState(null);
  const input = useRef(null);
  async function submit(event) {
    event.preventDefault();
    if (await onUpload(file)) { setFile(null); input.current.value = ''; }
  }
  return <section className="panel reference-panel">
    <div className="section-title"><span className="step">02</span><div><h2>Kho tham chiếu</h2><p>Thêm báo cáo cũ để làm nguồn đối chiếu.</p></div></div>
    <form id="reference-form" onSubmit={submit}><label className="reference-picker" htmlFor="reference-file">Chọn tài liệu nguồn<input ref={input} id="reference-file" type="file" accept=".pdf,.docx" disabled={busy} required onChange={event => setFile(event.target.files[0])} /></label><button className="button secondary" disabled={busy || !ready || !file}>+ Thêm vào kho</button></form>
    <div className="reference-list">{references.length ? references.map(item => <div className="reference-item" key={item.id}><span className="file-icon">{item.file_type.toUpperCase()}</span><div className="reference-info"><strong>{item.filename}</strong><small>{number(item.chunks)} đoạn · {number(item.size_bytes / 1024)} KB{item.warnings?.length ? ' · Có cảnh báo trích xuất' : ''}</small></div><a href={`/api/documents/${encodeURIComponent(item.id)}/file`} aria-label={`Tải ${item.filename}`}>Tải</a></div>) : <p className="empty">Chưa có tài liệu tham chiếu.<br />Thêm báo cáo cũ để bắt đầu.</p>}</div>
    <p className="field-note">Chỉ thêm tài liệu bạn được phép sử dụng. Hiển thị 100 tài liệu nguồn mới nhất.</p>
  </section>;
}
