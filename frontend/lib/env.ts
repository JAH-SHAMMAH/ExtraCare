import { z } from "zod";

// Runtime environment variable validation
// Throws at module load if required variables are missing or malformed

const envSchema = z.object({
  NEXT_PUBLIC_API_URL: z.string().url("NEXT_PUBLIC_API_URL must be a valid URL").default("http://localhost:8000"),
  NEXT_PUBLIC_APP_NAME: z.string().default("ExtraCare ERP"),
  NEXT_PUBLIC_DEFAULT_LOCALE: z.string().default("en-NG"),
  NEXT_PUBLIC_DEFAULT_CURRENCY: z.string().default("NGN"),
  NEXT_PUBLIC_ENABLE_ANALYTICS: z.string().default("false").transform((v) => v === "true"),
  NEXT_PUBLIC_ENABLE_BETA: z.string().default("false").transform((v) => v === "true"),
});

function loadEnv() {
  const raw = {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
    NEXT_PUBLIC_APP_NAME: process.env.NEXT_PUBLIC_APP_NAME,
    NEXT_PUBLIC_DEFAULT_LOCALE: process.env.NEXT_PUBLIC_DEFAULT_LOCALE,
    NEXT_PUBLIC_DEFAULT_CURRENCY: process.env.NEXT_PUBLIC_DEFAULT_CURRENCY,
    NEXT_PUBLIC_ENABLE_ANALYTICS: process.env.NEXT_PUBLIC_ENABLE_ANALYTICS,
    NEXT_PUBLIC_ENABLE_BETA: process.env.NEXT_PUBLIC_ENABLE_BETA,
  };

  const result = envSchema.safeParse(raw);

  if (!result.success) {
    const errorMessages = result.error.issues
      .map((i) => `  ${i.path.join(".")}: ${i.message}`)
      .join("\n");
    // During build, warn instead of throwing to avoid blocking CI
    if (typeof window === "undefined") {
      console.warn(`[env] Environment validation warnings:\n${errorMessages}`);
    }
    return envSchema.parse({ ...raw, NEXT_PUBLIC_API_URL: raw.NEXT_PUBLIC_API_URL || "http://localhost:8000" });
  }

  return result.data;
}

export const env = loadEnv();
