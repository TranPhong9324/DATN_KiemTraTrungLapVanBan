"use strict";
const $ = (selector) => document.querySelector(selector);
let ready = false;
let busy = false;
let lastReport = null;
let maxUploadMB = 20;
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const method = (engine) => engine === "semantic" ? "Ngữ nghĩa SBERT" : "So khớp từ vựng";
const date = (value) => new Date(value).toLocaleString("vi-VN", {dateStyle:"short", timeStyle:"short"});
const number = (value) => Number(value).toLocaleString("vi-VN", {maximumFractionDigits:2});

async function api(url, options = {}) {
  let response;
  try { response = await fetch(url, options); }
  catch { throw new Error("Không liên lạc được với web. Kiểm tra cửa sổ chạy máy chủ và thử lại."); }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(body.detail) ? body.detail.map((item) => item.msg).join("; ") : body.detail;
    throw new Error(detail || `Yêu cầu thất bại (${response.status}).`);
  }
  return body;
}
function notify(message, error = false) {
  $("#notice").hidden = false;
  $("#notice").textContent = message;
  $("#notice").classList.toggle("error", error);
}
function controls() {
  $("#check-button").disabled = busy || !ready;
  $("#reference-button").disabled = busy || !ready;
  $("#refresh").disabled = busy;
  $("#check-file").disabled = busy;
  $("#reference-file").disabled = busy;
  $("#check-form").classList.toggle("busy", busy);
}
async function refresh() {
  try {
    const health = await api("/api/health");
    ready = health.database === "ready";
    maxUploadMB = health.max_upload_mb;
    $("#connection").classList.toggle("ready", ready);
    $("#connection").innerHTML = `<span class="dot"></span>${ready ? "PostgreSQL đã kết nối" : "Chưa kết nối dữ liệu"}`;
    $("#setup").hidden = ready;
    $("#setup-detail").textContent = health.detail;
    $("#file-hint").textContent = `PDF, DOCX · Tối đa ${maxUploadMB} MB`;
    if (!ready) return;
    const [stats, documents, checks] = await Promise.all([api("/api/stats"), api("/api/documents?role=reference"), api("/api/checks")]);
    $("#stat-references").textContent = number(stats.references);
    $("#stat-chunks").textContent = number(stats.reference_chunks);
    $("#stat-checks").textContent = number(stats.checks);
    const references = documents.filter((item) => item.role === "reference");
    $("#reference-list").innerHTML = references.length ? references.map((item) => `<div class="reference-item"><span class="file-icon">${escapeHtml(item.file_type.toUpperCase())}</span><div class="reference-info"><strong>${escapeHtml(item.filename)}</strong><small>${number(item.chunks)} đoạn · ${number(item.size_bytes / 1024)} KB${item.warnings.length ? " · Có cảnh báo trích xuất" : ""}</small></div><a href="/api/documents/${encodeURIComponent(item.id)}/file" aria-label="Tải ${escapeHtml(item.filename)}">Tải</a></div>`).join("") : '<p class="empty">Chưa có tài liệu tham chiếu.<br>Thêm báo cáo cũ để bắt đầu.</p>';
    $("#history").innerHTML = checks.length ? checks.map((item) => `<tr><td>${escapeHtml(item.filename)}</td><td>${escapeHtml(date(item.created_at))}</td><td>${method(item.engine)}</td><td>${number(item.coverage)}%</td><td><button class="button secondary history-open" data-id="${escapeHtml(item.id)}" type="button">Xem kết quả</button></td></tr>`).join("") : '<tr><td colspan="5" class="empty">Chưa có lần kiểm tra nào.</td></tr>';
  } catch (error) { ready = false; notify(error.message, true); }
  finally { controls(); }
}
function locationLabel(location) {
  const start = [location.label, location.section].filter(Boolean).join(" · ");
  const range = location.end_label && location.end_label !== location.label ? `${start} → ${location.end_label}` : start;
  return location.extraction_method === "ocr" ? `${range} · OCR` : range;
}
function severity(score) {
  if (score >= 0.8) return {key:"high", label:"Trùng lặp cao"};
  if (score >= 0.65) return {key:"medium", label:"Trùng lặp trung bình"};
  return {key:"low", label:"Trùng lặp thấp"};
}
function reportMatches(report) {
  return (report.matches || []).map((match, index) => ({...match, alert_number: match.alert_number || index + 1}));
}
function reportChunks(report, matches) {
  if (report.document_chunks?.length) return report.document_chunks;
  const chunks = new Map();
  matches.forEach((match) => {
    const id = match.query_chunk_id || `old-${match.alert_number}`;
    if (!chunks.has(id)) chunks.set(id, {id, ordinal:match.query_ordinal || match.alert_number, text:match.query_text, location:match.query_location, alert_numbers:[], max_score:0});
    const chunk = chunks.get(id);
    chunk.alert_numbers.push(match.alert_number);
    chunk.max_score = Math.max(chunk.max_score, match.score);
  });
  return [...chunks.values()].sort((a, b) => a.ordinal - b.ordinal);
}
function renderWebSources(search) {
  if (!search) return "";
  const matches = search.matches || [];
  const cards = matches.slice(0, 20).map((item, index) => { const level = severity(item.web_score); const sourceNumber = item.internet_number || index + 1; return `<article class="alert-card severity-${level.key}" data-web-query="${escapeHtml(item.query_id)}"><div class="alert-card-top"><span class="severity-dot" aria-hidden="true"></span><strong>${number(sourceNumber)} ${level.label.toUpperCase()} - ${number(item.web_score * 100)}%</strong></div><h3>${escapeHtml(item.title)}</h3><p class="alert-method">Nguồn Internet${item.candidate ? " · Nghi vấn" : " · Tham khảo"}</p><p class="alert-excerpt">${escapeHtml(item.snippet || "")}</p><div class="alert-card-bottom"><span>Đoạn ${number((item.query_ordinal ?? 0) + 1)}</span><span class="source-actions"><button class="source-jump" type="button" data-query-id="${escapeHtml(item.query_id)}">Đến đoạn đối chiếu</button><a href="${escapeHtml(item.link)}" target="_blank" rel="noopener noreferrer">Mở nguồn ↗</a></span></div></article>`; }).join("");
  const status = search.warning ? `<p class="warning">${escapeHtml(search.warning)}</p>` : `<p class="field-note">Đã tìm ${number(search.queries?.length || 0)} đoạn trên Internet sau khi đối chiếu kho nội bộ.</p>`;
  return `<div class="web-review"><div class="web-review-heading"><span class="toolbar-kicker">NGUỒN INTERNET</span><strong>${number(matches.length)} nguồn bổ sung</strong></div>${status}${cards || '<p class="field-note">Không tìm thấy nguồn Internet phù hợp.</p>'}</div>`;
}
function renderReport(report) {
  lastReport = report;
  $("#result-empty").hidden = true;
  $("#result").hidden = false;
  $("#export").hidden = false;
  $("#result-subtitle").textContent = report.filename;
  const thresholdNote = report.threshold_calibrated ? "Ngưỡng khởi đầu được chọn trên tập validation; vẫn cần xác nhận bằng báo cáo thật." : "Ngưỡng do người dùng chọn; cần đọc nội dung đối chiếu trước khi kết luận.";
  const eligible = report.eligible_chunks ?? report.total_chunks;
  const ignored = Object.values(report.ignored_chunks?.queries || {}).reduce((sum, value) => sum + value, 0);
  const processingNote = [ignored ? `${number(ignored)} đoạn không phù hợp đã được bỏ qua` : "", report.suppressed_alerts ? `${number(report.suppressed_alerts)} cảnh báo lặp đã được ẩn` : ""].filter(Boolean).join(" · ");
  const matches = reportMatches(report);
  const chunks = reportChunks(report, matches);
  const webMatches = (report.internet_search?.matches || []).map((item, index) => ({...item, internet_number: index + 1}));
  const webMarkers = new Map();
  webMatches.filter((item) => item.candidate).forEach((item) => {
    const values = webMarkers.get(item.query_id) || [];
    values.push(item.internet_number);
    webMarkers.set(item.query_id, values);
  });
  chunks.forEach((chunk) => { chunk.web_markers = webMarkers.get(chunk.id) || []; });
  const documentHtml = chunks.map((chunk) => {
    const alertNumbers = chunk.alert_numbers || [];
    const webNumbers = chunk.web_markers || [];
    const level = severity(chunk.max_score || 0);
    const badges = alertNumbers.map((value) => `<button class="document-marker" type="button" data-alert="${number(value)}" aria-label="Mở cảnh báo ${number(value)}">${number(value)}</button>`).join("");
    const webBadges = webNumbers.map((value) => `<span class="document-marker web-marker" title="Nguồn Internet nghi vấn">W${number(value)}</span>`).join("");
    return `<section class="document-block ${alertNumbers.length || webNumbers.length ? `is-match severity-${level.key}` : ""} ${chunk.ignored ? "is-ignored" : ""}" id="doc-chunk-${escapeHtml(chunk.id)}" data-alerts="${alertNumbers.join(",")}"><div class="document-location">${escapeHtml(locationLabel(chunk.location || {}))}${chunk.ignored ? " · Đã loại khỏi đối chiếu" : ""}</div><div class="document-text">${badges}${webBadges}<span>${escapeHtml(chunk.text)}</span></div></section>`;
  }).join("");
  const alertsHtml = matches.map((match) => {
    const level = severity(match.score);
    return `<article class="alert-card severity-${level.key}" id="alert-${number(match.alert_number)}" data-alert="${number(match.alert_number)}" tabindex="0"><div class="alert-card-top"><span class="severity-dot" aria-hidden="true"></span><strong>${number(match.alert_number)} ${level.label.toUpperCase()} - ${number(match.score * 100)}%</strong></div><h3>${escapeHtml(match.source_filename)}</h3><p class="alert-method">${escapeHtml(match.alert_label || report.alert_label || method(report.engine))}${match.chunk_count > 1 ? ` · ${number(match.chunk_count)} đoạn liền nhau` : ""}</p><p class="alert-excerpt">${escapeHtml(match.source_text)}</p><div class="alert-card-bottom"><span>${escapeHtml(locationLabel(match.source_location || {}))}</span><a href="/api/documents/${encodeURIComponent(match.source_document_id)}/file">${escapeHtml(match.source_filename)} ↗</a></div></article>`;
  }).join("");
  const previewUrl = `/api/documents/${encodeURIComponent(report.document_id)}/preview#toolbar=0&navpanes=0`;
  const totalResults = matches.length + webMatches.length;
  const sourceSummary = `${number(report.sources?.length || 0)} nội bộ · ${number(webMatches.length)} Internet`;
  $("#result").innerHTML = `<div class="review-summary"><div><span class="review-percent">${number(report.coverage)}%</span><strong>Nội dung được cảnh báo</strong></div><div><strong>${number(report.matched_chunks)} / ${number(eligible)} đoạn</strong><span>${escapeHtml(report.alert_label || method(report.engine))} · Ngưỡng ${number(report.threshold)}</span></div><div><strong>${sourceSummary} nguồn đối chiếu</strong><span>${processingNote || thresholdNote}</span></div></div>${(report.warnings || []).map((warning) => `<p class="warning">${escapeHtml(warning)}</p>`).join("")}<div class="review-layout"><section class="document-view"><header class="review-toolbar"><div><span class="toolbar-kicker">VĂN BẢN ĐANG KIỂM TRA</span><h3>${escapeHtml(report.filename)}</h3></div><div class="preview-switch" role="group" aria-label="Kiểu xem văn bản"><button class="preview-toggle is-active" data-mode="original" type="button">Bản gốc</button><button class="preview-toggle" data-mode="marked" type="button">Văn bản đánh dấu</button></div></header><iframe class="document-preview" title="Bản xem trước ${escapeHtml(report.filename)}" src="${previewUrl}"></iframe><div class="document-paper" hidden>${documentHtml || '<div class="result-empty"><h3>Không có nội dung văn bản trong báo cáo cũ.</h3></div>'}</div></section><aside class="alerts-view"><header class="review-toolbar"><div><span class="alert-count">${number(totalResults)}</span><h3>Kết quả đối chiếu</h3></div><span>Nội bộ và Internet</span></header><div class="source-ranking">${(report.sources || []).map((source) => `<span>#${number(source.rank || 1)} ${escapeHtml(source.filename)} · ${number(source.coverage)}%</span>`).join("")}</div><div class="alerts-list">${alertsHtml || '<div class="result-empty"><h3>Không có đoạn vượt ngưỡng nội bộ</h3><p>Hãy xem thêm các nguồn Internet bên dưới.</p></div>'}${renderWebSources(report.internet_search)}</div></aside></div>`;
}
function validateSelection(file) {
  if (!file) throw new Error("Vui lòng chọn một tài liệu.");
  if (!/\.(pdf|docx)$/i.test(file.name)) throw new Error("Chỉ hỗ trợ PDF và DOCX.");
  if (!file.size) throw new Error("Tệp đang chọn rỗng.");
  if (file.size > maxUploadMB * 1024 * 1024) throw new Error(`Tệp vượt giới hạn ${maxUploadMB} MB.`);
}
$("#check-file").addEventListener("change", () => { $("#file-label").textContent = $("#check-file").files[0]?.name || "Kéo thả báo cáo vào đây"; });
for (const event of ["dragenter", "dragover"]) $("#dropzone").addEventListener(event, (e) => { e.preventDefault(); if (!busy) $("#dropzone").classList.add("dragging"); });
for (const event of ["dragleave", "drop"]) $("#dropzone").addEventListener(event, (e) => { e.preventDefault(); $("#dropzone").classList.remove("dragging"); });
$("#dropzone").addEventListener("drop", (e) => {
  if (busy) return;
  try {
    if (e.dataTransfer.files.length !== 1) throw new Error("Mỗi lần chỉ chọn một báo cáo.");
    validateSelection(e.dataTransfer.files[0]);
    $("#check-file").files = e.dataTransfer.files;
    $("#check-file").dispatchEvent(new Event("change"));
  } catch (error) { notify(error.message, true); }
});
$("#reference-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    validateSelection($("#reference-file").files[0]);
    const data = new FormData(e.currentTarget);
    busy = true; controls(); notify("Đang trích xuất tài liệu và lưu vào kho tham chiếu…");
    const result = await api("/api/references", {method:"POST", body:data});
    $("#reference-form").reset();
    notify(`Đã thêm ${result.filename}: ${result.chunks} đoạn.${result.warnings.length ? " " + result.warnings.join(" ") : ""}`);
    await refresh();
  } catch (error) { notify(error.message, true); }
  finally { busy = false; controls(); }
});
$("#check-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    validateSelection($("#check-file").files[0]);
    const data = new FormData(e.currentTarget);
    busy = true; controls(); notify("Đang trích xuất và đối chiếu báo cáo. Hãy giữ trang mở cho đến khi hoàn tất…");
    const result = await api("/api/checks", {method:"POST", body:data});
    renderReport(result);
    notify("Đã kiểm tra và lưu kết quả vào PostgreSQL.");
    await refresh();
    $("#result-section").scrollIntoView({behavior:"smooth", block:"start"});
  } catch (error) { notify(error.message, true); }
  finally { busy = false; controls(); }
});
$("#history").addEventListener("click", async (e) => {
  const button = e.target.closest(".history-open");
  if (!button || busy) return;
  try { renderReport(await api(`/api/checks/${encodeURIComponent(button.dataset.id)}`)); $("#result-section").scrollIntoView({behavior:"smooth"}); }
  catch (error) { notify(error.message, true); }
});
function setReviewMode(mode) {
  const original = mode === "original";
  const preview = document.querySelector(".document-preview");
  const paper = document.querySelector(".document-paper");
  if (!preview || !paper) return;
  preview.hidden = !original;
  paper.hidden = original;
  document.querySelectorAll(".preview-toggle").forEach((button) => button.classList.toggle("is-active", button.dataset.mode === mode));
}
function focusAlert(alertNumber, scrollToDocument) {
  document.querySelectorAll(".alert-card.is-active,.document-block.is-active").forEach((item) => item.classList.remove("is-active"));
  const card = document.querySelector(`#alert-${alertNumber}`);
  const blocks = [...document.querySelectorAll(".document-block")].filter((item) => (item.dataset.alerts || "").split(",").includes(String(alertNumber)));
  card?.classList.add("is-active");
  blocks.forEach((item) => item.classList.add("is-active"));
  if (scrollToDocument) setReviewMode("marked");
  (scrollToDocument ? blocks[0] : card)?.scrollIntoView({behavior:"smooth", block:"center"});
}
function focusWebSource(queryId) {
  document.querySelectorAll(".alert-card.is-active,.document-block.is-active").forEach((item) => item.classList.remove("is-active"));
  const block = document.querySelector(`#doc-chunk-${CSS.escape(queryId)}`);
  const card = document.querySelector(`.alert-card[data-web-query="${CSS.escape(queryId)}"]`);
  setReviewMode("marked");
  block?.classList.add("is-active");
  card?.classList.add("is-active");
  block?.scrollIntoView({behavior:"smooth", block:"center"});
}
$("#result").addEventListener("click", (event) => {
  const toggle = event.target.closest(".preview-toggle");
  if (toggle) { setReviewMode(toggle.dataset.mode); return; }
  const marker = event.target.closest(".document-marker");
  if (marker) { focusAlert(marker.dataset.alert, false); return; }
  const sourceJump = event.target.closest(".source-jump");
  if (sourceJump) { focusWebSource(sourceJump.dataset.queryId); return; }
  const card = event.target.closest(".alert-card");
  if (card && !event.target.closest("a")) focusAlert(card.dataset.alert, true);
});
$("#result").addEventListener("keydown", (event) => {
  const card = event.target.closest(".alert-card");
  if (card && ["Enter", " "].includes(event.key)) { event.preventDefault(); focusAlert(card.dataset.alert, true); }
});
$("#export").addEventListener("click", () => {
  if (!lastReport) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(lastReport, null, 2)], {type:"application/json;charset=utf-8"}));
  const anchor = document.createElement("a"); anchor.href = url; anchor.download = `ket-qua-${lastReport.id}.json`; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
$("#refresh").addEventListener("click", refresh);
refresh();
