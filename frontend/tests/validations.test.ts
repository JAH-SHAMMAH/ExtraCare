import { describe, it, expect } from "vitest";
import {
  employeeSchema,
  leaveSchema,
  vitalsSchema,
  invoiceSchema,
  payrollRunSchema,
  paymentSchema,
  dealSchema,
  validateForm,
} from "@/lib/validations";

describe("employeeSchema", () => {
  it("accepts a valid employee", () => {
    const result = employeeSchema.safeParse({
      first_name: "Ada",
      last_name: "Lovelace",
      email: "ada@example.com",
      phone: "+234 801 234 5678",
      department: "Engineering",
      designation: "Lead",
      employment_type: "full_time",
      salary: 500000,
      hire_date: "2025-01-15",
    });
    expect(result.success).toBe(true);
  });

  it("rejects missing required fields", () => {
    const result = employeeSchema.safeParse({
      first_name: "",
      last_name: "",
      email: "not-an-email",
      employment_type: "full_time",
      salary: 0,
    });
    expect(result.success).toBe(false);
  });

  it("rejects invalid employment type", () => {
    const result = employeeSchema.safeParse({
      first_name: "Bob",
      last_name: "Smith",
      email: "b@x.com",
      employment_type: "ghost",
      salary: 1000,
    });
    expect(result.success).toBe(false);
  });
});

describe("leaveSchema", () => {
  it("rejects when end date is before start date", () => {
    const result = leaveSchema.safeParse({
      leave_type: "annual",
      start_date: "2025-06-10",
      end_date: "2025-06-05",
      days: 5,
    });
    expect(result.success).toBe(false);
  });

  it("accepts a valid leave request", () => {
    const result = leaveSchema.safeParse({
      leave_type: "sick",
      start_date: "2025-06-01",
      end_date: "2025-06-03",
      days: 3,
      reason: "Flu",
    });
    expect(result.success).toBe(true);
  });
});

describe("vitalsSchema", () => {
  it("requires at least one measurement", () => {
    const result = vitalsSchema.safeParse({ patient_id: "p1" });
    expect(result.success).toBe(false);
  });

  it("passes with just temperature", () => {
    const result = vitalsSchema.safeParse({ patient_id: "p1", temperature: 36.8 });
    expect(result.success).toBe(true);
  });
});

describe("invoiceSchema", () => {
  it("requires at least one line item", () => {
    const result = invoiceSchema.safeParse({
      client_name: "Acme",
      client_email: "a@b.com",
      due_date: "2025-12-31",
      items: [],
    });
    expect(result.success).toBe(false);
  });

  it("accepts a valid invoice", () => {
    const result = invoiceSchema.safeParse({
      client_name: "Acme",
      client_email: "a@b.com",
      due_date: "2025-12-31",
      items: [{ description: "Service", quantity: 2, unit_price: 100 }],
    });
    expect(result.success).toBe(true);
  });
});

describe("payrollRunSchema", () => {
  it("rejects when end is not after start", () => {
    const result = payrollRunSchema.safeParse({
      start: "2025-06-01",
      end: "2025-06-01",
    });
    expect(result.success).toBe(false);
  });

  it("accepts a valid range", () => {
    const result = payrollRunSchema.safeParse({
      start: "2025-06-01",
      end: "2025-06-30",
    });
    expect(result.success).toBe(true);
  });
});

describe("paymentSchema", () => {
  it("rejects zero amount", () => {
    expect(paymentSchema.safeParse({ amount: 0 }).success).toBe(false);
  });
  it("accepts positive amount", () => {
    expect(paymentSchema.safeParse({ amount: 50 }).success).toBe(true);
  });
});

describe("dealSchema", () => {
  it("rejects probability over 100", () => {
    const result = dealSchema.safeParse({
      title: "Big deal",
      contact_id: "c1",
      value: 1000,
      stage: "proposal",
      probability: 150,
    });
    expect(result.success).toBe(false);
  });
});

describe("validateForm helper", () => {
  it("returns structured errors on failure", () => {
    const result = validateForm(employeeSchema, { first_name: "" });
    expect(result.success).toBe(false);
    if ("errors" in result) {
      expect(result.errors).toHaveProperty("first_name");
    }
  });

  it("returns parsed data on success", () => {
    const result = validateForm(paymentSchema, { amount: "25.50" });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.amount).toBe(25.5);
    }
  });
});
