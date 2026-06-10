import type { NextRequest } from "next/server";
import { auth, authDisabled } from "@/auth";

// Authenticated server-side proxy to the FastAPI backend. The browser only
// ever talks to this route; the backend URL and bearer token stay server-side.
// /api/auth/* is handled by the more-specific NextAuth route, not this one.

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";
const API_AUTH_TOKEN = process.env.API_AUTH_TOKEN ?? "";

// Allow long-running streams (AI chat/memos) up to the plan limit.
export const maxDuration = 300;

async function proxy(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  if (!authDisabled) {
    const session = await auth();
    if (!session?.user) {
      return Response.json({ detail: "unauthorized" }, { status: 401 });
    }
  }

  const { path } = await params;
  const url = new URL(`${BACKEND_URL}/api/${path.join("/")}`);
  url.search = req.nextUrl.search;

  const headers = new Headers();
  for (const name of ["content-type", "accept"]) {
    const v = req.headers.get(name);
    if (v) headers.set(name, v);
  }
  if (API_AUTH_TOKEN) headers.set("authorization", `Bearer ${API_AUTH_TOKEN}`);

  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  let res: Response;
  try {
    res = await fetch(url, {
      method: req.method,
      headers,
      body: hasBody ? req.body : undefined,
      // streaming request bodies (CSV uploads) require half-duplex
      ...(hasBody ? { duplex: "half" as const } : {}),
      cache: "no-store",
    });
  } catch {
    return Response.json({ detail: "backend unreachable" }, { status: 502 });
  }

  // Stream the response through so SSE (AI chat) works end to end.
  const out = new Headers();
  for (const name of ["content-type", "cache-control"]) {
    const v = res.headers.get(name);
    if (v) out.set(name, v);
  }
  return new Response(res.body, { status: res.status, headers: out });
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as DELETE, proxy as PATCH };
