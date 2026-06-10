import { NextResponse } from "next/server";
import { auth, authDisabled } from "@/auth";

// Next.js 16 convention: proxy.ts replaces middleware.ts. NextAuth's `auth`
// acts as the proxy: unauthenticated page requests are redirected to /signin
// via the `authorized` callback. API routes are excluded by the matcher —
// the catch-all /api proxy route returns 401 JSON itself.
export default authDisabled ? () => NextResponse.next() : auth;

export const config = {
  matcher: ["/((?!api|signin|_next/static|_next/image|favicon.ico).*)"],
};
