import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from "axios";
import Cookies from "js-cookie";
import { env } from "./env";

const API_URL = env.NEXT_PUBLIC_API_URL;

export const api: AxiosInstance = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
  timeout: 30_000,
});

// ── Request interceptor: attach JWT + org slug ────────────────────────────────
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = Cookies.get("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;

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

      const refreshToken = Cookies.get("refresh_token");
      if (!refreshToken) {
        isRefreshing = false;
        clearAuth();
        window.location.href = "/login";
        return Promise.reject(error);
      }

      try {
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
  Cookies.set("access_token", accessToken, { expires: 1, secure: true, sameSite: "strict" });
  Cookies.set("refresh_token", refreshToken, { expires: 7, secure: true, sameSite: "strict" });
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
  logout: () => clearAuth(),
};

export const usersApi = {
  list: (params?: { page?: number; page_size?: number; search?: string; status?: string }) =>
    api.get("/users", { params }).then((r) => r.data),
  get: (id: string) => api.get(`/users/${id}`).then((r) => r.data),
  listRoles: () => api.get("/users/roles/available").then((r) => r.data),
  create: (data: object) => api.post("/users", data).then((r) => r.data),
  update: (id: string, data: object) => api.patch(`/users/${id}`, data).then((r) => r.data),
  updateStatus: (id: string, status: string) => api.patch(`/users/${id}/status`, { status }).then((r) => r.data),
  assignRoles: (id: string, role_ids: string[]) => api.patch(`/users/${id}/roles`, role_ids).then((r) => r.data),
  invite: (data: object) => api.post("/users/invite", data).then((r) => r.data),
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
  fees: {
    list: (p?: object) => api.get("/school/fees", { params: p }).then((r) => r.data),
    create: (data: object) => api.post("/school/fees", data).then((r) => r.data),
    recordPayment: (id: string, data: object) => api.post(`/school/fees/${id}/pay`, data).then((r) => r.data),
    summary: (p?: object) => api.get("/school/fees/summary", { params: p }).then((r) => r.data),
  },
  attendance: {
    list: (p?: object) => api.get("/school/attendance", { params: p }).then((r) => r.data),
    mark: (records: object[], date?: string) => api.post("/school/attendance", records, { params: { attendance_date: date } }).then((r) => r.data),
    summary: (class_id: string, start_date: string, end_date: string) =>
      api.get("/school/attendance/summary", { params: { class_id, start_date, end_date } }).then((r) => r.data),
    studentHistory: (student_id: string, start_date?: string, end_date?: string) =>
      api.get(`/school/attendance/student/${student_id}`, { params: { start_date, end_date } }).then((r) => r.data),
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
  },
  attempts: {
    list: (p?: { exam_id?: string; student_id?: string }) =>
      api.get("/cbt/attempts", { params: p }).then((r) => r.data),
    get: (id: string) => api.get(`/cbt/attempts/${id}`).then((r) => r.data),
    start: (exam_id: string, student_id: string) =>
      api.post(`/cbt/exams/${exam_id}/attempts`, null, { params: { student_id } }).then((r) => r.data),
    submit: (attempt_id: string, answers: Array<{ question_id: string; answer_text: string }>) =>
      api.post(`/cbt/attempts/${attempt_id}/submit`, { answers }).then((r) => r.data),
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
    const token = Cookies.get("access_token") || "";
    const base = API_URL.replace(/^http/, "ws");
    return `${base}/api/v1/messenger/ws?token=${encodeURIComponent(token)}`;
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
    const token = Cookies.get("access_token") || "";
    const base = API_URL.replace(/^http/, "ws");
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
