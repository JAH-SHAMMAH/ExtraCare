import type { MetadataRoute } from "next";

export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://fairviewschoolng.com";

export const SEO_KEYWORDS = [
  "Fairview School Portal",
  "Fairview School",
  "school portal",
  "student records",
  "parent portal",
  "school attendance",
  "school management software",
  "school ERP Nigeria",
];

export const INDUSTRY_LANDING_PAGES = [
  {
    path: "/erp-for-schools",
    title: "Fairview School Portal",
    description:
      "Run student records, attendance, exams, fees, timetable, transport, CBT, HR, and academic reporting in one secure school portal.",
    keywords: [
      "school management software",
      "school portal",
      "school ERP Nigeria",
      "student records management",
      "parent portal",
    ],
  },
] as const;

export function canonical(path: string): string {
  return new URL(path, SITE_URL).toString();
}

export function landingMetadata(path: string): MetadataRoute.Sitemap[number] {
  return {
    url: canonical(path),
    lastModified: new Date(),
    changeFrequency: "weekly",
    priority: path === "/" ? 1 : 0.9,
  };
}

export function softwareSchema(input: {
  name: string;
  description: string;
  path: string;
  category: string;
  keywords: readonly string[];
}) {
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: input.name,
    applicationCategory: "BusinessApplication",
    applicationSubCategory: input.category,
    operatingSystem: "Web",
    description: input.description,
    url: canonical(input.path),
    brand: {
      "@type": "Brand",
      name: "Fairview School Portal",
    },
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "NGN",
      availability: "https://schema.org/InStock",
    },
    keywords: input.keywords.join(", "),
  };
}

export function faqSchema(items: Array<{ question: string; answer: string }>) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: items.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: item.answer,
      },
    })),
  };
}
