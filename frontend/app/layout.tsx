import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { SEO_KEYWORDS, SITE_URL } from "@/lib/seo";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "Fairview School Portal",
    template: "%s | Fairview School Portal",
  },
  description:
    "The official Fairview School portal for students, parents, teachers, and staff — admissions, attendance, results, timetable, HR, finance, and school communications.",
  keywords: SEO_KEYWORDS,
  alternates: { canonical: "/" },
  openGraph: {
    title: "Fairview School Portal",
    description:
      "The official Fairview School portal for students, parents, teachers, and staff.",
    url: SITE_URL,
    siteName: "Fairview School Portal",
    type: "website",
    locale: "en_NG",
  },
  twitter: {
    card: "summary_large_image",
    title: "Fairview School Portal",
    description:
      "The official Fairview School portal for students, parents, teachers, and staff.",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-snippet": -1,
      "max-image-preview": "large",
      "max-video-preview": -1,
    },
  },
  // Browser tab + PWA. Next's metadata API emits the equivalent of the guide's
  // <head> <link> tags; manifest ties into the PWA / Mobile Manager install icon.
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/favicon-32.png", type: "image/png", sizes: "32x32" },
      { url: "/favicon-16.png", type: "image/png", sizes: "16x16" },
    ],
    apple: "/apple-touch-icon.png",
  },
  manifest: "/manifest.webmanifest",
};

// theme_color for the address bar / PWA splash (crest green).
export const viewport: Viewport = {
  themeColor: "#1d8a3a",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="font-sans" suppressHydrationWarning>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
