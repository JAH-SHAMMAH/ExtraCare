/** Shrink a phone photo before upload: max 1600px, JPEG. Phone cameras produce
 *  5–10 MB files (over the server's 5 MB cap) and sometimes HEIC; re-encoding
 *  fixes both. Falls back to the original file if the browser can't decode it. */
const MAX_EDGE = 1600;
const KEEP_AS_IS = 1_000_000;

export async function prepareImage(file: File): Promise<File> {
  try {
    if (typeof document === "undefined" || !file.type.startsWith("image/") || file.type === "image/gif") return file;
    if (file.size <= KEEP_AS_IS && /^image\/(jpeg|png|webp)$/.test(file.type)) return file;
    const bmp = await createImageBitmap(file);
    const scale = Math.min(1, MAX_EDGE / Math.max(bmp.width, bmp.height));
    const w = Math.max(1, Math.round(bmp.width * scale));
    const h = Math.max(1, Math.round(bmp.height * scale));
    const canvas = document.createElement("canvas");
    canvas.width = w; canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) return file;
    ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, w, h);
    ctx.drawImage(bmp, 0, 0, w, h);
    const blob: Blob | null = await new Promise((res) => canvas.toBlob(res, "image/jpeg", 0.85));
    if (!blob || blob.size >= file.size && /^image\/(jpeg|png|webp)$/.test(file.type)) return file;
    return new File([blob], file.name.replace(/\.[^.]+$/, "") + ".jpg", { type: "image/jpeg" });
  } catch {
    return file;
  }
}

/** Give an upload error a readable `response.data.detail` when the server sent none. */
export function explainUploadError(err: any): never {
  const status = err?.response?.status;
  if (!err?.response?.data?.detail) {
    const detail =
      !err?.response ? "Couldn't reach the server. Check your connection and try again."
      : status === 413 ? "That photo is too large. Try a smaller one."
      : status >= 500 ? "The server couldn't save the photo. Please try again, and tell the administrator if it keeps happening."
      : `Upload failed (HTTP ${status}).`;
    err.response = { ...(err.response || {}), data: { detail } };
  }
  throw err;
}
