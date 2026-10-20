/**
 * Turn pasted lines like
 *   "Mr Jeremiah CRS, secondary"
 *   "Mrs Juliet French primary"
 * into rows for the bulk teacher form. Anything it guesses wrong is editable on
 * the preview table, so this errs towards "one row per line, nothing dropped".
 */
export interface BulkRow {
  title: string;
  first_name: string;
  last_name: string;
  subject: string;
  department: string;
  email: string;
}

const TITLES = new Set(["mr", "mrs", "ms", "miss", "mx", "dr", "prof", "mal", "engr", "pastor", "sir", "madam", "mdm"]);
const DEPT_WORDS = new Set(["primary", "secondary", "nursery", "eyfs", "junior", "senior", "creche", "playgroup", "kindergarten"]);

export function parseTeacherLines(text: string): BulkRow[] {
  const rows: BulkRow[] = [];
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim().replace(/[;|\t]+/g, ",");
    if (!line) continue;

    let left = line;
    let department = "";
    const comma = line.lastIndexOf(",");
    if (comma >= 0) {
      left = line.slice(0, comma);
      department = line.slice(comma + 1).trim();
    }
    let tokens = left.split(/[\s,]+/).filter(Boolean);

    // No comma: the department is the last word ("early years" is two).
    if (!department && tokens.length > 1) {
      const last = tokens[tokens.length - 1].toLowerCase();
      const last2 = tokens.length > 2 ? `${tokens[tokens.length - 2]} ${tokens[tokens.length - 1]}`.toLowerCase() : "";
      if (last2 === "early years") { department = "Early Years"; tokens = tokens.slice(0, -2); }
      else if (DEPT_WORDS.has(last)) { department = tokens[tokens.length - 1]; tokens = tokens.slice(0, -1); }
    }

    let title = "";
    if (tokens.length > 1 && TITLES.has(tokens[0].toLowerCase().replace(/\.$/, ""))) {
      title = tokens[0].replace(/\.$/, ""); tokens = tokens.slice(1);
    }
    if (!tokens.length) continue;
    const [first, ...rest] = tokens;
    rows.push({
      title: title ? title[0].toUpperCase() + title.slice(1).toLowerCase() : "",
      first_name: first,
      last_name: "",
      subject: rest.join(" "),
      department: department.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase()),
      email: "",
    });
  }
  return rows;
}
