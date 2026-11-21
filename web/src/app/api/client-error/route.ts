/**
 * Browser errors land here and are logged as one JSON line (task 10.3), so the host's log
 * drain (Vercel, Logtail, ...) or Sentry's log ingestion can alert on them.
 */
export async function POST(request: Request) {
  const text = (await request.text()).slice(0, 8000);
  let report: unknown = text;
  try {
    report = JSON.parse(text);
  } catch {
    // keep as text
  }
  console.error(
    JSON.stringify({ event: "client_error", report, ua: request.headers.get("user-agent") }),
  );
  return new Response(null, { status: 204 });
}
