"use client";

import { useState, useCallback } from "react";
import { z } from "zod";
import { toast } from "sonner";

interface UseFormValidationReturn<T> {
  errors: Record<string, string>;
  validate: (data: unknown) => T | null;
  clearErrors: () => void;
  clearError: (field: string) => void;
  setFieldError: (field: string, message: string) => void;
}

export function useFormValidation<S extends z.ZodTypeAny>(
  schema: S
): UseFormValidationReturn<z.infer<S>> {
  type T = z.infer<S>;
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = useCallback(
    (data: unknown): T | null => {
      const result = schema.safeParse(data);
      if (result.success) {
        setErrors({});
        return result.data;
      }
      const fieldErrors: Record<string, string> = {};
      for (const issue of result.error.issues) {
        const key = issue.path.join(".") || "_root";
        if (!fieldErrors[key]) fieldErrors[key] = issue.message;
      }
      setErrors(fieldErrors);
      // Show the first error as a toast for visibility
      const firstError = Object.values(fieldErrors)[0];
      if (firstError) toast.error(firstError);
      return null;
    },
    [schema]
  );

  const clearErrors = useCallback(() => setErrors({}), []);
  const clearError = useCallback((field: string) => setErrors((prev) => { const next = { ...prev }; delete next[field]; return next; }), []);
  const setFieldError = useCallback((field: string, message: string) => setErrors((prev) => ({ ...prev, [field]: message })), []);

  return { errors, validate, clearErrors, clearError, setFieldError };
}
