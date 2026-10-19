/** @type {import('next').NextConfig} */
const nextConfig = {
  // Emit a self-contained server bundle (.next/standalone/server.js) so the
  // production Dockerfile's `COPY .next/standalone` works. Required for the
  // containerized deploy; no effect on app behaviour.
  output: "standalone",
  reactStrictMode: true,
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**" },
    ],
  },
  poweredByHeader: false,
  async headers() {
    const csp = [
      "default-src 'self'",
      "base-uri 'self'",
      "object-src 'none'",
      "frame-ancestors 'none'",
      "form-action 'self'",
      "img-src 'self' data: blob: https:",
      "media-src 'self' blob: https:",
      "font-src 'self' data: https:",
      "style-src 'self' 'unsafe-inline' https:",
      // Next.js injects small inline scripts to start the page, so 'unsafe-inline' is still needed here.
      "script-src 'self' 'unsafe-inline'" + (process.env.NODE_ENV === "production" ? "" : " 'unsafe-eval'"),
      "connect-src 'self' https: wss:",
      "frame-src 'self' https:",
      "worker-src 'self' blob:",
      ...(process.env.NODE_ENV === "production" ? ["upgrade-insecure-requests"] : []),
    ].join("; ");
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(self), microphone=(self), geolocation=(), payment=()" },
          { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
          { key: "Cross-Origin-Opener-Policy", value: "same-origin-allow-popups" },
        ],
      },
      {
        // The service worker must not be cached for long, or a fix to it would not reach phones.
        source: "/sw.js",
        headers: [{ key: "Cache-Control", value: "no-cache" }, { key: "Service-Worker-Allowed", value: "/" }],
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
