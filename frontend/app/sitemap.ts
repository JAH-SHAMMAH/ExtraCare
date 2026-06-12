import type { MetadataRoute } from "next";
import { canonical, INDUSTRY_LANDING_PAGES, landingMetadata } from "@/lib/seo";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    ...INDUSTRY_LANDING_PAGES.map((page) => landingMetadata(page.path)),
    {
      url: canonical("/login"),
      lastModified: new Date(),
      changeFrequency: "monthly",
      priority: 0.2,
    },
    {
      url: canonical("/register"),
      lastModified: new Date(),
      changeFrequency: "monthly",
      priority: 0.4,
    },
  ];
}
