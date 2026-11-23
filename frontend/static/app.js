"use strict";
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
let ready = false;
let busy = false;
let lastReport = null;
let review = null;           // trạng thái màn đối chiếu đang mở
let maxUploadMB = 20;
let currentUser = null;
let registrationEnabled = true;
const ROLE_LABELS = {user:"Người dùng", admin:"Quản trị"};
const roleLabel = (role) => ROLE_LABELS[role] || ROLE_LABELS.user;   // vai trò lạ (dữ liệu cũ chưa nâng cấp) được coi là người dùng thường
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const method = (engine) => engine === "semantic" ? "Ngữ nghĩa SBERT" : "So khớp từ vựng";
const date = (value) => new Date(value).toLocaleString("vi-VN", {dateStyle:"short", timeStyle:"short"});
const number = (value) => Number(value).toLocaleString("vi-VN", {maximumFractionDigits:2});
const siteOf = (url) => { try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return ""; } };  // tên miền để người đọc nhận ra trang
const safeUrl = (value) => /^https?:\/\//i.test(String(value || "")) ? String(value) : "";  // chỉ http(s), chặn javascript: từ dữ liệu bên ngoài
const jsonBody = (method, payload) => ({method, headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
const isAdmin = () => currentUser?.role === "admin";

async function api(url, options = {}) {
  let response;
  try { response = await fetch(url, options); }
  catch { throw new Error("Không liên lạc được với web. Kiểm tra cửa sổ chạy máy chủ và thử lại."); }
  const body = await response.json().catch(() => ({}));
  if (response.status === 401 && url !== "/api/auth/login") {
    // Lần mở trang đầu chưa đăng nhập: ở lại trang chủ, không báo lỗi. Đang dùng mà hết phiên: báo và chuyển tới đăng nhập.
    if (currentUser) showLogin("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại."); else signedOut();
    throw Object.assign(new Error("Cần đăng nhập."), {auth: true});
  }
  if (!response.ok) {
    const detail = Array.isArray(body.detail) ? body.detail.map((item) => item.msg).join("; ") : body.detail;
    throw new Error(detail || `Yêu cầu thất bại (${response.status}).`);
  }
  return body;
}

function clearData() {
  // Không để lại dữ liệu của người trước trên màn hình khi đăng xuất hoặc hết phiên.
  lastReport = null; review = null;
  $("#result").innerHTML = ""; $("#result").hidden = true; $("#result-empty").hidden = false; $("#export").hidden = true;
  $("#result-subtitle").textContent = "";
  $("#history").innerHTML = ""; $("#reference-list").innerHTML = ""; $("#web-list").innerHTML = "";
  $("#user-table").innerHTML = ""; $("#reset-user").innerHTML = "";
  ["#stat-references", "#stat-chunks", "#stat-checks", "#stat-web"].forEach((id) => { $(id).textContent = "—"; });
  ["#user-name", "#user-role", "#account-name", "#account-email", "#account-role", "#password-error", "#password-ok", "#notice"].forEach((id) => { $(id).textContent = ""; });
  $("#notice").hidden = true;
  $$("form").forEach((form) => form.reset());
  $$("input[type=password], input.was-password").forEach((input) => { input.type = "password"; });
  $("#check-file").dispatchEvent(new Event("change")); $("#reference-file").dispatchEvent(new Event("change"));
}

// ------------------------------------------------------------------ điều hướng
const PUBLIC_ROUTES = {"": "home", "trang-chu": "home", "faq": "home", "dang-nhap": "login", "dang-ky": "register"};
const VIEWS = {"kiem-tra":"check", "lich-su":"history", "kho":"references", "nguoi-dung":"users", "tai-khoan":"account"};
const VIEW_TITLES = {check:"Kiểm tra báo cáo", history:"Lịch sử kiểm tra", references:"Kho tham chiếu", users:"Người dùng", account:"Tài khoản"};
const PUBLIC_TITLES = {home:"Đối chiếu báo cáo đồ án", login:"Đăng nhập", register:"Đăng ký tài khoản"};
const SITE = "Đối chiếu báo cáo đồ án";
let scrollTarget = null;  // phần tử cần cuộn tới sau khi đổi mục (nếu không có thì về đầu trang)

function allowedView(name) {
  if (name === "users") return currentUser?.role === "admin" ? name : "check";
  if (name === "references") return isAdmin() ? name : "check";   // chỉ quản trị vào kho tham chiếu
  return name;
}
function showPublic(name, moveFocus = false) {
  $("#public-view").hidden = false; $("#app-view").hidden = true;
  $("#public-nav").hidden = false; $("#main-nav").hidden = true; $("#user-box").hidden = true;
  ["home", "login", "register"].forEach((id) => { $(`#${id}-view`).hidden = id !== name; });
  $("#register-form").hidden = !registrationEnabled; $("#register-disabled").hidden = registrationEnabled;
  document.title = name === "home" ? SITE : `${PUBLIC_TITLES[name]} · ${SITE}`;
  const heading = name === "home" ? ($("#home-title")) : $(`#${name}-title`);
  if (location.hash === "#faq" && name === "home") { $("#faq").scrollIntoView({block:"start"}); if (moveFocus) $("#faq-title").focus({preventScroll:true}); return; }
  window.scrollTo(0, 0);
  if (moveFocus) heading.focus({preventScroll:true});
}
function showView(name, moveFocus = false) {
  $("#public-view").hidden = true; $("#app-view").hidden = false;
  $("#public-nav").hidden = true; $("#main-nav").hidden = false; $("#user-box").hidden = false;
  $$(".view").forEach((section) => { section.hidden = section.id !== `view-${name}`; });
  $$("#main-nav a, #user-name").forEach((link) => {
    if (link.dataset.view === name) link.setAttribute("aria-current", "page"); else link.removeAttribute("aria-current");
  });
  document.title = `${VIEW_TITLES[name]} · ${SITE}`;
  if (moveFocus) $(`#title-${name}`).focus({preventScroll:true});  // người dùng bàn phím/đọc màn hình biết mục đã đổi
}
function route(moveFocus = false) {
  let key = location.hash.slice(1);
  try { key = decodeURIComponent(key); } catch { key = ""; }  // băm sai định dạng: coi như trang chủ
  if (!currentUser) {
    // Chưa đăng nhập: các mục riêng tư đưa tới đăng nhập; còn lại là trang chủ.
    if (key in PUBLIC_ROUTES) showPublic(PUBLIC_ROUTES[key], moveFocus);
    else if (key in VIEWS) showPublic("login", moveFocus);
    else showPublic("home", moveFocus);
    return;
  }
  if (key in PUBLIC_ROUTES && key !== "") { history.replaceState(null, "", "#kiem-tra"); }  // đã đăng nhập thì không ở trang chủ/đăng nhập
  const wanted = VIEWS[location.hash.slice(1)] || (location.hash.slice(1) === "" || location.hash.slice(1) in PUBLIC_ROUTES ? "check" : null);
  if (!wanted) { if ($("#app-view").hidden) showView("check", moveFocus); return; }  // băm lạ (ví dụ #main): giữ nguyên mục đang xem
  const view = allowedView(wanted);
  if (view !== wanted) history.replaceState(null, "", "#kiem-tra");
  showView(view, moveFocus);
}
function afterNavigate() {
  const target = scrollTarget; scrollTarget = null;
  if (target) target.scrollIntoView({block:"start"}); else if (location.hash !== "#faq") window.scrollTo(0, 0);
}
function goTo(hash, target = null) {
  scrollTarget = target;
  if (location.hash === hash) { route(!target); afterNavigate(); } else location.hash = hash;
}
window.addEventListener("hashchange", () => { route(!scrollTarget); afterNavigate(); });
$(".skip-link").addEventListener("click", (event) => { event.preventDefault(); $("#main").focus(); });

function signedOut() { currentUser = null; clearData(); route(); }
function showLogin(message = "") {
  currentUser = null; clearData();
  if (message) { history.replaceState(null, "", "#dang-nhap"); }
  route();
  $("#login-error").textContent = message;
}
function showApp(user) {
  currentUser = user;
  $("#user-name").textContent = user.full_name;
  $("#user-name").setAttribute("aria-label", `${user.full_name} (tài khoản và đổi mật khẩu)`); $("#user-name").title = "Tài khoản và đổi mật khẩu";
  $("#user-role").textContent = roleLabel(user.role);
  $("#account-name").textContent = user.full_name; $("#account-email").textContent = user.email; $("#account-role").textContent = roleLabel(user.role);
  const admin = user.role === "admin";
  $("#nav-users").hidden = !admin;
  $("#nav-references").hidden = !admin;
  $("#reference-form").hidden = !admin; $("#reference-note").hidden = !admin;
  route();
}
function notify(message, error = false) {
  $("#notice").hidden = false;
  $("#notice").textContent = message;
  $("#notice").classList.toggle("error", error);
}
function controls() {
  $("#refresh").disabled = busy;
  $("#check-file").disabled = busy;
  $("#reference-file").disabled = busy;
  $("#check-button").disabled = busy || !ready || !$("#check-file").files.length;
  $("#reference-button").disabled = busy || !ready || !$("#reference-file").files.length;
  $("#check-form").classList.toggle("busy", busy);
}
function applyRegistrationSetting() {
  ["#nav-register", "#hero-register", "#login-register-line"].forEach((id) => { $(id).hidden = !registrationEnabled; });
  $("#register-form").hidden = !registrationEnabled; $("#register-disabled").hidden = registrationEnabled;
}

async function refresh() {
  try {
    const health = await api("/api/health");
    ready = health.database === "ready";
    maxUploadMB = health.max_upload_mb;
    registrationEnabled = health.registration_enabled !== false; applyRegistrationSetting();
    // Phương pháp và ngưỡng theo cấu hình máy chủ: chưa bật SBERT thì dùng so khớp từ vựng thay vì gửi yêu cầu chắc chắn lỗi.
    const engine = health.semantic_enabled ? "semantic" : "lexical";
    $("#check-form [name=engine]").value = engine;
    $("#check-form [name=threshold]").value = health.thresholds?.[engine] ?? (engine === "semantic" ? 0.68 : 0.30);
    $("#connection").classList.toggle("ready", ready);
    $("#connection").innerHTML = `<span class="dot" aria-hidden="true"></span>${ready ? "PostgreSQL đã kết nối" : "Chưa kết nối dữ liệu"}`;
    $("#setup").hidden = ready;
    $("#setup-detail").textContent = health.detail;
    $("#file-hint").textContent = `PDF hoặc DOCX, tối đa ${maxUploadMB} MB`;
    if (!ready) { currentUser = null; route(); return; }
    showApp(await api("/api/auth/me"));
    if (currentUser.role === "admin") await loadAdmin();
    // Người dùng thường không gọi các API của kho tham chiếu (máy chủ cũng từ chối).
    const [stats, documents, checks, webSources] = await Promise.all([api("/api/stats"), isAdmin() ? api("/api/documents?role=reference") : [], api("/api/checks"), isAdmin() ? api("/api/documents?role=web") : []]);
    $("#stat-checks").textContent = number(stats.checks);
    if (isAdmin()) {
      $("#stat-references").textContent = number(stats.references);
      $("#stat-chunks").textContent = number(stats.reference_chunks);
      $("#stat-web").textContent = number(stats.web_sources);
      $("#web-list").innerHTML = webSources.length ? webSources.map((item) => {
        const url = safeUrl(item.source_url);
        return `<tr><td>${escapeHtml(item.filename)}<br>${url ? `<a class="muted" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(clip(url, 70))}<span class="sr-only"> (mở tab mới)</span></a>` : ""}</td><td>${escapeHtml(date(item.created_at))}</td><td class="num">${number(item.chunks)}</td><td><button class="button secondary web-delete" type="button" data-id="${escapeHtml(item.id)}" data-title="${escapeHtml(item.filename)}" aria-label="Xóa nguồn Internet ${escapeHtml(item.filename)}">Xóa</button></td></tr>`;
      }).join("") : '<tr><td colspan="4" class="empty">Chưa có trang Internet nào được lưu. Trang tìm thấy khi kiểm tra sẽ tự được lưu ở đây.</td></tr>';
      const references = documents.filter((item) => item.role === "reference");
      $("#reference-list").innerHTML = references.length ? references.map((item) => `<tr><td>${escapeHtml(item.filename)}${item.warnings.length ? ' <span class="muted">(có cảnh báo trích xuất)</span>' : ""}</td><td>${escapeHtml(item.file_type.toUpperCase())}</td><td class="num">${number(item.chunks)}</td><td class="num">${number(item.size_bytes / 1024)} KB</td><td><a href="/api/documents/${encodeURIComponent(item.id)}/file" aria-label="Tải ${escapeHtml(item.filename)}">Tải xuống</a></td></tr>`).join("") : '<tr><td colspan="5" class="empty">Chưa có tài liệu tham chiếu. Thêm báo cáo cũ để bắt đầu.</td></tr>';
    }
    $("#history").innerHTML = checks.length ? checks.map((item) => `<tr><td>${escapeHtml(item.filename)}</td><td>${escapeHtml(date(item.created_at))}</td><td>${method(item.engine)}</td><td class="num">${number(item.coverage)}%</td><td><button class="button secondary history-open" data-id="${escapeHtml(item.id)}" type="button" aria-label="Xem kết quả của ${escapeHtml(item.filename)}">Xem kết quả</button></td></tr>`).join("") : '<tr><td colspan="5" class="empty">Chưa có lần kiểm tra nào.</td></tr>';
  } catch (error) {
    ready = false;
    if (error.auth) return;  // đã chuyển về trang chủ / đăng nhập
    if (currentUser) notify(error.message, true);
    else { route(); $("#login-error").textContent = error.message; }
  } finally { controls(); }
}

async function loadAdmin() {
  const users = await api("/api/users");
  $("#user-table").innerHTML = users.map((user) => {
    const self = user.id === currentUser.id;
    const current = user.role === "admin" ? "admin" : "user";
    const roles = Object.entries(ROLE_LABELS).map(([value, label]) => `<option value="${value}"${value === current ? " selected" : ""}>${label}</option>`).join("");
    return `<tr><td>${escapeHtml(user.full_name)}</td><td>${escapeHtml(user.email)}</td><td><select class="role-select" data-id="${escapeHtml(user.id)}" aria-label="Vai trò của ${escapeHtml(user.full_name)}"${self ? " disabled" : ""}>${roles}</select></td><td><span class="status${user.is_active ? "" : " off"}">${user.is_active ? "Hoạt động" : "Đã khóa"}</span></td><td><button class="button secondary toggle-active" data-id="${escapeHtml(user.id)}" data-active="${user.is_active}" type="button"${self ? " disabled" : ""}>${user.is_active ? "Khóa" : "Mở khóa"}</button></td></tr>`;
  }).join("");
  $("#reset-user").innerHTML = users.filter((u) => u.id !== currentUser.id).map((u) => `<option value="${escapeHtml(u.id)}">${escapeHtml(u.full_name)} · ${escapeHtml(u.email)}</option>`).join("") || '<option value="">Chưa có tài khoản khác</option>';
}
async function adminAction(task, success) {
  try { await task(); notify(success); await loadAdmin(); }
  catch (error) { notify(error.message, true); }
}

// ------------------------------------------------------------------ màn đối chiếu
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

// Cụm từ trùng nguyên văn: từ n từ liên tiếp trở lên xuất hiện ở cả hai đoạn (không phân biệt hoa/thường và dấu câu).
// Đây chỉ là gợi ý hiển thị để người đọc thấy chỗ giống; điểm cảnh báo do máy chủ tính, không đổi.
const SHARED_MIN_WORDS = 4;
function tokenize(text) {
  return [...String(text || "").matchAll(/[\p{L}\p{N}]+/gu)].map((m) => ({start:m.index, end:m.index + m[0].length, norm:m[0].normalize("NFC").toLowerCase()}));
}
function sharedMarks(tokens, otherTokens, n) {
  const marks = new Array(tokens.length).fill(false);
  if (n < 1 || tokens.length < n || otherTokens.length < n) return marks;
  const grams = new Set();
  for (let i = 0; i + n <= otherTokens.length; i++) grams.add(otherTokens.slice(i, i + n).map((t) => t.norm).join(" "));
  for (let i = 0; i + n <= tokens.length; i++) {
    if (grams.has(tokens.slice(i, i + n).map((t) => t.norm).join(" "))) for (let k = i; k < i + n; k++) marks[k] = true;
  }
  return marks;
}
function highlight(text, tokens, marks) {
  let html = "", position = 0, i = 0;
  while (i < tokens.length) {
    if (!marks[i]) { i++; continue; }
    let j = i;
    while (j + 1 < tokens.length && marks[j + 1]) j++;
    html += escapeHtml(text.slice(position, tokens[i].start)) + `<mark>${escapeHtml(text.slice(tokens[i].start, tokens[j].end))}</mark>`;
    position = tokens[j].end; i = j + 1;
  }
  return html + escapeHtml(text.slice(position));
}
function comparePair(targetText, sourceText) {
  const targetTokens = tokenize(targetText), sourceTokens = tokenize(sourceText);
  // Đoạn ngắn hơn 4 từ thì dùng độ dài đoạn ngắn làm cụm tối thiểu (nếu không sẽ không bao giờ có chỗ nào được tô).
  const n = Math.min(SHARED_MIN_WORDS, targetTokens.length, sourceTokens.length);
  const targetMarks = sharedMarks(targetTokens, sourceTokens, n), sourceMarks = sharedMarks(sourceTokens, targetTokens, n);
  const shared = targetMarks.filter(Boolean).length;
  return {
    targetHtml: highlight(targetText, targetTokens, targetMarks), sourceHtml: highlight(sourceText, sourceTokens, sourceMarks),
    n, shared, total: targetTokens.length, percent: targetTokens.length ? Math.round(shared / targetTokens.length * 100) : 0,
  };
}

function buildItems(report, matches, chunks) {
  const chunkById = new Map(chunks.map((chunk) => [chunk.id, chunk]));
  const internal = matches.map((match) => ({
    key: `a${match.alert_number}`, kind: "internal", no: String(match.alert_number), score: match.score, level: severity(match.score),
    source: match.source_filename, sourceId: match.source_document_id || null, redacted: Boolean(match.redacted),
    // Trang Internet đã lưu trong CSDL: so khớp toàn văn như nguồn nội bộ, nhưng có địa chỉ trang gốc.
    fromWeb: match.source_kind === "web", link: match.source_kind === "web" ? safeUrl(match.source_url) : "",
    method: [match.alert_label || report.alert_label || method(report.engine), match.source_kind === "web" ? "Nguồn Internet (bản đã lưu)" : ""].filter(Boolean).join(" · "), count: match.chunk_count || 1,
    targetText: match.query_text || "", targetLoc: locationLabel(match.query_location || {}),
    sourceText: match.source_text || "", sourceLoc: locationLabel(match.source_location || {}),
    chunkIds: match.query_chunk_ids || (match.query_chunk_id ? [match.query_chunk_id] : []),
  }));
  // Kết quả tìm kiếm đã được tải về và đối chiếu toàn văn (stored) thì không hiện thêm đoạn trích ngắn nữa.
  // Kết quả tìm kiếm không có cụm trùng nào với đoạn của bài (chỉ cùng từ khóa) không phải cảnh báo: không đưa vào danh sách.
  const web = (report.internet_search?.matches || []).filter((item) => !item.stored && item.candidate).map((item, index) => {
    const chunk = chunkById.get(item.query_id);
    return {
      key: `w${index + 1}`, kind: "web", no: `W${index + 1}`, score: item.web_score, level: severity(item.web_score),
      source: item.title || "Nguồn Internet", sourceId: null, link: safeUrl(item.link), candidate: Boolean(item.candidate),
      fetchError: item.fetch_error || "",
      method: `Nguồn Internet · ${item.candidate ? "Nghi vấn" : "Tham khảo"}`, count: 1,
      targetText: chunk?.text || "", targetLoc: chunk ? locationLabel(chunk.location || {}) : "",
      sourceText: item.snippet || "", sourceLoc: "Đoạn trích từ kết quả tìm kiếm",
      chunkIds: item.query_id ? [item.query_id] : [],
    };
  });
  return [...internal, ...web];
}

const clip = (text, size = 140) => { const flat = String(text || "").replace(/\s+/g, " ").trim(); return flat.length > size ? flat.slice(0, size - 1) + "…" : flat; };

function renderBlockText(chunk) {
  const text = String(chunk.text || "");
  const lines = text.split("\n");
  const isTable = String(chunk.location?.label || "").startsWith("Bảng") && lines.some((line) => line.includes(" | "));
  if (!isTable) return `<div class="document-text">${escapeHtml(text)}</div>`;
  const rows = [];
  lines.forEach((line) => {
    if (line.includes(" | ")) rows.push(line.split(" | "));
    else if (rows.length) rows[rows.length - 1][rows[rows.length - 1].length - 1] += `\n${line}`;  // ô nhiều dòng
    else rows.push([line]);
  });
  return `<table class="doc-table"><tbody>${rows.map((cells) => `<tr>${cells.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
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
  const items = buildItems(report, matches, chunks);
  const levelCount = (key) => items.filter((item) => item.level.key === key).length;
  const levelSummary = `Cao ${number(levelCount("high"))} · Trung bình ${number(levelCount("medium"))} · Thấp ${number(levelCount("low"))}`;
  const wordLevel = report.similarity_index !== undefined && report.similarity_index !== null;
  const headline = wordLevel
    ? `<div><dt>Chỉ số trùng nguyên văn</dt><dd><span class="review-percent">${number(report.similarity_index)}%</span><small>Tính theo số từ nằm trong cụm ${number(report.min_shared_words || 4)} từ trùng liên tiếp; không phải kết luận đạo văn</small></dd></div>`
    : `<div><dt>Nội dung được cảnh báo</dt><dd><span class="review-percent">${number(report.coverage)}%</span></dd></div>`;
  review = {report, items, chunks, filtered: items, activeKey: null};

  const sources = (report.sources || []).map((source) => ({name: source.filename, coverage: source.word_coverage ?? source.coverage, site: source.kind === "web" ? siteOf(safeUrl(source.url)) : ""}));
  const isWeb = (item) => item.kind === "web" || item.fromWeb;
  const hasWeb = items.some(isWeb);
  const sourceOptions = [`<option value="">Tất cả nguồn</option>`]
    .concat(sources.map((source) => `<option value="in:${escapeHtml(source.name)}">${escapeHtml(source.name)}${source.site ? ` · ${escapeHtml(source.site)}` : ""} (${number(source.coverage)}%)</option>`))
    .concat(hasWeb ? [`<option value="web">Nguồn Internet</option>`] : []).join("");
  const savedSources = (report.sources || []).filter((source) => source.kind === "web").length;
  const sourceSummary = `${number((report.sources?.length || 0) - savedSources)} nội bộ, ${number(savedSources + new Set(items.filter((item) => item.kind === "web").map((item) => item.link || item.source)).size)} Internet`;
  const storage = report.internet_search?.storage || {};
  const searchResults = report.internet_search?.matches || [];
  const hiddenResults = searchResults.filter((item) => !item.stored && !item.candidate).length;
  const storageLines = [
    hiddenResults && hiddenResults === searchResults.length
      ? `Không có trang Internet nào trùng nguyên văn từ ${number(report.min_shared_words || 4)} từ liên tiếp trở lên với bài (${number(hiddenResults)} kết quả tìm kiếm chỉ cùng từ khóa) nên không có trang nào được lưu vào cơ sở dữ liệu.`
      : hiddenResults ? `${number(hiddenResults)} kết quả tìm kiếm chỉ cùng từ khóa, không có cụm trùng nguyên văn với bài, nên không được liệt kê.` : "",
    storage.new ? `Đã lưu ${number(storage.new)} trang Internet mới vào cơ sở dữ liệu để dùng cho các lần kiểm tra sau.` : "",
    storage.failed ? `${number(storage.failed)} trang Internet không tải được nên chỉ có đoạn trích kèm kết quả tìm kiếm.` : "",
    storage.skipped ? `${number(storage.skipped)} trang Internet chưa được lưu vì kho nguồn Internet đã đầy.` : "",
  ].filter(Boolean);
  const storageNote = storageLines.length ? `<p class="field-note web-note">${storageLines.map(escapeHtml).join(" ")}</p>` : "";
  const warningsHtml = (report.warnings || []).map((warning) => `<p class="warning-line">${escapeHtml(warning)}</p>`).join("");
  const maskNote = report.masked_sources ? `<p class="field-note mask-note">Tên tệp nguồn được thay bằng “Nguồn 1”, “Nguồn 2”… vì người dùng thường không truy cập kho tham chiếu. Đoạn trích vẫn hiển thị để bạn biết chỗ cần sửa.</p>` : "";
  const previewUrl = `/api/documents/${encodeURIComponent(report.document_id)}/preview#toolbar=0&navpanes=0`;

  // Văn bản đánh dấu: số cảnh báo chỉ gắn ở đoạn đầu của mỗi cảnh báo; nhãn mức chỉ hiện ở đầu một dải đoạn liên tiếp.
  const firstChunkOf = new Map(items.filter((item) => item.chunkIds.length).map((item) => [item.key, item.chunkIds[0]]));
  const markersByChunk = new Map();
  items.forEach((item) => { const id = firstChunkOf.get(item.key); if (id) markersByChunk.set(id, [...(markersByChunk.get(id) || []), item]); });
  const webChunkIds = new Set(items.filter((item) => item.kind === "web" && item.candidate).flatMap((item) => item.chunkIds));
  let previousFlagged = false;
  const documentHtml = chunks.map((chunk) => {
    const flagged = (chunk.alert_numbers || []).length > 0;
    const web = !flagged && webChunkIds.has(chunk.id);
    const level = severity(chunk.max_score || 0);
    const run = (flagged || web) && !previousFlagged;
    previousFlagged = flagged || web;
    const levelText = flagged ? level.label : (web ? "Có nguồn Internet nghi vấn" : "");
    const labelHtml = levelText ? (run ? `<span class="level">${levelText}</span> · ` : `<span class="sr-only">${levelText} · </span>`) : "";
    const marks = (markersByChunk.get(chunk.id) || []).filter((item) => item.kind === "internal" || item.candidate)
      .map((item) => `<button class="document-marker${item.kind === "web" ? " web-marker" : ""}" type="button" data-key="${item.key}" aria-label="Mở đối chiếu ${item.kind === "web" ? "nguồn Internet " : "cảnh báo "}${escapeHtml(item.no)}">${escapeHtml(item.no)}</button>`).join("");
    const keys = items.filter((item) => item.chunkIds.includes(chunk.id)).map((item) => item.key).join(" ");
    return `<section class="document-block${flagged ? ` severity-${level.key}` : ""}${web ? " is-web" : ""}${chunk.ignored ? " is-ignored" : ""}" id="doc-chunk-${escapeHtml(chunk.id)}" data-keys="${keys}" data-flagged="${flagged || web ? "1" : "0"}"><div class="document-location">${labelHtml}${escapeHtml(locationLabel(chunk.location || {}))}${chunk.ignored ? " · Đã loại khỏi đối chiếu" : ""}</div>${marks ? `<div class="document-marks">${marks}</div>` : ""}${renderBlockText(chunk)}</section>`;
  }).join("");

  $("#result").innerHTML = `<dl class="review-summary">${headline}<div><dt>Đoạn được cảnh báo</dt><dd>${number(report.matched_chunks)} / ${number(eligible)} đoạn<small>${escapeHtml(report.alert_label || method(report.engine))} · Ngưỡng ${number(report.threshold)}${report.min_shared_words ? ` · có cụm từ trùng từ ${report.min_shared_words} từ liên tiếp` : ""}</small><small>${levelSummary}</small></dd></div><div><dt>Nguồn đối chiếu</dt><dd>${sourceSummary}<small>${processingNote || thresholdNote}</small></dd></div></dl>${warningsHtml}${maskNote}${storageNote}
<div class="review-tabs" role="tablist" aria-label="Cách xem kết quả">
  <button class="tab" role="tab" id="tab-compare" aria-selected="true" aria-controls="panel-compare" type="button" data-tab="compare">Đối chiếu<span class="tab-count">${number(items.length)}</span></button>
  <button class="tab" role="tab" id="tab-marked" aria-selected="false" aria-controls="panel-marked" type="button" tabindex="-1" data-tab="marked">Văn bản đánh dấu</button>
  <button class="tab" role="tab" id="tab-original" aria-selected="false" aria-controls="panel-original" type="button" tabindex="-1" data-tab="original">Bản gốc</button>
</div>
<div class="compare" role="tabpanel" id="panel-compare" aria-labelledby="tab-compare">
  <section class="pane alert-pane" aria-label="Danh sách cảnh báo">
    <div class="alert-filters">
      <div class="field"><label for="flt-level">Mức trùng lặp</label><select id="flt-level"><option value="">Tất cả mức (${number(items.length)})</option><option value="high">Cao (${number(levelCount("high"))})</option><option value="medium">Trung bình (${number(levelCount("medium"))})</option><option value="low">Thấp (${number(levelCount("low"))})</option></select></div>
      <div class="field"><label for="flt-sort">Sắp xếp</label><select id="flt-sort"><option value="order">Theo vị trí trong báo cáo</option><option value="score">Điểm cao trước</option></select></div>
      <div class="field field-wide"><label for="flt-source">Nguồn</label><select id="flt-source">${sourceOptions}</select></div>
    </div>
    <div class="alert-summary"><span id="alert-count" aria-live="polite"></span><button class="link-button" id="flt-reset" type="button" hidden>Bỏ lọc</button></div>
    <ul class="alert-list" id="alert-list"></ul>
  </section>
  <section class="pane compare-pane" aria-label="Đối chiếu hai đoạn" id="compare-pane"></section>
</div>
<div class="pane marked-pane" role="tabpanel" id="panel-marked" aria-labelledby="tab-marked" hidden>
  <div class="marked-bar"><span>Mỗi số là một cảnh báo; bấm số để mở đối chiếu.</span><label class="check-row"><input type="checkbox" id="only-flagged"> Chỉ hiện đoạn bị cảnh báo</label></div>
  <div class="document-paper" tabindex="0" role="region" aria-label="Văn bản đánh dấu đoạn tương đồng"><div class="doc-inner">${documentHtml || '<p class="empty">Không có nội dung văn bản trong báo cáo cũ.</p>'}</div></div>
</div>
<div class="pane original-pane" role="tabpanel" id="panel-original" aria-labelledby="tab-original" hidden>
  <iframe class="document-preview" title="Bản gốc ${escapeHtml(report.filename)}" data-src="${previewUrl}"></iframe>
</div>`;
  applyFilters(true);
}

function filteredItems() {
  const level = $("#flt-level").value, source = $("#flt-source").value, sort = $("#flt-sort").value;
  let list = review.items.filter((item) => (!level || item.level.key === level)
    && (!source || (source === "web" ? (item.kind === "web" || item.fromWeb) : item.kind === "internal" && `in:${item.source}` === source)));
  if (sort === "score") list = [...list].sort((a, b) => b.score - a.score);
  return list;
}
function applyFilters(initial = false) {
  if (!review) return;
  review.filtered = filteredItems();
  const filtering = Boolean($("#flt-level").value || $("#flt-source").value);
  $("#flt-reset").hidden = !filtering;
  $("#alert-count").textContent = filtering ? `${number(review.filtered.length)} / ${number(review.items.length)} kết quả` : `${number(review.items.length)} kết quả`;
  $("#alert-list").innerHTML = review.filtered.length ? review.filtered.map((item) => {
    const meta = [item.method, item.count > 1 ? `${number(item.count)} đoạn liền nhau` : "", item.targetLoc].filter(Boolean).join(" · ");
    return `<li><button class="alert-item severity-${item.level.key}${item.kind === "web" ? " is-web" : ""}" type="button" data-key="${item.key}"><span class="ai-top"><span class="ai-no">${escapeHtml(item.no)}</span><span class="ai-level">${item.level.label}</span><span class="ai-score">${number(item.score * 100)}%</span></span><span class="ai-source">${escapeHtml(item.source)}</span>${item.link ? `<span class="ai-url">Trang web · ${escapeHtml(siteOf(item.link))}</span>` : ""}<span class="ai-meta">${escapeHtml(meta)}</span><span class="ai-excerpt">${escapeHtml(clip(item.sourceText || item.targetText))}</span></button></li>`;
  }).join("") : `<li class="empty">${review.items.length ? "Không có cảnh báo nào khớp bộ lọc." : "Không có đoạn nào vượt ngưỡng. Báo cáo không có cảnh báo."}</li>`;
  const keep = review.filtered.find((item) => item.key === review.activeKey);
  selectAlert((keep || review.filtered[0])?.key || null, {scroll: false});
}

function selectAlert(key, {scroll = true} = {}) {
  review.activeKey = key;
  $$("#alert-list .alert-item").forEach((button) => {
    if (button.dataset.key === key) { button.setAttribute("aria-current", "true"); if (scroll) button.scrollIntoView({block:"nearest"}); } else button.removeAttribute("aria-current");
  });
  $$(".document-block.is-active").forEach((block) => block.classList.remove("is-active"));
  $$(".document-block").filter((block) => (block.dataset.keys || "").split(" ").includes(key)).forEach((block) => block.classList.add("is-active"));
  renderCompare();
}
function renderCompare() {
  const pane = $("#compare-pane");
  const item = review.items.find((entry) => entry.key === review.activeKey);
  if (!item) { pane.innerHTML = `<div class="cmp-empty"><h3>Chưa chọn cảnh báo</h3><p>${review.items.length ? "Không có cảnh báo nào khớp bộ lọc hiện tại." : "Báo cáo này không có đoạn nào vượt ngưỡng nên không có gì để đối chiếu."}</p></div>`; return; }
  const position = review.filtered.findIndex((entry) => entry.key === item.key);
  const hidden = item.redacted || !item.sourceText;
  const pair = hidden ? null : comparePair(item.targetText, item.sourceText);
  const semantic = item.kind === "internal" && review.report.engine === "semantic";
  let metric;
  if (hidden) metric = "Bạn không có quyền xem nội dung của nguồn này nên chỉ xem được đoạn trong báo cáo.";
  else {
    metric = `Trùng nguyên văn <strong>${number(pair.shared)} / ${number(pair.total)} từ (${pair.percent}%)</strong> của đoạn trong báo cáo · ${escapeHtml(item.method)}, điểm ${number(item.score * 100)}%.`;
  }
  let note = "";
  if (pair && item.kind === "internal" && semantic && pair.percent < 25) note = "Điểm cao nhưng ít cụm từ trùng nguyên văn: đây thường là đoạn diễn đạt lại cùng ý. Hãy đọc cả hai đoạn để quyết định.";
  else if (pair && pair.n < SHARED_MIN_WORDS && pair.n > 0) note = `Đoạn rất ngắn (${number(pair.n)} từ) nên cụm từ trùng được tô ngắn hơn ${SHARED_MIN_WORDS} từ.`;
  else if (pair && pair.percent === 0) note = `Không có cụm từ nào trùng từ ${SHARED_MIN_WORDS} từ liên tiếp trở lên; mức tương đồng đến từ các từ riêng lẻ.`;
  else if (item.kind === "web") note = `${item.fetchError ? `Chưa lưu được trang này (${item.fetchError}) nên chỉ có đoạn trích.` : "Đoạn trích Internet chỉ là phần ngắn kèm kết quả tìm kiếm."} Có thể chưa đủ để kết luận; hãy mở nguồn để đọc nguyên bản.`;
  else if (item.fromWeb) note = "So khớp với bản toàn văn của trang web được lưu lúc kiểm tra. Trang gốc có thể đã thay đổi sau đó; hãy mở trang gốc nếu cần xác minh.";
  const link = (item.kind === "web" || item.fromWeb) && item.link ? `<a class="button secondary" href="${escapeHtml(item.link)}" target="_blank" rel="noopener noreferrer">Mở trang gốc<span class="sr-only"> (mở tab mới)</span></a>`
    : (item.sourceId ? `<a class="button secondary" href="/api/documents/${encodeURIComponent(item.sourceId)}/file">Tải nguồn<span class="sr-only"> ${escapeHtml(item.source)}</span></a>` : "");
  pane.innerHTML = `<header class="cmp-head"><div><h3>Cảnh báo ${escapeHtml(item.no)}<span class="level">${item.level.label}</span></h3><p>${escapeHtml(item.source)}</p>${item.link ? `<p class="cmp-url"><a href="${escapeHtml(item.link)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.link)}<span class="sr-only"> (mở tab mới)</span></a></p>` : ""}</div><div class="cmp-nav"><button class="button secondary" type="button" data-step="-1"${position <= 0 ? " disabled" : ""}>Trước</button><span class="pos" aria-live="polite">${position + 1} / ${review.filtered.length}</span><button class="button secondary" type="button" data-step="1"${position >= review.filtered.length - 1 ? " disabled" : ""}>Sau</button></div></header>
<div class="cmp-body"><p class="cmp-metric">${metric}</p>${note ? `<p class="cmp-note">${note}</p>` : ""}
<div class="cmp-cols"><div class="cmp-col"><h4>Đoạn trong báo cáo</h4><p class="cmp-loc">${escapeHtml(item.targetLoc || "—")}</p><div class="cmp-text">${pair ? pair.targetHtml : escapeHtml(item.targetText)}</div></div>
<div class="cmp-col"><h4>${escapeHtml(item.kind === "web" ? "Đoạn trích từ Internet" : (item.fromWeb ? "Đoạn trong trang Internet (bản đã lưu)" : "Đoạn trong nguồn"))}</h4><p class="cmp-loc">${escapeHtml(item.sourceLoc || "—")}</p><div class="cmp-text${hidden ? " is-hidden" : ""}">${hidden ? "Nội dung nguồn không hiển thị với tài khoản của bạn." : pair.sourceHtml}</div></div></div></div>
<footer class="cmp-foot"><button class="button secondary" type="button" data-locate="${item.key}"${item.chunkIds.length ? "" : " disabled"}>Xem vị trí trong văn bản</button>${link}<span class="legend"><mark>Cụm từ</mark> trùng nguyên văn từ ${SHARED_MIN_WORDS} từ liên tiếp</span></footer>`;
}
function stepAlert(delta) {
  const index = review.filtered.findIndex((item) => item.key === review.activeKey) + delta;
  if (index >= 0 && index < review.filtered.length) selectAlert(review.filtered[index].key);
}
function selectTab(name, focus = false) {
  $$(".review-tabs [role=tab]").forEach((tab) => {
    const on = tab.dataset.tab === name;
    tab.setAttribute("aria-selected", String(on)); tab.tabIndex = on ? 0 : -1;
    if (on && focus) tab.focus();
  });
  ["compare", "marked", "original"].forEach((id) => { const panel = $(`#panel-${id}`); if (panel) panel.hidden = id !== name; });
  if (name === "original") { const frame = $(".document-preview"); if (frame && !frame.getAttribute("src")) frame.setAttribute("src", frame.dataset.src); }  // chỉ tải bản gốc khi mở tab
}
function locate(key) {
  selectTab("marked");
  const block = $$(".document-block").find((item) => (item.dataset.keys || "").split(" ").includes(key));
  block?.scrollIntoView({block:"center"});
}

// ------------------------------------------------------------------ sự kiện: kết quả
$("#result").addEventListener("click", (event) => {
  const tab = event.target.closest("[role=tab]");
  if (tab) { selectTab(tab.dataset.tab); return; }
  const item = event.target.closest(".alert-item");
  if (item) {
    selectAlert(item.dataset.key, {scroll: false});
    // Màn hẹp: khung đối chiếu nằm dưới danh sách, đưa nó vào tầm nhìn.
    if (matchMedia("(max-width: 960px)").matches) $("#compare-pane").scrollIntoView({block:"start"});
    return;
  }
  const marker = event.target.closest(".document-marker");
  if (marker) { selectTab("compare"); if (!review.filtered.some((entry) => entry.key === marker.dataset.key)) { $("#flt-level").value = ""; $("#flt-source").value = ""; applyFilters(); } selectAlert(marker.dataset.key); $("#compare-pane").scrollIntoView({block:"nearest"}); return; }
  const step = event.target.closest("[data-step]");
  if (step) { stepAlert(Number(step.dataset.step)); return; }
  const locator = event.target.closest("[data-locate]");
  if (locator) { locate(locator.dataset.locate); return; }
  if (event.target.closest("#flt-reset")) { $("#flt-level").value = ""; $("#flt-source").value = ""; applyFilters(); }
});
$("#result").addEventListener("change", (event) => {
  if (event.target.matches("#flt-level, #flt-source, #flt-sort")) applyFilters();
  if (event.target.matches("#only-flagged")) $$(".document-block").forEach((block) => { block.hidden = event.target.checked && block.dataset.flagged !== "1"; });
});
$("#result").addEventListener("keydown", (event) => {
  const tab = event.target.closest("[role=tab]");
  if (tab) {
    const tabs = $$(".review-tabs [role=tab]"); let index = tabs.indexOf(tab);
    if (event.key === "ArrowRight") index = (index + 1) % tabs.length;
    else if (event.key === "ArrowLeft") index = (index - 1 + tabs.length) % tabs.length;
    else if (event.key === "Home") index = 0; else if (event.key === "End") index = tabs.length - 1; else return;
    event.preventDefault(); selectTab(tabs[index].dataset.tab, true);
  }
});
$("#export").addEventListener("click", () => {
  if (!lastReport) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(lastReport, null, 2)], {type:"application/json;charset=utf-8"}));
  const anchor = document.createElement("a"); anchor.href = url; anchor.download = `ket-qua-${lastReport.id}.json`; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

// ------------------------------------------------------------------ tải tệp
function validateSelection(file) {
  if (!file) throw new Error("Vui lòng chọn một tài liệu.");
  if (!/\.(pdf|docx)$/i.test(file.name)) throw new Error("Chỉ hỗ trợ PDF và DOCX.");
  if (!file.size) throw new Error("Tệp đang chọn rỗng.");
  if (file.size > maxUploadMB * 1024 * 1024) throw new Error(`Tệp vượt giới hạn ${maxUploadMB} MB.`);
}
$("#check-file").addEventListener("change", () => {
  const file = $("#check-file").files[0];
  $("#file-label").textContent = file ? file.name : "Chọn hoặc kéo thả báo cáo vào đây";
  $("#file-hint").textContent = file ? `${number(file.size / 1024)} KB · bấm để đổi tệp` : `PDF hoặc DOCX, tối đa ${maxUploadMB} MB`;
  controls();
});
$("#reference-file").addEventListener("change", () => {
  const file = $("#reference-file").files[0];
  $("#reference-file-name").textContent = file ? `${file.name} (${number(file.size / 1024)} KB)` : "Chưa chọn tệp (PDF hoặc DOCX)";
  controls();
});
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
    $("#reference-form").reset(); $("#reference-file").dispatchEvent(new Event("change"));
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
    $("#result-title").setAttribute("tabindex", "-1"); $("#result-title").focus({preventScroll:true});
  } catch (error) { notify(error.message, true); }
  finally { busy = false; controls(); }
});
$("#web-list").addEventListener("click", async (e) => {
  const button = e.target.closest(".web-delete");
  if (!button) return;
  if (!window.confirm(`Xóa nguồn Internet “${button.dataset.title}” khỏi cơ sở dữ liệu? Các báo cáo đã tạo không bị ảnh hưởng.`)) return;
  try { await api(`/api/documents/${encodeURIComponent(button.dataset.id)}`, {method:"DELETE"}); notify("Đã xóa nguồn Internet."); await refresh(); }
  catch (error) { notify(error.message, true); }
});
$("#history").addEventListener("click", async (e) => {
  const button = e.target.closest(".history-open");
  if (!button || busy) return;
  try {
    renderReport(await api(`/api/checks/${encodeURIComponent(button.dataset.id)}`));
    goTo("#kiem-tra", $("#result-section"));
  }
  catch (error) { notify(error.message, true); }
});

// ------------------------------------------------------------------ đăng nhập, đăng ký, đăng xuất, mật khẩu
document.addEventListener("change", (event) => {
  const toggle = event.target.closest(".show-password");
  if (!toggle) return;
  $$(toggle.dataset.targets).forEach((input) => { input.type = toggle.checked ? "text" : "password"; input.classList.add("was-password"); });
});
async function enterApp() {
  history.replaceState(null, "", "#kiem-tra");  // không để "Quay lại" đưa về trang đăng nhập
  await refresh();
  if (currentUser) $("#title-check").focus({preventScroll:true});
}
$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("#login-error").textContent = "";
  $("#login-button").disabled = true;
  try {
    await api("/api/auth/login", jsonBody("POST", {email: $("#login-email").value, password: $("#login-password").value}));
    $("#login-form").reset(); $("#login-password").type = "password";
    await enterApp();
  } catch (error) { $("#login-error").textContent = error.message; }
  finally { $("#login-button").disabled = false; }
});
$("#register-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("#register-error").textContent = "";
  if ($("#reg-password").value !== $("#reg-confirm").value) { $("#register-error").textContent = "Hai mật khẩu nhập chưa giống nhau."; $("#reg-confirm").focus(); return; }
  $("#register-button").disabled = true;
  try {
    await api("/api/auth/register", jsonBody("POST", {full_name: $("#reg-name").value, email: $("#reg-email").value, password: $("#reg-password").value}));
    $("#register-form").reset();
    await enterApp();
    if (currentUser) notify("Đã tạo tài khoản. Bạn chỉ xem được bài kiểm tra của chính mình.");
  } catch (error) { $("#register-error").textContent = error.message; }
  finally { $("#register-button").disabled = false; }
});
$("#logout").addEventListener("click", async () => {
  await fetch("/api/auth/logout", {method:"POST"}).catch(() => {});
  currentUser = null; clearData();
  if (location.hash === "#trang-chu") route(true); else location.hash = "#trang-chu";  // đăng xuất trở về trang chủ (hashchange gọi route)
});
$("#password-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("#password-error").textContent = ""; $("#password-ok").textContent = "";
  if ($("#pw-new").value !== $("#pw-confirm").value) { $("#password-error").textContent = "Hai mật khẩu mới nhập chưa giống nhau."; $("#pw-confirm").focus(); return; }
  $("#password-button").disabled = true;
  try {
    const result = await api("/api/auth/password", jsonBody("POST", {current_password: $("#pw-current").value, new_password: $("#pw-new").value}));
    $("#password-form").reset(); $$("#password-form input").forEach((input) => { input.type = input.classList.contains("show-password") ? "checkbox" : "password"; });
    $("#password-ok").textContent = result.detail;
  } catch (error) { if (!error.auth) $("#password-error").textContent = error.message; }
  finally { $("#password-button").disabled = false; }
});

// ------------------------------------------------------------------ quản trị
$("#user-form").addEventListener("submit", (e) => {
  e.preventDefault();
  adminAction(async () => {
    await api("/api/users", jsonBody("POST", {email: $("#new-email").value, full_name: $("#new-name").value, password: $("#new-password").value, role: $("#new-role").value}));
    $("#user-form").reset();
  }, "Đã tạo tài khoản.");
});
$("#reset-form").addEventListener("submit", (e) => {
  e.preventDefault();
  if (!$("#reset-user").value) return;
  adminAction(async () => {
    await api(`/api/users/${encodeURIComponent($("#reset-user").value)}`, jsonBody("PATCH", {password: $("#reset-password").value}));
    $("#reset-password").value = "";
  }, "Đã đặt lại mật khẩu. Người dùng đó bị đăng xuất và cần dùng mật khẩu mới.");
});
$("#user-table").addEventListener("change", (e) => {
  const select = e.target.closest(".role-select");
  if (select) adminAction(() => api(`/api/users/${encodeURIComponent(select.dataset.id)}`, jsonBody("PATCH", {role: select.value})), "Đã đổi vai trò. Người dùng đó cần đăng nhập lại.");
});
$("#user-table").addEventListener("click", (e) => {
  const button = e.target.closest(".toggle-active");
  if (button) adminAction(() => api(`/api/users/${encodeURIComponent(button.dataset.id)}`, jsonBody("PATCH", {is_active: button.dataset.active !== "true"})), "Đã cập nhật trạng thái tài khoản.");
});
// Vùng bảng cuộn ngang phải focus được bằng bàn phím (WCAG 2.1.1) và có tên cho trình đọc màn hình.
$$(".table-scroll").forEach((box) => {
  box.tabIndex = 0; box.setAttribute("role", "region");
  box.setAttribute("aria-label", box.querySelector("caption")?.textContent.trim() || "Bảng dữ liệu");
});
$("#refresh").addEventListener("click", refresh);
refresh();
