import { describe, it, expect } from "vitest";
import { extractErrorMessage } from "@/lib/import/presets";

describe("extractErrorMessage", () => {
  it("handles string detail (HTTPException)", () => {
    const err = { response: { data: { detail: "Email already exists" }, status: 409 } };
    expect(extractErrorMessage(err)).toBe("Email already exists");
  });

  it("handles Pydantic validation array", () => {
    const err = {
      response: {
        status: 422,
        data: {
          detail: [
            { loc: ["body", "email"], msg: "value is not a valid email address", type: "value_error.email" },
            { loc: ["body", "first_name"], msg: "field required", type: "value_error.missing" },
          ],
        },
      },
    };
    const msg = extractErrorMessage(err);
    expect(msg).toContain("email");
    expect(msg).toContain("not a valid email address");
    expect(msg).toContain("first_name");
    expect(msg).toContain("field required");
  });

  it("strips 'body' prefix from Pydantic loc", () => {
    const err = {
      response: {
        status: 422,
        data: { detail: [{ loc: ["body", "phone"], msg: "bad format", type: "x" }] },
      },
    };
    expect(extractErrorMessage(err)).toBe("phone: bad format");
  });

  it("handles nested object detail", () => {
    const err = {
      response: { status: 400, data: { detail: { message: "Custom error", code: "E001" } } },
    };
    expect(extractErrorMessage(err)).toBe("Custom error");
  });

  it("handles plain message field (non-FastAPI backend)", () => {
    const err = { response: { status: 500, data: { message: "Server exploded" } } };
    expect(extractErrorMessage(err)).toBe("Server exploded");
  });

  it("handles network error (no response)", () => {
    const err = { message: "Network Error", code: "ERR_NETWORK" };
    expect(extractErrorMessage(err)).toBe("Network error — check connection");
  });

  it("handles timeout", () => {
    const err = { message: "timeout of 5000ms exceeded", code: "ECONNABORTED" };
    expect(extractErrorMessage(err)).toBe("Request timed out");
  });

  it("falls back to HTTP status when detail is missing", () => {
    const err = { response: { status: 503, statusText: "Service Unavailable", data: {} } };
    expect(extractErrorMessage(err)).toBe("HTTP 503: Service Unavailable");
  });

  it("handles string response body", () => {
    const err = { response: { status: 500, data: "Internal Server Error" } };
    expect(extractErrorMessage(err)).toBe("Internal Server Error");
  });

  it("never returns [object Object]", () => {
    const pydanticErr = {
      response: { status: 422, data: { detail: [{ loc: ["body", "x"], msg: "bad", type: "y" }] } },
    };
    const msg = extractErrorMessage(pydanticErr);
    expect(msg).not.toContain("[object Object]");
  });
});
