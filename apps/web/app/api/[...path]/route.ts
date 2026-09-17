import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

function apiOrigin(): string {
  const url = process.env.API_PROXY_URL || "http://127.0.0.1:8000";
  return url.replace(/\/$/, "");
}

function forwardHeaders(request: NextRequest): Headers {
  const headers = new Headers();
  request.headers.forEach((value, key) => {
    const lower = key.toLowerCase();
    if (lower === "host" || lower === "connection" || lower === "content-length") return;
    headers.set(key, value);
  });
  return headers;
}

async function proxy(request: NextRequest, path: string[]): Promise<NextResponse> {
  const target = `${apiOrigin()}/api/${path.join("/")}${request.nextUrl.search}`;
  const method = request.method.toUpperCase();
  const init: RequestInit & { duplex?: "half" } = {
    method,
    headers: forwardHeaders(request),
    redirect: "manual",
  };
  if (method !== "GET" && method !== "HEAD") {
    init.body = request.body;
    init.duplex = "half";
  }

  let upstream: Response;
  try {
    upstream = await fetch(target, init);
  } catch {
    return NextResponse.json(
      {
        detail:
          "Cannot reach the API. Set API_PROXY_URL on Vercel to your deployed FastAPI URL and redeploy.",
      },
      { status: 502 },
    );
  }

  const responseHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    const lower = key.toLowerCase();
    if (lower === "transfer-encoding") return;
    responseHeaders.append(key, value);
  });

  return new NextResponse(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

type RouteContext = { params: Promise<{ path: string[] }> };

async function handle(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return proxy(request, path);
}

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
export const OPTIONS = handle;
