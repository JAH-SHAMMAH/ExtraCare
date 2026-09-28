import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * A structural guard on the sidebar's nav manifest.
 *
 * WHY THIS EXISTS, and why the permission test beside it was not enough:
 * Result Analysis shipped gated correctly — `canAccessPath` returned true for the
 * classroom tier, `RouteGuard` let a teacher through, the route answered — and a
 * class teacher still could not find it, because the entry had been put in the
 * Academics section instead of the report sections. Every permission assertion
 * passed while the feature was, in practice, unreachable.
 *
 * Permission tests answer "may she open it". This answers "can she find it".
 *
 * It reads the manifest as SOURCE rather than importing it, because Sidebar.tsx
 * is a React component wired to stores, routing and icons; standing all that up
 * in a unit test would test the harness rather than the manifest. The parse is
 * deliberately dumb — section key, then the hrefs until the next section — so it
 * fails loudly if the file's shape changes rather than silently matching nothing.
 */

const SRC = readFileSync(
  join(__dirname, "..", "components", "layout", "Sidebar.tsx"),
  "utf8",
);

/** section key -> hrefs listed under it, in order. */
function sectionsFromManifest(src: string): Record<string, string[]> {
  const out: Record<string, string[]> = {};
  const keyRe = /key:\s*"([a-z0-9-]+)"/g;
  const found: { key: string; at: number }[] = [];
  let m: RegExpExecArray | null;
  while ((m = keyRe.exec(src))) found.push({ key: m[1], at: m.index });

  found.forEach((entry, i) => {
    const end = i + 1 < found.length ? found[i + 1].at : src.length;
    const chunk = src.slice(entry.at, end);
    const hrefs = [...chunk.matchAll(/href:\s*"([^"]+)"/g)].map((x) => x[1]);
    out[entry.key] = hrefs;
  });
  return out;
}

const SECTIONS = sectionsFromManifest(SRC);
const REPORT_SECTIONS = ["nursery-report", "primary-report", "secondary-report"];
const RESULT_ANALYSIS = "/dashboard/modules/school/result-analysis";

describe("sidebar nav manifest", () => {
  it("parses the sections it is about to assert on", () => {
    // If this fails, the parse broke — every assertion below would pass or fail
    // for the wrong reason, so it is checked first.
    for (const key of REPORT_SECTIONS) {
      expect(Object.keys(SECTIONS)).toContain(key);
      expect(SECTIONS[key].length).toBeGreaterThan(3);
    }
  });

  it.each(REPORT_SECTIONS)("puts Result Analysis in %s", (key) => {
    expect(SECTIONS[key]).toContain(RESULT_ANALYSIS);
  });

  it.each(REPORT_SECTIONS)("keeps Result Analysis beside Grade Analysis in %s", (key) => {
    // They answer the same question at different cuts, so they belong together.
    // Adjacency is asserted because "present somewhere in a 12-item list" is how
    // a link ends up findable only by someone who already knows it is there.
    const items = SECTIONS[key];
    const ga = items.indexOf("/dashboard/modules/school/grade-analysis");
    const ra = items.indexOf(RESULT_ANALYSIS);
    expect(ga).toBeGreaterThan(-1);
    expect(Math.abs(ra - ga)).toBe(1);
  });

  it("does not also leave it in Academics", () => {
    // Listed in two sections, a teacher sees it twice and an admin wonders which
    // one is the real one. It is a report tool; it lives with the report tools.
    expect(SECTIONS["academics"] ?? []).not.toContain(RESULT_ANALYSIS);
  });

  it("gives every report section the same core report tools", () => {
    // The bug was an entry in the wrong section, so the guard is that the three
    // levels do not silently drift apart in what they offer.
    const core = [
      "/dashboard/modules/school/reports-view",
      "/dashboard/modules/school/make-report",
      "/dashboard/modules/school/report-entry",
      "/dashboard/modules/school/grade-analysis",
      RESULT_ANALYSIS,
    ];
    for (const key of REPORT_SECTIONS) {
      for (const href of core) {
        expect(SECTIONS[key], `${key} is missing ${href}`).toContain(href);
      }
    }
  });
});
