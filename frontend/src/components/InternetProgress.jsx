export default function InternetProgress({ report, busy, running, stopping, onContinue, onStop }) {
  const state = report.internet_search;
  if (!state?.state_version) return null;
  return <section className="internet-progress" aria-label="Tiến độ kiểm tra Internet">
    <div className="internet-progress-heading"><strong>Kiểm tra Internet {state.complete ? '· Đã hoàn tất' : running ? '· Đang chạy' : '· Chưa hoàn tất'}</strong>
      <span>Đã tìm {state.searched_chunks} / {state.total_chunks} đoạn · Bỏ qua {state.skipped_chunks} đoạn quá ngắn · Còn {state.pending_chunks} đoạn</span>
    </div>
    <progress aria-label="Số đoạn đã xử lý" max={Math.max(1, state.total_chunks)} value={state.processed_chunks} />
    {state.warning && <p className="field-note">{state.warning}</p>}
    {!state.enabled ? <p className="field-note">Tìm Internet chưa bật. Kết quả hiện tại chỉ gồm đối chiếu kho nội bộ.</p>
      : !state.complete && <div className="internet-scan-controls">
        {running ? <button className="button secondary" disabled={stopping} onClick={onStop}>{stopping ? 'Đang dừng sau đợt hiện tại…' : 'Tạm dừng sau đợt này'}</button>
          : <button className="button secondary" disabled={busy || !onContinue} onClick={() => onContinue(report)}>{state.searched_chunks ? 'Tiếp tục kiểm tra Internet' : 'Kiểm tra Internet toàn báo cáo'}</button>}
        <p className="field-note">Xử lý theo thứ tự văn bản, tối đa {state.batch_size} đoạn mỗi đợt. Tiến độ được lưu sau mỗi đợt; mở lại báo cáo để tiếp tục khi bị ngắt. Không tô màu chưa có nghĩa là không trùng.</p>
      </div>}
  </section>;
}
