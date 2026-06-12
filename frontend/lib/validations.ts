import { z } from "zod";

// ── Shared Primitives ───────────────────────────────────────────────────────

const requiredString = (label: string) => z.string().min(1, `${label} is required`);
const optionalString = z.string().optional().or(z.literal(""));
const positiveNumber = (label: string) => z.coerce.number().min(0, `${label} must be positive`);
const positiveInt = (label: string) => z.coerce.number().int().min(0, `${label} must be a positive integer`);
const emailField = z.string().email("Valid email required").or(z.literal(""));
const dateField = (label: string) => z.string().min(1, `${label} is required`);
const optionalDate = z.string().optional().or(z.literal(""));
const phoneField = z.string().regex(/^[+]?[\d\s()-]{7,20}$/, "Invalid phone number").or(z.literal(""));

// ── School Module ───────────────────────────────────────────────────────────

export const studentSchema = z.object({
  first_name: requiredString("First name"),
  last_name: requiredString("Last name"),
  email: emailField,
  phone: phoneField,
  date_of_birth: optionalDate,
  gender: z.enum(["male", "female", "other"]).optional(),
  guardian_name: optionalString,
  guardian_phone: phoneField,
  address: optionalString,
  class_id: optionalString,
});

export const teacherSchema = z.object({
  first_name: requiredString("First name"),
  last_name: requiredString("Last name"),
  email: z.string().email("Valid email required"),
  phone: phoneField,
  department: optionalString,
  subjects: optionalString,
  qualification: optionalString,
});

export const classSchema = z.object({
  name: requiredString("Class name"),
  section: optionalString,
  capacity: positiveInt("Capacity"),
  class_teacher_id: optionalString,
});

export const subjectSchema = z.object({
  name: requiredString("Subject name"),
  code: requiredString("Subject code"),
  department: optionalString,
  teacher_id: optionalString,
  credits: positiveInt("Credits").optional(),
});

export const examSchema = z.object({
  name: requiredString("Exam name"),
  exam_type: z.enum(["midterm", "final", "quiz", "assignment", "project"]),
  subject_id: requiredString("Subject"),
  class_id: requiredString("Class"),
  date: dateField("Exam date"),
  total_marks: positiveInt("Total marks").pipe(z.number().min(1, "Must be at least 1")),
});

export const feeSchema = z.object({
  student_id: requiredString("Student ID"),
  fee_type: requiredString("Fee type"),
  amount: positiveNumber("Amount").pipe(z.number().min(1, "Amount must be greater than 0")),
  due_date: dateField("Due date"),
  description: optionalString,
});

// ── Hospital Module ─────────────────────────────────────────────────────────

export const patientSchema = z.object({
  first_name: requiredString("First name"),
  last_name: requiredString("Last name"),
  email: emailField,
  phone: phoneField,
  date_of_birth: optionalDate,
  gender: z.enum(["male", "female", "other"]).optional(),
  blood_type: z.enum(["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"]).optional(),
  address: optionalString,
  emergency_contact: optionalString,
  insurance_id: optionalString,
});

export const doctorSchema = z.object({
  first_name: requiredString("First name"),
  last_name: requiredString("Last name"),
  email: z.string().email("Valid email required"),
  phone: phoneField,
  specialization: requiredString("Specialization"),
  license_number: optionalString,
  department: optionalString,
});

export const appointmentSchema = z.object({
  patient_id: requiredString("Patient ID"),
  doctor_id: requiredString("Doctor ID"),
  appointment_date: dateField("Appointment date"),
  start_time: requiredString("Start time"),
  end_time: optionalString,
  reason: optionalString,
});

export const labTestSchema = z.object({
  patient_id: requiredString("Patient ID"),
  doctor_id: requiredString("Doctor ID"),
  test_name: requiredString("Test name"),
  test_type: optionalString,
  notes: optionalString,
});

export const vitalsSchema = z.object({
  patient_id: requiredString("Patient ID"),
  temperature: positiveNumber("Temperature").optional(),
  blood_pressure_systolic: positiveInt("Systolic BP").optional(),
  blood_pressure_diastolic: positiveInt("Diastolic BP").optional(),
  heart_rate: positiveInt("Heart rate").optional(),
  respiratory_rate: positiveInt("Respiratory rate").optional(),
  oxygen_saturation: positiveNumber("SpO2").optional(),
  weight: positiveNumber("Weight").optional(),
  notes: optionalString,
}).refine(
  (data) => data.temperature || data.blood_pressure_systolic || data.heart_rate || data.oxygen_saturation || data.weight,
  { message: "At least one vital sign measurement is required" }
);

export const prescriptionSchema = z.object({
  patient_id: requiredString("Patient ID"),
  doctor_id: requiredString("Doctor ID"),
  medication: requiredString("Medication"),
  dosage: requiredString("Dosage"),
  frequency: requiredString("Frequency"),
  duration: optionalString,
  notes: optionalString,
});

export const medicalRecordSchema = z.object({
  patient_id: requiredString("Patient ID"),
  doctor_id: requiredString("Doctor ID"),
  record_type: z.enum(["consultation", "lab_result", "prescription", "surgery", "follow_up"]),
  diagnosis: optionalString,
  symptoms: optionalString,
  notes: optionalString,
});

export const billSchema = z.object({
  patient_id: requiredString("Patient ID"),
  description: requiredString("Description"),
  amount: positiveNumber("Amount").pipe(z.number().min(1, "Amount must be greater than 0")),
  due_date: optionalDate,
});

export const pharmacySchema = z.object({
  drug_name: requiredString("Drug name"),
  generic_name: optionalString,
  category: requiredString("Category"),
  quantity_in_stock: positiveInt("Quantity"),
  unit_price: positiveNumber("Unit price"),
  supplier: optionalString,
  batch_number: optionalString,
  expiry_date: optionalDate,
  reorder_level: positiveInt("Reorder level"),
});

// ── Business Module ─────────────────────────────────────────────────────────

export const employeeSchema = z.object({
  first_name: requiredString("First name"),
  last_name: requiredString("Last name"),
  email: z.string().email("Valid email required"),
  phone: phoneField,
  department: optionalString,
  designation: optionalString,
  employment_type: z.enum(["full_time", "part_time", "contract", "intern"]),
  salary: positiveNumber("Salary"),
  hire_date: optionalDate,
});

export const departmentSchema = z.object({
  name: requiredString("Department name"),
  code: requiredString("Department code").pipe(z.string().max(10, "Code max 10 characters")),
  description: optionalString,
  budget: positiveNumber("Budget").optional(),
});

export const leaveSchema = z.object({
  leave_type: z.enum(["annual", "sick", "compassionate", "maternity", "paternity", "unpaid"]),
  start_date: dateField("Start date"),
  end_date: dateField("End date"),
  days: positiveInt("Days").pipe(z.number().min(1, "Minimum 1 day")),
  reason: optionalString,
}).refine(
  (data) => !data.start_date || !data.end_date || new Date(data.end_date) >= new Date(data.start_date),
  { message: "End date must be after start date", path: ["end_date"] }
);

export const inventorySchema = z.object({
  name: requiredString("Item name"),
  sku: optionalString,
  category: optionalString,
  quantity_in_stock: positiveInt("Quantity"),
  unit_cost: positiveNumber("Unit cost"),
  selling_price: positiveNumber("Selling price"),
  reorder_level: positiveInt("Reorder level"),
  supplier: optionalString,
  description: optionalString,
});

export const invoiceLineSchema = z.object({
  description: requiredString("Item description"),
  quantity: positiveInt("Quantity").pipe(z.number().min(1, "Min 1")),
  unit_price: positiveNumber("Unit price").pipe(z.number().min(0.01, "Min 0.01")),
});

export const invoiceSchema = z.object({
  client_name: requiredString("Client name"),
  client_email: emailField,
  due_date: dateField("Due date"),
  items: z.array(invoiceLineSchema).min(1, "At least one line item required"),
});

export const contactSchema = z.object({
  first_name: requiredString("First name"),
  last_name: requiredString("Last name"),
  email: emailField,
  phone: phoneField,
  company: optionalString,
  position: optionalString,
  lead_source: z.enum(["website", "referral", "social_media", "cold_call", "event", "other"]),
  status: z.enum(["lead", "prospect", "customer", "churned"]),
  notes: optionalString,
});

export const dealSchema = z.object({
  title: requiredString("Deal title"),
  contact_id: requiredString("Contact ID"),
  value: positiveNumber("Value"),
  stage: z.enum(["discovery", "proposal", "negotiation", "closed_won", "closed_lost"]),
  probability: z.coerce.number().int().min(0).max(100, "Max 100%"),
  expected_close_date: optionalDate,
  notes: optionalString,
});

export const procurementLineSchema = z.object({
  description: requiredString("Item description"),
  quantity: positiveInt("Quantity").pipe(z.number().min(1, "Min 1")),
  unit_price: positiveNumber("Unit price"),
});

export const procurementSchema = z.object({
  supplier_name: requiredString("Supplier name"),
  supplier_email: emailField,
  expected_delivery: optionalDate,
  notes: optionalString,
  items: z.array(procurementLineSchema).min(1, "At least one item required"),
});

export const payrollRunSchema = z.object({
  start: dateField("Start date"),
  end: dateField("End date"),
}).refine(
  (data) => new Date(data.end) > new Date(data.start),
  { message: "End date must be after start date", path: ["end"] }
);

// ── Finance Transaction Schema ──────────────────────────────────────────────

export const transactionSchema = z.object({
  transaction_date: dateField("Transaction date"),
  type: z.enum(["income", "expense", "transfer", "refund"], { errorMap: () => ({ message: "Must be income, expense, transfer, or refund" }) }),
  category: optionalString,
  description: optionalString,
  amount: positiveNumber("Amount"),
  currency: optionalString,
  reference: optionalString,
  payment_method: optionalString,
  counterparty: optionalString,
  notes: optionalString,
});

// ── Shared Payment Schema ───────────────────────────────────────────────────

export const paymentSchema = z.object({
  amount: positiveNumber("Amount").pipe(z.number().min(0.01, "Amount must be greater than 0")),
});

// ── Helper: extract first error from Zod result ─────────────────────────────

export function getFormErrors(result: z.SafeParseReturnType<any, any>): Record<string, string> {
  if (result.success) return {};
  const errors: Record<string, string> = {};
  for (const issue of result.error.issues) {
    const key = issue.path.join(".");
    if (!errors[key]) errors[key] = issue.message;
  }
  return errors;
}

export function validateForm<T>(schema: z.ZodSchema<T>, data: unknown): { success: true; data: T } | { success: false; errors: Record<string, string> } {
  const result = schema.safeParse(data);
  if (result.success) return { success: true, data: result.data };
  return { success: false, errors: getFormErrors(result) };
}
