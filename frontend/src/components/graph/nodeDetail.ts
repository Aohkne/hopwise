const PREFERRED_KEYS = [
  "name_en", "dob", "position", "nationality", "birth_place", "height_cm",
  "founded_year", "founded", "headquarters", "industry", "title", "age",
  "launch_year", "website", "wikidata_id",
];

export function pickImage(props: Record<string, unknown>): string | null {
  if (typeof props.image_url === "string") return props.image_url;
  const logos = props.logo_urls;
  if (Array.isArray(logos) && typeof logos[0] === "string") return logos[0];
  return null;
}

export function pickRows(props: Record<string, unknown>): [string, string][] {
  const rows: [string, string][] = [];
  for (const key of PREFERRED_KEYS) {
    const v = props[key];
    if (v !== undefined && v !== null && v !== "" && typeof v !== "object") {
      rows.push([key, String(v)]);
    }
    if (rows.length >= 6) break;
  }
  return rows;
}

