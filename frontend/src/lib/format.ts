// Formatting of numbers, sizes, dates and prices for display.

const integer = new Intl.NumberFormat("en-US");

export function formatNumber(value: number): string {
  return integer.format(value);
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[unit]}`;
}

/** US dollars, with enough digits that a fraction of a cent still shows. */
export function formatCost(usd: number | null): string {
  if (usd === null) return "—";
  if (usd === 0) return "$0.00";
  if (usd < 0.01) return `$${usd.toPrecision(2)}`;
  return `$${usd.toFixed(usd < 1 ? 4 : 2)}`;
}

export function formatScore(score: number): string {
  return score.toFixed(3);
}

export function formatPercent(part: number, whole: number): string {
  if (whole === 0) return "0%";
  return `${Math.round((part / whole) * 100)}%`;
}

const dateTime = new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" });

export function formatDate(iso: string): string {
  return dateTime.format(new Date(iso));
}

/** "Just now", "5 minutes ago", ... and the date after a week. */
export function formatRelative(iso: string, now = Date.now()): string {
  const seconds = Math.round((now - new Date(iso).getTime()) / 1000);
  if (seconds < 45) return "just now";
  const steps: [number, Intl.RelativeTimeFormatUnit][] = [
    [60, "minute"],
    [3600, "hour"],
    [86400, "day"],
  ];
  const relative = new Intl.RelativeTimeFormat("en-US", { numeric: "auto" });
  for (let i = steps.length - 1; i >= 0; i--) {
    const [size, unit] = steps[i]!;
    if (seconds >= size) {
      const amount = Math.round(seconds / size);
      if (unit === "day" && amount > 7) break;
      return relative.format(-amount, unit);
    }
  }
  return formatDate(iso);
}

/** The name a person gave the file: upload ids are "<random>_<name>". */
export function displayName(fileId: string): string {
  const underscore = fileId.indexOf("_");
  return underscore === -1 ? fileId : fileId.slice(underscore + 1);
}

const LIST_LINE = /^\s*([•▪◦●*–-]|\d{1,3}[.)])\s/;

/**
 * Joins the lines a PDF breaks inside paragraphs, so a passage reads as
 * prose. Blank lines and list lines (bullets, "1.") keep their breaks.
 */
export function reflow(text: string): string {
  return text
    .replace(/\r\n?/g, "\n")
    .split(/\n\s*\n/)
    .map((paragraph) =>
      paragraph
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .reduce((joined, line) => {
          if (!joined) return line;
          if (LIST_LINE.test(line)) return `${joined}\n${line}`;
          // A word split by a hyphen at the line end keeps the hyphen, which
          // is right for compounds ("well-known") and harmless otherwise.
          return joined.endsWith("-") ? joined + line : `${joined} ${line}`;
        }, ""),
    )
    .filter(Boolean)
    .join("\n\n");
}
