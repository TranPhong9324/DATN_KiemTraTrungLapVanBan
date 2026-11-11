export async function api(url, options = {}) {
  let response;
  try { response = await fetch(url, options); }
  catch { throw new Error('Không liên lạc được với web. Kiểm tra máy chủ và thử lại.'); }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(body.detail) ? body.detail.map(item => item.msg).join('; ') : body.detail;
    throw new Error(detail || `Yêu cầu thất bại (${response.status}).`);
  }
  return body;
}
export function validateSelection(file, maxUploadMB) {
  if (!file) throw new Error('Vui lòng chọn một tài liệu.');
  if (!/\.(pdf|docx)$/i.test(file.name)) throw new Error('Chỉ hỗ trợ PDF và DOCX.');
  if (!file.size) throw new Error('Tệp đang chọn rỗng.');
  if (file.size > maxUploadMB * 1024 * 1024) throw new Error(`Tệp vượt giới hạn ${maxUploadMB} MB.`);
}
