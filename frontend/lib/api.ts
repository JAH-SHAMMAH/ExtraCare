import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from "axios";
import Cookies from "js-cookie";
import { env } from "./env";

const API_URL = env.NEXT_PUBLIC_API_URL;

// Cookie-auth mode (Priority 2 rollout). When NEXT_PUBLIC_COOKIE_AUTH=true the
// backend issues httpOnly access/refresh cookies + a readable csrf_token; the
// client stops persisting tokens in JS, authenticates via the cookie
// (withCredentials), and echoes the CSRF token on mutations. Default false =
// Bearer-token mode (unchanged) so rollout is coordinated + reversible.
const COOKIE_AUTH = process.env.NEXT_PUBLIC_COOKIE_AUTH === "true";

export const api: AxiosInstance = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
  timeout: 30_000,
  // Send cookies on cross-origin requests (CORS allow_credentials is enabled
  // server-side). Harmless in Bearer mode; required for cookie auth.
  withCredentials: true,
});

// ── Request interceptor: attach auth + org slug ───────────────────────────────
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (!COOKIE_AUTH) {
    // Bearer mode: attach the JS-readable access token.
    const token = Cookies.get("access_token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
  } else {
    // Cookie mode: the httpOnly access cookie authenticates via withCredentials.
    // Echo the CSRF token (double-submit) on state-changing requests.
    const method = (config.method || "get").toLowerCase();
    if (method === "post" || method === "put" || method === "patch" || method === "delete") {
      const csrf = Cookies.get("csrf_token");
      if (csrf) config.headers["X-CSRF-Token"] = csrf;
    }
  }

  const orgSlug = Cookies.get("org_slug");
  if (orgSlug) config.headers["X-Org-Slug"] = orgSlug;

  return config;
});

// ── Response interceptor: auto-refresh on 401 ────────────────────────────────
let isRefreshing = false;
let failedQueue: Array<{ resolve: (v: unknown) => void; reject: (e: unknown) => void }> = [];

function processQueue(error: Error | null, token: string | null = null) {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error);
    else resolve(token);
  });
  failedQueue = [];
}

// Surface slow API calls while the perf flag is on. The backend stamps
// every response with X-Response-Time; when it crosses 300ms we echo it to
// the console so a developer watching "why does this page feel slow?" can
// see which endpoint is actually the culprit without opening the Network
// panel. Toggle via localStorage.setItem("ec:perf", "1") (same flag as
// nav timing).
api.interceptors.response.use((res) => {
  try {
    if (typeof window !== "undefined" && window.localStorage.getItem("ec:perf") === "1") {
      const header = res.headers?.["x-response-time"];
      const ms = typeof header === "string" ? parseFloat(header) : NaN;
      if (!Number.isNaN(ms) && ms > 300) {
        // eslint-disable-next-line no-console
        console.warn(`[perf] slow api ${res.config.method?.toUpperCase()} ${res.config.url}: ${ms.toFixed(0)}ms`);
      }
    }
  } catch {
    // Perf logging must never throw into the app.
  }
  return res;
});

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status === 401 && !original._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          original.headers.Authorization = `Bearer ${token}`;
          return api(original);
        });
      }

      original._retry = true;
      isRefreshing = true;

      try {
        if (COOKIE_AUTH) {
          // Refresh token rides in the httpOnly cookie — send no body. The
          // backend rotates + re-issues the cookies on the response.
          await axios.post(`${API_URL}/api/v1/auth/refresh`, {}, { withCredentials: true });
          processQueue(null, "cookie");
          return api(original);
        }

        const refreshToken = Cookies.get("refresh_token");
        if (!refreshToken) {
          isRefreshing = false;
          clearAuth();
          window.location.href = "/login";
          return Promise.reject(error);
        }
        const { data } = await axios.post(`${API_URL}/api/v1/auth/refresh`, {
          refresh_token: refreshToken,
        });
        setAuth(data.access_token, data.refresh_token);
        processQueue(null, data.access_token);
        original.headers.Authorization = `Bearer ${data.access_token}`;
        return api(original);
      } catch (refreshError) {
        processQueue(refreshError as Error, null);
        clearAuth();
        window.location.href = "/login";
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export function setAuth(accessToken: string, refreshToken: string, orgSlug?: string) {
  // Cookie mode: the backend sets httpOnly access/refresh cookies — never
  // persist tokens in JS-readable storage. Only the (non-secret) org slug is
  // kept client-side for the X-Org-Slug header.
  if (!COOKIE_AUTH) {
    // Secure must match the actual protocol: browsers drop `secure` cookies over
    // plain HTTP on a non-localhost host (e.g. a phone hitting the LAN IP), which
    // would silently lose the session right after login. HTTPS in prod → secure.
    const secure = typeof window !== "undefined" && window.location.protocol === "https:";
    Cookies.set("access_token", accessToken, { expires: 1, secure, sameSite: "strict" });
    Cookies.set("refresh_token", refreshToken, { expires: 7, secure, sameSite: "strict" });
  }
  if (orgSlug) Cookies.set("org_slug", orgSlug, { expires: 30 });
}

export function clearAuth() {
  Cookies.remove("access_token");
  Cookies.remove("refresh_token");
  Cookies.remove("org_slug");
}

// ── Typed API helpers ─────────────────────────────────────────────────────────

export const authApi = {
  // org_slug is optional: in single-school mode the server resolves the one
  // organisation; it's only sent by multi-tenant deployments.
  login: (data: { email: string; password: string; org_slug?: string }) =>
    api.post("/auth/login", data).then((r) => r.data),

  register: (data: {
    org_name: string; org_slug: string; industry: string;
    admin_name: string; admin_email: string; password: string;
  }) => api.post("/auth/register", data).then((r) => r.data),

  me: () => api.get("/auth/me").then((r) => r.data),
  changePassword: (data: { current_password: string; new_password: string }) =>
    api.post("/auth/change-password", data).then((r) => r.data),
  logout: async () => {
    // Cookie mode: hit the server so it can clear the httpOnly cookies (JS
    // can't). Best-effort — local state is cleared regardless.
    if (COOKIE_AUTH) {
      try { await api.post("/auth/logout"); } catch { /* ignore */ }
    }
    clearAuth();
  },
};

export const usersApi = {
  list: (params?: { page?: number; page_size?: number; search?: string; status?: string }) =>
    api.get("/users", { params }).then((r) => r.data),
  get: (id: string) => api.get(`/users/${id}`).then((r) => r.data),
  // All non-teaching staff + admins (no 100-row cap; server-side filtered).
  staff: (params?: { search?: string }) => api.get("/users/staff", { params }).then((r) => r.data),
  listRoles: () => api.get("/users/roles/available").then((r) => r.data),
  create: (data: object) => api.post("/users", data).then((r) => r.data),
  update: (id: string, data: object) => api.patch(`/users/${id}`, data).then((r) => r.data),
  updateStatus: (id: string, status: string) => api.patch(`/users/${id}/status`, { status }).then((r) => r.data),
  assignRoles: (id: string, role_ids: string[]) => api.patch(`/users/${id}/roles`, role_ids).then((r) => r.data),
  invite: (data: object) => api.post("/users/invite", data).then((r) => r.data),
  resetPassword: (id: string) => api.post(`/users/${id}/reset-password`).then((r) => r.data),
  delete: (id: string) => api.delete(`/users/${id}`),
};

export const analyticsApi = {
  overview: () => api.get("/analytics/overview").then((r) => r.data),
  activityFeed: (limit = 20) => api.get("/analytics/activity-feed", { params: { limit } }).then((r) => r.data),
  // Immutable audit trail — gated by audit_logs:read (org_admin), unlike the
  // broader activity feed. Used by the Audit Log page only.
  auditLog: (limit = 100) => api.get("/analytics/audit-log", { params: { limit } }).then((r) => r.data),
};

export const paymentsApi = {
  initialize: (data: { target_tier: "pro" | "enterprise"; email?: string }) =>
    api.post("/payments/initialize", data).then((r) => r.data),
  verify: (reference: string) =>
    api.get(`/payments/verify/${reference}`).then((r) => r.data),
  config: () => api.get("/payments/config").then((r) => r.data),
};

// ── School API ───────────────────────────────────────────────────────────────

export const schoolApi = {
  students: {
    list: (p?: object) => api.get("/school/students", { params: p }).then((r) => r.data),
    get: (id: string) => api.get(`/school/students/${id}`).then((r) => r.data),
    create: (data: object) => api.post("/school/students", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/school/students/${id}`, data).then((r) => r.data),
    delete: (id: string) => api.delete(`/school/students/${id}`),
  },
  teachers: {
    list: (p?: object) => api.get("/school/teachers", { params: p }).then((r) => r.data),
    get: (id: string) => api.get(`/school/teachers/${id}`).then((r) => r.data),
    create: (data: object) => api.post("/school/teachers", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/school/teachers/${id}`, data).then((r) => r.data),
    delete: (id: string) => api.delete(`/school/teachers/${id}`),
  },
  classes: {
    list: (p?: object) => api.get("/school/classes", { params: p }).then((r) => r.data),
    get: (id: string) => api.get(`/school/classes/${id}`).then((r) => r.data),
    create: (data: object) => api.post("/school/classes", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/school/classes/${id}`, data).then((r) => r.data),
    delete: (id: string) => api.delete(`/school/classes/${id}`),
  },
  subjects: {
    list: (p?: object) => api.get("/school/subjects", { params: p }).then((r) => r.data),
    get: (id: string) => api.get(`/school/subjects/${id}`).then((r) => r.data),
    create: (data: object) => api.post("/school/subjects", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/school/subjects/${id}`, data).then((r) => r.data),
    delete: (id: string) => api.delete(`/school/subjects/${id}`),
  },
  exams: {
    list: (p?: object) => api.get("/school/exams", { params: p }).then((r) => r.data),
    get: (id: string) => api.get(`/school/exams/${id}`).then((r) => r.data),
    create: (data: object) => api.post("/school/exams", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/school/exams/${id}`, data).then((r) => r.data),
    results: (exam_id: string) => api.get(`/school/exams/${exam_id}/results`).then((r) => r.data),
    submitResults: (exam_id: string, results: object[]) => api.post(`/school/exams/${exam_id}/results`, results).then((r) => r.data),
  },
  // Fees moved to financeApi.feeRecords (/finance/fee-records) — /school/fees was never built.
  attendance: {
    list: (p?: object) => api.get("/school/attendance", { params: p }).then((r) => r.data),
    mark: (records: object[], date?: string) => api.post("/school/attendance", records, { params: { attendance_date: date } }).then((r) => r.data),
    summary: (class_id: string, start_date: string, end_date: string) =>
      api.get("/school/attendance/summary", { params: { class_id, start_date, end_date } }).then((r) => r.data),
    studentHistory: (student_id: string, start_date?: string, end_date?: string) =>
      api.get(`/school/attendance/student/${student_id}`, { params: { start_date, end_date } }).then((r) => r.data),
    settings: {
      get: () => api.get("/school/attendance/settings").then((r) => r.data),
      update: (data: object) => api.put("/school/attendance/settings", data).then((r) => r.data),
    },
    reasons: {
      list: (activeOnly?: boolean) => api.get("/school/attendance/reasons", { params: { active_only: activeOnly } }).then((r) => r.data),
      create: (data: object) => api.post("/school/attendance/reasons", data).then((r) => r.data),
      update: (id: string, data: object) => api.patch(`/school/attendance/reasons/${id}`, data).then((r) => r.data),
      remove: (id: string) => api.delete(`/school/attendance/reasons/${id}`),
    },
  },
  timetable: {
    list: (p?: object) => api.get("/school/timetable", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/school/timetable", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/school/timetable/${id}`, data).then((r) => r.data),
    delete: (id: string) => api.delete(`/school/timetable/${id}`),
  },
  ratings: {
    list: (p?: object) => api.get("/school/ratings", { params: p }).then((r) => r.data),
    submit: (data: object) => api.post("/school/ratings", data).then((r) => r.data),
    teacherAverage: (teacher_id: string) => api.get(`/school/ratings/teacher/${teacher_id}`).then((r) => r.data),
  },
  grades: {
    submit: (grades: object[]) => api.post("/school/grades", grades).then((r) => r.data),
    reportCard: (student_id: string, term?: string) => api.get(`/school/students/${student_id}/report-card`, { params: { term } }).then((r) => r.data),
    publishStatus: (params: { term: string; class_id?: string; exam_id?: string; subject_id?: string }) =>
      api.get("/school/grades/publish-status", { params }).then((r) => r.data),
    publish: (data: { term: string; status: "published" | "draft"; class_id?: string; exam_id?: string; subject_id?: string }) =>
      api.post("/school/grades/publish", data).then((r) => r.data),
  },
  // Library (Phase 6.5). Routes live under /library/* — separate router.
  library: {
    books: {
      list: (p?: { search?: string; category?: string; available_only?: boolean; page?: number; page_size?: number }) =>
        api.get("/library/books", { params: p }).then((r) => r.data),
      create: (data: object) => api.post("/library/books", data).then((r) => r.data),
      update: (id: string, data: object) => api.patch(`/library/books/${id}`, data).then((r) => r.data),
      remove: (id: string) => api.delete(`/library/books/${id}`),
    },
    loans: {
      list: (p?: { status?: "borrowed" | "returned" | "overdue"; borrower_user_id?: string; book_id?: string; page?: number; page_size?: number }) =>
        api.get("/library/loans", { params: p }).then((r) => r.data),
      mine: () => api.get("/library/loans/mine").then((r) => r.data),
      issue: (data: { book_id: string; borrower_user_id: string; due_date: string; notes?: string }) =>
        api.post("/library/loans", data).then((r) => r.data),
      returnLoan: (id: string) => api.post(`/library/loans/${id}/return`).then((r) => r.data),
    },
    stats: () => api.get("/library/stats").then((r) => r.data),
  },
  // Lesson Planner (Phase 6.4). Teachers own their plans server-side; the
  // `mine` param is a convenience for admins to scope to their own view.
  lessons: {
    list: (p?: {
      class_id?: string;
      subject_id?: string;
      teacher_id?: string;
      start_date?: string;
      end_date?: string;
      status?: "draft" | "published";
      mine?: boolean;
    }) => api.get("/school/lessons", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/school/lessons", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/school/lessons/${id}`, data).then((r) => r.data),
    publish: (id: string) => api.post(`/school/lessons/${id}/publish`).then((r) => r.data),
    remove: (id: string) => api.delete(`/school/lessons/${id}`),
  },
};

// ── School Experience Layer ──────────────────────────────────────────────────
//
// Mirrors /api/v1/classroom, /cbt, /behaviour, /feedback, /clubs, /journals,
// /tuckshop plus the extended /school/timetable + /school/attendance/student
// endpoints. Each module is grouped into its own export for tree-shaking and
// to keep call sites readable (e.g. `classroomApi.assignments.list(...)`).

export const classroomApi = {
  assignments: {
    list: (p?: object) => api.get("/classroom/assignments", { params: p }).then((r) => r.data),
    get: (id: string) => api.get(`/classroom/assignments/${id}`).then((r) => r.data),
    create: (data: object) => api.post("/classroom/assignments", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/classroom/assignments/${id}`, data).then((r) => r.data),
    delete: (id: string) => api.delete(`/classroom/assignments/${id}`),
    submissions: (id: string) => api.get(`/classroom/assignments/${id}/submissions`).then((r) => r.data),
  },
  submissions: {
    create: (data: object) => api.post("/classroom/submissions", data).then((r) => r.data),
    grade: (id: string, data: { score: number; feedback?: string }) =>
      api.patch(`/classroom/submissions/${id}/grade`, data).then((r) => r.data),
    mine: (student_id: string) => api.get("/classroom/my-submissions", { params: { student_id } }).then((r) => r.data),
  },
  reflections: {
    list: (p?: object) => api.get("/classroom/reflections", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/classroom/reflections", data).then((r) => r.data),
    comment: (id: string, teacher_comment: string) =>
      api.patch(`/classroom/reflections/${id}/comment`, { teacher_comment }).then((r) => r.data),
  },
};

export const cbtApi = {
  exams: {
    list: (p?: object) => api.get("/cbt/exams", { params: p }).then((r) => r.data),
    get: (id: string) => api.get(`/cbt/exams/${id}`).then((r) => r.data),
    create: (data: object) => api.post("/cbt/exams", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/cbt/exams/${id}`, data).then((r) => r.data),
    delete: (id: string) => api.delete(`/cbt/exams/${id}`),
  },
  questions: {
    list: (exam_id: string, include_answers = false) =>
      api.get(`/cbt/exams/${exam_id}/questions`, { params: { include_answers } }).then((r) => r.data),
    add: (exam_id: string, data: object) =>
      api.post(`/cbt/exams/${exam_id}/questions`, data).then((r) => r.data),
    delete: (question_id: string) => api.delete(`/cbt/questions/${question_id}`),
    addFromBank: (exam_id: string, question_ids: string[]) =>
      api.post(`/cbt/exams/${exam_id}/questions/from-bank`, { question_ids }).then((r) => r.data),
  },
  bank: {
    list: (p?: { subject_id?: string; topic?: string; difficulty?: string; question_type?: string; search?: string; page?: number; page_size?: number }) =>
      api.get("/cbt/question-bank", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/cbt/question-bank", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/cbt/question-bank/${id}`, data).then((r) => r.data),
    delete: (id: string) => api.delete(`/cbt/question-bank/${id}`),
    import: (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return api.post("/cbt/question-bank/import", fd, { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data);
    },
  },
  attempts: {
    list: (p?: { exam_id?: string; student_id?: string }) =>
      api.get("/cbt/attempts", { params: p }).then((r) => r.data),
    get: (id: string) => api.get(`/cbt/attempts/${id}`).then((r) => r.data),
    start: (exam_id: string, student_id: string) =>
      api.post(`/cbt/exams/${exam_id}/attempts`, null, { params: { student_id } }).then((r) => r.data),
    submit: (attempt_id: string, answers: Array<{ question_id: string; answer_text: string }>) =>
      api.post(`/cbt/attempts/${attempt_id}/submit`, { answers }).then((r) => r.data),
    review: (id: string) => api.get(`/cbt/attempts/${id}/review`).then((r) => r.data),
    remark: (id: string, items: Array<{ answer_id: string; points_awarded: number }>) =>
      api.post(`/cbt/attempts/${id}/remark`, items).then((r) => r.data),
    reset: (id: string) => api.post(`/cbt/attempts/${id}/reset`).then((r) => r.data),
  },
  results: {
    get: (exam_id: string) => api.get(`/cbt/exams/${exam_id}/results`).then((r) => r.data),
    exportCsv: (exam_id: string) =>
      api.get(`/cbt/exams/${exam_id}/results/export`, { responseType: "blob" }).then((r) => r.data as Blob),
    publish: (exam_id: string) => api.post(`/cbt/exams/${exam_id}/publish-results`).then((r) => r.data),
    unpublish: (exam_id: string) => api.post(`/cbt/exams/${exam_id}/unpublish-results`).then((r) => r.data),
    feedGradebook: (exam_id: string) => api.post(`/cbt/exams/${exam_id}/feed-gradebook`).then((r) => r.data),
  },
  interventions: {
    list: (p?: { status?: string; student_id?: string; exam_id?: string }) =>
      api.get("/cbt/interventions", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/cbt/interventions", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/cbt/interventions/${id}`, data).then((r) => r.data),
  },
  settings: {
    get: () => api.get("/cbt/settings").then((r) => r.data),
    update: (data: object) => api.put("/cbt/settings", data).then((r) => r.data),
  },
};

export const behaviourApi = {
  list: (p?: object) => api.get("/behaviour/records", { params: p }).then((r) => r.data),
  create: (data: object) => api.post("/behaviour/records", data).then((r) => r.data),
  delete: (id: string) => api.delete(`/behaviour/records/${id}`),
  studentSummary: (student_id: string) =>
    api.get(`/behaviour/student/${student_id}/summary`).then((r) => r.data),
  schoolSummary: (days = 30) =>
    api.get("/behaviour/summary", { params: { days } }).then((r) => r.data),
};

export const feedbackApi = {
  list: (p?: object) => api.get("/feedback", { params: p }).then((r) => r.data),
  submit: (data: object) => api.post("/feedback", data).then((r) => r.data),
  resolve: (id: string, data: { admin_response: string; is_resolved?: boolean }) =>
    api.patch(`/feedback/${id}/resolve`, data).then((r) => r.data),
};

export const clubsApi = {
  list: (p?: object) => api.get("/clubs", { params: p }).then((r) => r.data),
  get: (id: string) => api.get(`/clubs/${id}`).then((r) => r.data),
  create: (data: object) => api.post("/clubs", data).then((r) => r.data),
  update: (id: string, data: object) => api.patch(`/clubs/${id}`, data).then((r) => r.data),
  delete: (id: string) => api.delete(`/clubs/${id}`),
  members: (id: string) => api.get(`/clubs/${id}/members`).then((r) => r.data),
  join: (id: string, data: { student_id: string; role?: string }) =>
    api.post(`/clubs/${id}/join`, data).then((r) => r.data),
  leave: (membership_id: string) => api.delete(`/clubs/memberships/${membership_id}`),
};

// Bulk SMS (Phase 6.6). Admin-only on the backend; the UI hides the nav
// item for non-admin roles via the sidebar allow-list.
export const smsApi = {
  classes: () => api.get("/sms/classes").then((r) => r.data),
  previewRecipients: (params: { target_type: string; target_value?: string }) =>
    api.get("/sms/recipients/preview", { params }).then((r) => r.data),
  send: (data: {
    body: string;
    target_type: string;
    target_value?: unknown;
    sender_id?: string;
    subject?: string;
    provider?: string;
  }) => api.post("/sms/campaigns", data).then((r) => r.data),
  list: (p?: { status?: string; page?: number; page_size?: number }) =>
    api.get("/sms/campaigns", { params: p }).then((r) => r.data),
  get: (id: string) => api.get(`/sms/campaigns/${id}`).then((r) => r.data),
  resend: (id: string) => api.post(`/sms/campaigns/${id}/resend`).then((r) => r.data),
};

// Executive Dashboard (Phase 6.8). Single-call overview for the school
// owner/admin home. Backend caches happily (pure-input function on org_id +
// today's date) — wrap with React Query and we're done.
export const dashboardApi = {
  overview: () => api.get("/dashboard/overview").then((r) => r.data),
  workspaceOverview: () => api.get("/dashboard/workspace-overview").then((r) => r.data),
};

// Transport (Phase 6.7). Operational module — vehicles, drivers, routes,
// trips, and per-student boarding events. Admin-only on the backend.
export const transportApi = {
  dashboard: () => api.get("/transport/dashboard").then((r) => r.data),
  vehicles: {
    list: () => api.get("/transport/vehicles").then((r) => r.data),
    create: (data: object) => api.post("/transport/vehicles", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/transport/vehicles/${id}`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/transport/vehicles/${id}`),
  },
  drivers: {
    list: () => api.get("/transport/drivers").then((r) => r.data),
    create: (data: object) => api.post("/transport/drivers", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/transport/drivers/${id}`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/transport/drivers/${id}`),
  },
  routes: {
    list: (p?: { include_stops?: boolean }) =>
      api.get("/transport/routes", { params: p }).then((r) => r.data),
    get: (id: string) => api.get(`/transport/routes/${id}`).then((r) => r.data),
    create: (data: object) => api.post("/transport/routes", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/transport/routes/${id}`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/transport/routes/${id}`),
    addStop: (route_id: string, data: object) =>
      api.post(`/transport/routes/${route_id}/stops`, data).then((r) => r.data),
    updateStop: (stop_id: string, data: object) =>
      api.patch(`/transport/stops/${stop_id}`, data).then((r) => r.data),
    removeStop: (stop_id: string) => api.delete(`/transport/stops/${stop_id}`),
    assignStudent: (route_id: string, data: { student_id: string; pickup_stop_id?: string; dropoff_stop_id?: string }) =>
      api.post(`/transport/routes/${route_id}/students`, data).then((r) => r.data),
    unassignStudent: (route_id: string, student_id: string) =>
      api.delete(`/transport/routes/${route_id}/students/${student_id}`),
  },
  trips: {
    list: (p?: { trip_date?: string; status?: string; route_id?: string }) =>
      api.get("/transport/trips", { params: p }).then((r) => r.data),
    get: (id: string) => api.get(`/transport/trips/${id}`).then((r) => r.data),
    create: (data: { route_id: string; direction: "morning" | "afternoon"; trip_date?: string }) =>
      api.post("/transport/trips", data).then((r) => r.data),
    start: (id: string) => api.post(`/transport/trips/${id}/start`).then((r) => r.data),
    complete: (id: string) => api.post(`/transport/trips/${id}/complete`).then((r) => r.data),
    cancel: (id: string, reason?: string) =>
      api.post(`/transport/trips/${id}/cancel`, { reason }).then((r) => r.data),
    board: (trip_id: string, data: { student_id: string; status: string; notes?: string }) =>
      api.post(`/transport/trips/${trip_id}/board`, data).then((r) => r.data),
  },
};

export const journalsApi = {
  list: (p?: object) => api.get("/journals", { params: p }).then((r) => r.data),
  create: (data: object) => api.post("/journals", data).then((r) => r.data),
  delete: (id: string) => api.delete(`/journals/${id}`),
  remarks: {
    list: (p?: object) => api.get("/journals/remarks", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/journals/remarks", data).then((r) => r.data),
    delete: (id: string) => api.delete(`/journals/remarks/${id}`),
  },
};

export const tuckshopApi = {
  products: {
    list: (p?: object) => api.get("/tuckshop/products", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/tuckshop/products", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/tuckshop/products/${id}`, data).then((r) => r.data),
    delete: (id: string) => api.delete(`/tuckshop/products/${id}`),
  },
  purchases: {
    list: (p?: object) => api.get("/tuckshop/purchases", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/tuckshop/purchases", data).then((r) => r.data),
  },
  salesSummary: (date?: string) =>
    api.get("/tuckshop/sales/summary", { params: date ? { date } : undefined }).then((r) => r.data),
};

export const meApi = {
  schoolContext: () => api.get("/me/school-context").then((r) => r.data),
  /**
   * Phase 6.3 multi-role endpoint. Returns one section per role the user can
   * assume (admin/teacher/parent/student) plus `available_roles` + `default_role`.
   * Powers the role switcher and every role-scoped home page.
   */
  contexts: () => api.get("/me/contexts").then((r) => r.data),
};

// ── Attendance (event-sourced) ────────────────────────────────────────────────
//
// The new /attendance/* endpoints: timestamped check-in/out events plus the
// daily/monthly summaries derived from them. Distinct from
// `schoolApi.attendance` (the legacy daily roll-call marker), which is kept.
// `events.ingest` is the same endpoint a future ZKTeco adapter pushes to.

export const attendanceApi = {
  daily: (params: { date?: string; class_id?: string }) =>
    api.get("/attendance/daily", { params }).then((r) => r.data),
  monthly: (params: { year: number; month: number; student_id?: string }) =>
    api.get("/attendance/monthly", { params }).then((r) => r.data),
  studentHistory: (student_id: string, limit = 50) =>
    api.get(`/attendance/student/${student_id}/history`, { params: { limit } }).then((r) => r.data),
  recordManual: (data: {
    student_id: string;
    event_type: "check_in" | "check_out";
    event_time?: string;
    notes?: string;
  }) => api.post("/attendance/manual", data).then((r) => r.data),
};

// ── Notifications inbox ───────────────────────────────────────────────────────
//
// Real per-user notification feed (/notifications). Powers the attendance
// arrival/departure alerts parents see in the portal. The existing
// /dashboard/notifications page reads the activity feed and is left as-is.

export const notificationsApi = {
  list: (params?: { unread_only?: boolean; type?: string; limit?: number }) =>
    api.get("/notifications", { params }).then((r) => r.data),
  markRead: (id: string) => api.patch(`/notifications/${id}/read`).then((r) => r.data),
  markAllRead: () => api.patch("/notifications/read-all").then((r) => r.data),
};

// ── Import History API ──────────────────────────────────────────────────────

export const importApi = {
  list: (p?: { entity?: string; page?: number; page_size?: number }) =>
    api.get("/imports", { params: p }).then((r) => r.data),
  get: (id: string) => api.get(`/imports/${id}`).then((r) => r.data),
  create: (data: object) => api.post("/imports", data).then((r) => r.data),
  rollback: (id: string) => api.post(`/imports/${id}/rollback`).then((r) => r.data),
  checkDuplicates: (data: { entity: string; field: string; values: string[] }) =>
    api.post("/imports/check-duplicates", data).then((r) => r.data),
  startBackground: (data: object) => api.post("/imports/background", data).then((r) => r.data),
};

// ── Upload API ───────────────────────────────────────────────────────────────

export const uploadApi = {
  avatar: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return api.post("/upload/avatar", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }).then((r) => r.data);
  },
  document: (file: File, category?: string) => {
    const formData = new FormData();
    formData.append("file", file);
    if (category) formData.append("category", category);
    return api.post("/upload/document", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }).then((r) => r.data);
  },
};

// ── Search API ───────────────────────────────────────────────────────────────

export const searchApi = {
  global: (query: string, modules?: string[]) =>
    api.get("/search", { params: { q: query, modules: modules?.join(",") } }).then((r) => r.data),
};

// ── Leave API ────────────────────────────────────────────────────────────────

export const leaveApi = {
  applications: {
    list: (p?: { mine?: boolean; status?: string; limit?: number }) =>
      api.get("/leave/applications", { params: p }).then((r) => r.data),
    get: (id: string) => api.get(`/leave/applications/${id}`).then((r) => r.data),
    create: (data: object) => api.post("/leave/applications", data).then((r) => r.data),
    approve: (id: string, data?: { decision_note?: string }) =>
      api.patch(`/leave/applications/${id}/approve`, data ?? {}).then((r) => r.data),
    reject: (id: string, data?: { decision_note?: string }) =>
      api.patch(`/leave/applications/${id}/reject`, data ?? {}).then((r) => r.data),
  },
  analytics: () => api.get("/leave/analytics").then((r) => r.data),
};

// ── Messenger API ────────────────────────────────────────────────────────────

export const messengerApi = {
  conversations: {
    list: () => api.get("/messenger/conversations").then((r) => r.data),
    create: (data: { kind?: "direct" | "group"; peer_id?: string; title?: string; member_ids?: string[] }) =>
      api.post("/messenger/conversations", data).then((r) => r.data),
  },
  // Messageable users for the DM/group picker. Auth-only (no users:read) and
  // returns a plain array — purpose-built for Messenger, unlike /users which is
  // admin-gated and paginated.
  contacts: {
    list: (params?: { search?: string; limit?: number; offset?: number }) =>
      api.get("/messenger/contacts", { params }).then((r) => r.data),
  },
  messages: {
    list: (conversation_id: string, params?: { limit?: number; before?: string }) =>
      api.get(`/messenger/messages/${conversation_id}`, { params }).then((r) => r.data),
    create: (data: { conversation_id: string; type?: "text" | "image" | "video"; content?: string; file_url?: string }) =>
      api.post("/messenger/messages", data).then((r) => r.data),
  },
  upload: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return api
      .post("/messenger/upload", fd, { headers: { "Content-Type": "multipart/form-data" } })
      .then((r) => r.data);
  },
  wsUrl: () => {
    const base = API_URL.replace(/^http/, "ws");
    // Cookie mode: the httpOnly cookie rides on the same-origin WS handshake —
    // no token in the URL (avoids logging the token in proxy/access logs).
    if (COOKIE_AUTH) return `${base}/api/v1/messenger/ws`;
    const token = Cookies.get("access_token") || "";
    return `${base}/api/v1/messenger/ws?token=${encodeURIComponent(token)}`;
  },
};

// ── People & HR API (Batch 1) ─────────────────────────────────────────────────

// Parents Directory — staff-side view over guardian↔student links.
export const parentsApi = {
  list: (p?: { search?: string; page?: number; page_size?: number }) =>
    api.get("/school/parents", { params: p }).then((r) => r.data),
  create: (data: { user_id: string; student_id: string; relationship_type?: string; is_primary?: boolean }) =>
    api.post("/school/parents", data).then((r) => r.data),
  update: (id: string, data: { relationship_type?: string; is_primary?: boolean }) =>
    api.patch(`/school/parents/${id}`, data).then((r) => r.data),
  remove: (id: string) => api.delete(`/school/parents/${id}`),
};

// HR Development — Staff Assessment + Talent Pool (hr:write admin surfaces).
export const hrDevApi = {
  assessments: {
    list: (p?: { staff_user_id?: string; status?: string; page?: number; page_size?: number }) =>
      api.get("/hr/assessments", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/hr/assessments", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/hr/assessments/${id}`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/hr/assessments/${id}`),
  },
  talent: {
    list: (p?: { stage?: string; search?: string; page?: number; page_size?: number }) =>
      api.get("/hr/talent", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/hr/talent", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/hr/talent/${id}`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/hr/talent/${id}`),
  },
};

// ── Admissions & Enrollment API (Batch 2) ─────────────────────────────────────

export const enrollmentApi = {
  applications: {
    list: (p?: { status?: string; search?: string; page?: number; page_size?: number }) =>
      api.get("/enrollment/applications", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/enrollment/applications", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/enrollment/applications/${id}`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/enrollment/applications/${id}`),
    admit: (id: string, data?: object) => api.post(`/enrollment/applications/${id}/admit`, data ?? {}).then((r) => r.data),
  },
  entranceExams: {
    list: (p?: { status?: string; page?: number; page_size?: number }) =>
      api.get("/enrollment/entrance-exams", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/enrollment/entrance-exams", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/enrollment/entrance-exams/${id}`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/enrollment/entrance-exams/${id}`),
    results: {
      list: (examId: string) => api.get(`/enrollment/entrance-exams/${examId}/results`).then((r) => r.data),
      add: (examId: string, data: object) => api.post(`/enrollment/entrance-exams/${examId}/results`, data).then((r) => r.data),
      update: (resultId: string, data: object) => api.patch(`/enrollment/exam-results/${resultId}`, data).then((r) => r.data),
      remove: (resultId: string) => api.delete(`/enrollment/exam-results/${resultId}`),
    },
  },
  promotions: {
    list: (p?: { student_id?: string; page?: number; page_size?: number }) =>
      api.get("/enrollment/promotions", { params: p }).then((r) => r.data),
    preview: (data: { student_ids: string[]; to_class_id?: string; from_class_id?: string; academic_year?: string; outcome?: string }) =>
      api.post("/enrollment/promotions/preview", data).then((r) => r.data),
    create: (data: { student_ids: string[]; to_class_id?: string; from_class_id?: string; academic_year?: string; outcome?: string }) =>
      api.post("/enrollment/promotions", data).then((r) => r.data),
    revert: (batchId: string) => api.post(`/enrollment/promotions/${batchId}/revert`).then((r) => r.data),
  },
  transfers: {
    list: (p?: { status?: string; page?: number; page_size?: number }) =>
      api.get("/enrollment/transfers", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/enrollment/transfers", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/enrollment/transfers/${id}`, data).then((r) => r.data),
  },
};

// ── Academic Records & Recognition API (Batch 3) ──────────────────────────────

export const academicsApi = {
  subjectSelections: {
    list: (p?: { student_id?: string; subject_id?: string; status?: string; page?: number; page_size?: number }) =>
      api.get("/academics/subject-selections", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/academics/subject-selections", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/academics/subject-selections/${id}`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/academics/subject-selections/${id}`),
  },
  transcripts: {
    list: (p?: { student_id?: string; page?: number; page_size?: number }) =>
      api.get("/academics/transcripts", { params: p }).then((r) => r.data),
    get: (id: string) => api.get(`/academics/transcripts/${id}`).then((r) => r.data),
    create: (data: object) => api.post("/academics/transcripts", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/academics/transcripts/${id}`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/academics/transcripts/${id}`),
    addEntry: (id: string, data: object) => api.post(`/academics/transcripts/${id}/entries`, data).then((r) => r.data),
    removeEntry: (id: string, entryId: string) => api.delete(`/academics/transcripts/${id}/entries/${entryId}`).then((r) => r.data),
  },
  reportWorkflow: {
    list: (p?: { stage?: string; page?: number; page_size?: number }) =>
      api.get("/academics/report-workflow", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/academics/report-workflow", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/academics/report-workflow/${id}`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/academics/report-workflow/${id}`),
  },
  recognitions: {
    list: (p?: { type?: string; student_id?: string; house?: string; term?: string; page?: number; page_size?: number }) =>
      api.get("/academics/recognitions", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/academics/recognitions", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/academics/recognitions/${id}`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/academics/recognitions/${id}`),
    leaderboard: (p?: { term?: string }) => api.get("/academics/recognitions/leaderboard", { params: p }).then((r) => r.data),
  },
};

// ── Pastoral, Boarding & Health API (Batch 4) ─────────────────────────────────

export const pastoralApi = {
  hostels: {
    list: (p?: { page?: number; page_size?: number }) => api.get("/pastoral/hostels", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/pastoral/hostels", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/pastoral/hostels/${id}`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/pastoral/hostels/${id}`),
    allocations: (id: string) => api.get(`/pastoral/hostels/${id}/allocations`).then((r) => r.data),
  },
  allocations: {
    create: (data: object) => api.post("/pastoral/allocations", data).then((r) => r.data),
    remove: (id: string) => api.delete(`/pastoral/allocations/${id}`),
  },
  exeats: {
    list: (p?: { status?: string; page?: number; page_size?: number }) => api.get("/pastoral/exeats", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/pastoral/exeats", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/pastoral/exeats/${id}`, data).then((r) => r.data),
    approve: (id: string, data?: object) => api.post(`/pastoral/exeats/${id}/approve`, data ?? {}).then((r) => r.data),
    reject: (id: string, data?: object) => api.post(`/pastoral/exeats/${id}/reject`, data ?? {}).then((r) => r.data),
    markReturned: (id: string) => api.post(`/pastoral/exeats/${id}/return`).then((r) => r.data),
  },
  mentorReports: {
    list: (p?: { student_id?: string; mentor_id?: string; page?: number; page_size?: number }) =>
      api.get("/pastoral/mentor-reports", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/pastoral/mentor-reports", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/pastoral/mentor-reports/${id}`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/pastoral/mentor-reports/${id}`),
  },
};

// CONFIDENTIAL — only org_admin + nurse hold `medical:*`.
export const medicalApi = {
  list: (p?: { student_id?: string; record_type?: string; page?: number; page_size?: number }) =>
    api.get("/medical/records", { params: p }).then((r) => r.data),
  create: (data: object) => api.post("/medical/records", data).then((r) => r.data),
  update: (id: string, data: object) => api.patch(`/medical/records/${id}`, data).then((r) => r.data),
  remove: (id: string) => api.delete(`/medical/records/${id}`),
};

// ── Support ────────────────────────────────────────────────────────────────────

export const supportApi = {
  send: (data: { subject: string; message: string }) => api.post("/support", data).then((r) => r.data),
};

// ── HR: Recruitment + Disciplinary (Phase 4) ─────────────────────────────────────

export const hrExtApi = {
  jobs: {
    list: (status?: string) => api.get("/hr/recruitment/jobs", { params: { status } }).then((r) => r.data),
    create: (d: object) => api.post("/hr/recruitment/jobs", d).then((r) => r.data),
    update: (id: string, d: object) => api.patch(`/hr/recruitment/jobs/${id}`, d).then((r) => r.data),
    remove: (id: string) => api.delete(`/hr/recruitment/jobs/${id}`),
  },
  applicants: {
    list: (job_id?: string) => api.get("/hr/recruitment/applicants", { params: { job_id } }).then((r) => r.data),
    create: (d: object) => api.post("/hr/recruitment/applicants", d).then((r) => r.data),
    update: (id: string, d: object) => api.patch(`/hr/recruitment/applicants/${id}`, d).then((r) => r.data),
    remove: (id: string) => api.delete(`/hr/recruitment/applicants/${id}`),
  },
  cases: {
    list: (status?: string) => api.get("/hr/disciplinary/cases", { params: { status } }).then((r) => r.data),
    create: (d: object) => api.post("/hr/disciplinary/cases", d).then((r) => r.data),
    update: (id: string, d: object) => api.patch(`/hr/disciplinary/cases/${id}`, d).then((r) => r.data),
    remove: (id: string) => api.delete(`/hr/disciplinary/cases/${id}`),
  },
  appointments: {
    list: (p?: { staff_user_id?: string; status?: string }) => api.get("/hr/appointments", { params: p }).then((r) => r.data),
    create: (d: object) => api.post("/hr/appointments", d).then((r) => r.data),
    update: (id: string, d: object) => api.patch(`/hr/appointments/${id}`, d).then((r) => r.data),
    remove: (id: string) => api.delete(`/hr/appointments/${id}`),
  },
  stats: () => api.get("/hr/stats").then((r) => r.data),
};

// ── Remita parent fee payments ───────────────────────────────────────────────────

export const remitaApi = {
  invoices: () => api.get("/payments/remita/invoices").then((r) => r.data),
  initiate: (invoice_id: string) => api.post("/payments/remita/initiate", { invoice_id }).then((r) => r.data),
  verify: (rrr: string) => api.get(`/payments/remita/verify/${rrr}`).then((r) => r.data),
};

// ── Unified parent fee payments: which gateways the school configured, + the
// invoice-based hosted-checkout flow for the card providers (Paystack/Flutterwave).
export const feesApi = {
  providers: (): Promise<{ providers: string[] }> => api.get("/payments/fees/providers").then((r) => r.data),
  initiate: (invoice_id: string, provider: string) => api.post("/payments/fees/initiate", { invoice_id, provider }).then((r) => r.data),
  verify: (reference: string) => api.get(`/payments/fees/verify/${reference}`).then((r) => r.data),
};

// ── Finance & Accounting API (Batch 5) ────────────────────────────────────────

export const financeApi = {
  accounts: {
    list: (p?: { type?: string; active_only?: boolean }) => api.get("/finance/accounts", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/finance/accounts", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/finance/accounts/${id}`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/finance/accounts/${id}`),
  },
  periods: {
    list: () => api.get("/finance/periods").then((r) => r.data),
    create: (data: object) => api.post("/finance/periods", data).then((r) => r.data),
    lock: (id: string) => api.post(`/finance/periods/${id}/lock`).then((r) => r.data),
    unlock: (id: string) => api.post(`/finance/periods/${id}/unlock`).then((r) => r.data),
  },
  journal: {
    list: (p?: { page?: number; page_size?: number }) => api.get("/finance/journal", { params: p }).then((r) => r.data),
    post: (data: object) => api.post("/finance/journal", data).then((r) => r.data),
    reverse: (id: string) => api.post(`/finance/journal/${id}/reverse`).then((r) => r.data),
  },
  statements: (p?: { as_of?: string }) => api.get("/finance/statements", { params: p }).then((r) => r.data),
  invoices: {
    list: (p?: { status?: string; page?: number; page_size?: number }) => api.get("/finance/invoices", { params: p }).then((r) => r.data),
    get: (id: string) => api.get(`/finance/invoices/${id}`).then((r) => r.data),
    create: (data: object) => api.post("/finance/invoices", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/finance/invoices/${id}`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/finance/invoices/${id}`),
    post: (id: string) => api.post(`/finance/invoices/${id}/post`).then((r) => r.data),
    pay: (id: string, data: object) => api.post(`/finance/invoices/${id}/pay`, data).then((r) => r.data),
    void: (id: string) => api.post(`/finance/invoices/${id}/void`).then((r) => r.data),
  },
  payroll: {
    list: (p?: { status?: string; page?: number; page_size?: number }) => api.get("/finance/payroll", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/finance/payroll", data).then((r) => r.data),
    approve: (id: string) => api.post(`/finance/payroll/${id}/approve`).then((r) => r.data),
    void: (id: string) => api.post(`/finance/payroll/${id}/void`).then((r) => r.data),
    remove: (id: string) => api.delete(`/finance/payroll/${id}`),
  },
  salaryAdvances: {
    list: (p?: { status?: string; staff_user_id?: string }) => api.get("/finance/salary-advances", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/finance/salary-advances", data).then((r) => r.data),
    approve: (id: string, data?: object) => api.post(`/finance/salary-advances/${id}/approve`, data ?? {}).then((r) => r.data),
    reject: (id: string) => api.post(`/finance/salary-advances/${id}/reject`).then((r) => r.data),
    repay: (id: string, data: object) => api.post(`/finance/salary-advances/${id}/repay`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/finance/salary-advances/${id}`),
  },
  payAdjustments: {
    list: (p?: { kind?: string; status?: string }) => api.get("/finance/pay-adjustments", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/finance/pay-adjustments", data).then((r) => r.data),
    approve: (id: string) => api.post(`/finance/pay-adjustments/${id}/approve`).then((r) => r.data),
    void: (id: string) => api.post(`/finance/pay-adjustments/${id}/void`).then((r) => r.data),
    remove: (id: string) => api.delete(`/finance/pay-adjustments/${id}`),
  },
  requisitions: {
    list: (p?: { status?: string; department?: string }) => api.get("/finance/requisitions", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/finance/requisitions", data).then((r) => r.data),
    approve: (id: string) => api.post(`/finance/requisitions/${id}/approve`).then((r) => r.data),
    reject: (id: string) => api.post(`/finance/requisitions/${id}/reject`).then((r) => r.data),
    void: (id: string) => api.post(`/finance/requisitions/${id}/void`).then((r) => r.data),
    remove: (id: string) => api.delete(`/finance/requisitions/${id}`),
  },
  reports: {
    incomeExpense: (p?: { start?: string; end?: string }) => api.get("/finance/reports/income-expense", { params: p }).then((r) => r.data),
  },
  discounts: {
    list: (p?: { status?: string; student_id?: string }) => api.get("/finance/discounts", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/finance/discounts", data).then((r) => r.data),
    approve: (id: string) => api.post(`/finance/discounts/${id}/approve`).then((r) => r.data),
    reject: (id: string) => api.post(`/finance/discounts/${id}/reject`).then((r) => r.data),
    void: (id: string) => api.post(`/finance/discounts/${id}/void`).then((r) => r.data),
    remove: (id: string) => api.delete(`/finance/discounts/${id}`),
  },
  feeRecords: {
    list: (p?: { student_id?: string; term?: string; session_year?: string }) => api.get("/finance/fee-records", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/finance/fee-records", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/finance/fee-records/${id}`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/finance/fee-records/${id}`),
    assignClass: (data: object) => api.post("/finance/fee-records/assign-class", data).then((r) => r.data),
  },
  classes: {
    list: () => api.get("/finance/classes").then((r) => r.data),
  },
  settings: {
    get: () => api.get("/finance/settings").then((r) => r.data),
    update: (data: object) => api.put("/finance/settings", data).then((r) => r.data),
  },
  bankAccounts: {
    list: () => api.get("/finance/bank-accounts").then((r) => r.data),
    primary: () => api.get("/finance/bank-accounts/primary").then((r) => r.data),
    create: (data: object) => api.post("/finance/bank-accounts", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/finance/bank-accounts/${id}`, data).then((r) => r.data),
    setPrimary: (id: string) => api.post(`/finance/bank-accounts/${id}/set-primary`).then((r) => r.data),
    remove: (id: string) => api.delete(`/finance/bank-accounts/${id}`),
  },
  gateways: {
    list: () => api.get("/finance/payment-gateways").then((r) => r.data),
    create: (data: object) => api.post("/finance/payment-gateways", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/finance/payment-gateways/${id}`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/finance/payment-gateways/${id}`),
  },
  budgets: {
    list: () => api.get("/finance/budgets").then((r) => r.data),
    create: (data: object) => api.post("/finance/budgets", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/finance/budgets/${id}`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/finance/budgets/${id}`),
  },
  pettyCash: {
    list: (p?: { page?: number; page_size?: number }) => api.get("/finance/petty-cash", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/finance/petty-cash", data).then((r) => r.data),
    void: (id: string) => api.post(`/finance/petty-cash/${id}/void`).then((r) => r.data),
  },
  cash: {
    list: (p?: { type?: string; page?: number; page_size?: number }) => api.get("/finance/cash", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/finance/cash", data).then((r) => r.data),
    void: (id: string) => api.post(`/finance/cash/${id}/void`).then((r) => r.data),
  },
  store: {
    items: (p?: { page?: number; page_size?: number }) => api.get("/finance/store/items", { params: p }).then((r) => r.data),
    createItem: (data: object) => api.post("/finance/store/items", data).then((r) => r.data),
    updateItem: (id: string, data: object) => api.patch(`/finance/store/items/${id}`, data).then((r) => r.data),
    removeItem: (id: string) => api.delete(`/finance/store/items/${id}`),
    purchase: (id: string, data: object) => api.post(`/finance/store/items/${id}/purchase`, data).then((r) => r.data),
    adjust: (id: string, data: object) => api.post(`/finance/store/items/${id}/adjust`, data).then((r) => r.data),
    sales: (p?: { status?: string }) => api.get("/finance/store/sales", { params: p }).then((r) => r.data),
    getSale: (id: string) => api.get(`/finance/store/sales/${id}`).then((r) => r.data),
    createSale: (data: object) => api.post("/finance/store/sales", data).then((r) => r.data),
    voidSale: (id: string) => api.post(`/finance/store/sales/${id}/void`).then((r) => r.data),
    salesSummary: (p?: { start?: string; end?: string }) => api.get("/finance/store/sales-summary", { params: p }).then((r) => r.data),
  },
  warehouse: {
    list: () => api.get("/finance/warehouses").then((r) => r.data),
    create: (data: object) => api.post("/finance/warehouses", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/finance/warehouses/${id}`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/finance/warehouses/${id}`),
    stock: (id: string) => api.get(`/finance/warehouses/${id}/stock`).then((r) => r.data),
    receive: (data: object) => api.post("/finance/warehouse/receive", data).then((r) => r.data),
    transfer: (data: object) => api.post("/finance/warehouse/transfer", data).then((r) => r.data),
    issue: (data: object) => api.post("/finance/warehouse/issue", data).then((r) => r.data),
  },
  pickup: {
    points: () => api.get("/finance/pickup-points").then((r) => r.data),
    createPoint: (data: object) => api.post("/finance/pickup-points", data).then((r) => r.data),
    updatePoint: (id: string, data: object) => api.patch(`/finance/pickup-points/${id}`, data).then((r) => r.data),
    removePoint: (id: string) => api.delete(`/finance/pickup-points/${id}`),
    list: (p?: { status?: string; pickup_point_id?: string }) => api.get("/finance/pickups", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/finance/pickups", data).then((r) => r.data),
    collect: (id: string) => api.post(`/finance/pickups/${id}/collect`).then((r) => r.data),
    cancel: (id: string) => api.post(`/finance/pickups/${id}/cancel`).then((r) => r.data),
    remove: (id: string) => api.delete(`/finance/pickups/${id}`),
  },
};

// ── Wallet / PocketMoney + Cooperative API (Batch 6) ──────────────────────────

export const walletApi = {
  wallets: {
    list: (p?: { page?: number; page_size?: number }) => api.get("/finance/wallets", { params: p }).then((r) => r.data),
    get: (id: string) => api.get(`/finance/wallets/${id}`).then((r) => r.data),
    create: (data: object) => api.post("/finance/wallets", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/finance/wallets/${id}`, data).then((r) => r.data),
    topup: (id: string, data: object) => api.post(`/finance/wallets/${id}/topup`, data).then((r) => r.data),
    withdraw: (id: string, data: object) => api.post(`/finance/wallets/${id}/withdraw`, data).then((r) => r.data),
    spend: (id: string, data: object) => api.post(`/finance/wallets/${id}/spend`, data).then((r) => r.data),
    reverseEntry: (walletId: string, entryId: string) => api.post(`/finance/wallets/${walletId}/entries/${entryId}/reverse`).then((r) => r.data),
    reconciliation: () => api.get("/finance/wallets-reconciliation").then((r) => r.data),
  },
  cooperative: {
    members: (p?: { page?: number; page_size?: number }) => api.get("/finance/cooperative/members", { params: p }).then((r) => r.data),
    getMember: (id: string) => api.get(`/finance/cooperative/members/${id}`).then((r) => r.data),
    createMember: (data: object) => api.post("/finance/cooperative/members", data).then((r) => r.data),
    contribute: (id: string, data: object) => api.post(`/finance/cooperative/members/${id}/contribute`, data).then((r) => r.data),
    payout: (id: string, data: object) => api.post(`/finance/cooperative/members/${id}/payout`, data).then((r) => r.data),
    reconciliation: () => api.get("/finance/cooperative/reconciliation").then((r) => r.data),
  },
};

// ── Operations API (Batch 6, non-financial) ───────────────────────────────────

export const operationsApi = {
  calendar: {
    list: (p?: { page?: number; page_size?: number }) => api.get("/operations/calendar", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/operations/calendar", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/operations/calendar/${id}`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/operations/calendar/${id}`),
  },
  facilities: {
    list: (p?: { page?: number; page_size?: number }) => api.get("/operations/facilities", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/operations/facilities", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/operations/facilities/${id}`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/operations/facilities/${id}`),
    bookings: (id: string) => api.get(`/operations/facilities/${id}/bookings`).then((r) => r.data),
    book: (id: string, data: object) => api.post(`/operations/facilities/${id}/bookings`, data).then((r) => r.data),
    cancelBooking: (bookingId: string) => api.post(`/operations/bookings/${bookingId}/cancel`).then((r) => r.data),
  },
  visitors: {
    list: (p?: { status?: string; page?: number; page_size?: number }) => api.get("/operations/visitors", { params: p }).then((r) => r.data),
    signIn: (data: object) => api.post("/operations/visitors", data).then((r) => r.data),
    signOut: (id: string) => api.post(`/operations/visitors/${id}/signout`).then((r) => r.data),
    remove: (id: string) => api.delete(`/operations/visitors/${id}`),
  },
  collections: {
    list: (p?: { student_id?: string; page?: number; page_size?: number }) => api.get("/operations/collections", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/operations/collections", data).then((r) => r.data),
    remove: (id: string) => api.delete(`/operations/collections/${id}`),
  },
};

// ── Administration & Platform API (Batch 7) ───────────────────────────────────

export const biometricApi = {
  devices: {
    list: () => api.get("/biometric/devices").then((r) => r.data),
    create: (data: object) => api.post("/biometric/devices", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/biometric/devices/${id}`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/biometric/devices/${id}`),
  },
  enrollments: {
    list: () => api.get("/biometric/enrollments").then((r) => r.data),
    create: (data: object) => api.post("/biometric/enrollments", data).then((r) => r.data),
    remove: (id: string) => api.delete(`/biometric/enrollments/${id}`),
  },
  ingest: (data: object) => api.post("/biometric/ingest", data).then((r) => r.data),
  quarantine: {
    list: (status = "pending") => api.get("/biometric/quarantine", { params: { status } }).then((r) => r.data),
    resolve: (id: string, data: object) => api.post(`/biometric/quarantine/${id}/resolve`, data).then((r) => r.data),
    discard: (id: string) => api.post(`/biometric/quarantine/${id}/discard`),
  },
};

export const platformApi = {
  sessions: { list: () => api.get("/platform/sessions").then((r) => r.data), create: (d: object) => api.post("/platform/sessions", d).then((r) => r.data), remove: (id: string) => api.delete(`/platform/sessions/${id}`) },
  weeks: {
    list: (params?: { academic_year?: string; term?: string }) => api.get("/platform/weeks", { params }).then((r) => r.data),
    create: (d: object) => api.post("/platform/weeks", d).then((r) => r.data),
    generate: (d: object) => api.post("/platform/weeks/generate", d).then((r) => r.data),
    update: (id: string, d: object) => api.patch(`/platform/weeks/${id}`, d).then((r) => r.data),
    remove: (id: string) => api.delete(`/platform/weeks/${id}`),
  },
  houses: { list: () => api.get("/platform/houses").then((r) => r.data), create: (d: object) => api.post("/platform/houses", d).then((r) => r.data), remove: (id: string) => api.delete(`/platform/houses/${id}`) },
  bands: { list: () => api.get("/platform/grading-bands").then((r) => r.data), create: (d: object) => api.post("/platform/grading-bands", d).then((r) => r.data), remove: (id: string) => api.delete(`/platform/grading-bands/${id}`) },
  customFields: {
    list: (entity_type?: string) => api.get("/platform/custom-fields", { params: { entity_type } }).then((r) => r.data),
    create: (d: object) => api.post("/platform/custom-fields", d).then((r) => r.data),
    remove: (id: string) => api.delete(`/platform/custom-fields/${id}`),
  },
  polls: {
    list: (p?: { status?: string }) => api.get("/platform/polls", { params: p }).then((r) => r.data),
    create: (d: object) => api.post("/platform/polls", d).then((r) => r.data),
    close: (id: string) => api.post(`/platform/polls/${id}/close`).then((r) => r.data),
    remove: (id: string) => api.delete(`/platform/polls/${id}`),
    vote: (id: string, d: object) => api.post(`/platform/polls/${id}/vote`, d).then((r) => r.data),
  },
  mailbox: {
    send: (d: object) => api.post("/platform/mailbox/messages", d).then((r) => r.data),
    sent: () => api.get("/platform/mailbox/sent").then((r) => r.data),
    inbox: () => api.get("/platform/mailbox/inbox").then((r) => r.data),
    markRead: (rowId: string) => api.post(`/platform/mailbox/inbox/${rowId}/read`),
  },
  mobile: {
    devices: () => api.get("/platform/mobile/devices").then((r) => r.data),
    remove: (id: string) => api.delete(`/platform/mobile/devices/${id}`),
    config: () => api.get("/platform/mobile/config").then((r) => r.data),
    setConfig: (d: object) => api.post("/platform/mobile/config", d).then((r) => r.data),
  },
};

// ── News Feed API ────────────────────────────────────────────────────────────

export const feedApi = {
  posts: {
    list: (params?: { limit?: number; before?: string }) =>
      api.get("/feed/posts", { params }).then((r) => r.data),
    get: (id: string) => api.get(`/feed/posts/${id}`).then((r) => r.data),
    create: (data: { content?: string; media_url?: string; media_type?: "image" | "video" }) =>
      api.post("/feed/posts", data).then((r) => r.data),
    remove: (id: string) => api.delete(`/feed/posts/${id}`),
  },
  like: (id: string) => api.post(`/feed/posts/${id}/like`).then((r) => r.data),
  unlike: (id: string) => api.delete(`/feed/posts/${id}/like`).then((r) => r.data),
  comments: {
    list: (post_id: string, params?: { limit?: number }) =>
      api.get(`/feed/posts/${post_id}/comments`, { params }).then((r) => r.data),
    create: (post_id: string, data: { content: string }) =>
      api.post(`/feed/posts/${post_id}/comments`, data).then((r) => r.data),
    remove: (post_id: string, comment_id: string) =>
      api.delete(`/feed/posts/${post_id}/comments/${comment_id}`),
  },
};

// ── Livestream API ───────────────────────────────────────────────────────────

export const liveApi = {
  sessions: {
    list: (params?: { active_only?: boolean }) =>
      api.get("/live/sessions", { params }).then((r) => r.data),
    get: (id: string) => api.get(`/live/sessions/${id}`).then((r) => r.data),
  },
  start: (data: {
    title: string;
    description?: string;
    class_id?: string;
    subject_id?: string;
    timetable_id?: string;
  }) => api.post("/live/start", data).then((r) => r.data),
  end: (id: string) => api.post(`/live/${id}/end`).then((r) => r.data),
  timetable: {
    today: () => api.get("/live/timetable/today").then((r) => r.data),
    start: (timetable_id: string) =>
      api.post(`/live/from-timetable/${timetable_id}`).then((r) => r.data),
  },
  iceConfig: (): Promise<{ iceServers: RTCIceServer[] }> =>
    api.get("/live/ice-config").then((r) => r.data),
  recordings: {
    list: (session_id: string) =>
      api.get(`/live/${session_id}/recordings`).then((r) => r.data),
    upload: (session_id: string, blob: Blob, duration_seconds?: number) => {
      const fd = new FormData();
      // Filename gives the server a mime hint when Content-Type is vague.
      const ext = (blob.type || "").includes("mp4") ? "mp4" : "webm";
      fd.append("file", blob, `recording.${ext}`);
      const params = duration_seconds ? { duration_seconds } : undefined;
      return api
        .post(`/live/${session_id}/recording`, fd, {
          params,
          headers: { "Content-Type": "multipart/form-data" },
        })
        .then((r) => r.data);
    },
  },
  analytics: (session_id: string) =>
    api.get(`/live/${session_id}/analytics`).then((r) => r.data),
  wsUrl: (session_id: string) => {
    const base = API_URL.replace(/^http/, "ws");
    if (COOKIE_AUTH) return `${base}/api/v1/live/ws/${session_id}`;
    const token = Cookies.get("access_token") || "";
    return `${base}/api/v1/live/ws/${session_id}?token=${encodeURIComponent(token)}`;
  },
};

// ── HR API ───────────────────────────────────────────────────────────────────

export const hrApi = {
  me: {
    get: () => api.get("/hr/me").then((r) => r.data),
    update: (data: object) => api.patch("/hr/me", data).then((r) => r.data),
  },
  profiles: {
    get: (user_id: string) => api.get(`/hr/profiles/${user_id}`).then((r) => r.data),
  },
  overview: () => api.get("/hr/overview").then((r) => r.data),
  birthdays: (month?: number) =>
    api.get("/hr/birthdays", { params: month ? { month } : undefined }).then((r) => r.data),
  events: {
    list: (p?: { upcoming_only?: boolean; limit?: number }) =>
      api.get("/hr/events", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/hr/events", data).then((r) => r.data),
    update: (id: string, data: object) => api.patch(`/hr/events/${id}`, data).then((r) => r.data),
    delete: (id: string) => api.delete(`/hr/events/${id}`),
  },
};
