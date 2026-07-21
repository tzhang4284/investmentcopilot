import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

/** Local-dev escape hatch: AUTH_DISABLED=true skips sign-in entirely. */
export const authDisabled = process.env.AUTH_DISABLED === "true";

const allowedEmails = (process.env.ALLOWED_EMAILS ?? "")
  .split(",")
  .map((e) => e.trim().toLowerCase())
  .filter(Boolean);

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [Google],
  session: { strategy: "jwt" },
  pages: { signIn: "/signin" },
  callbacks: {
    signIn({ user }) {
      // Only emails on the allowlist may sign in — everyone else gets
      // AccessDenied even with a valid Google account.
      const email = user.email?.toLowerCase();
      return !!email && allowedEmails.includes(email);
    },
    authorized({ auth }) {
      return !!auth?.user;
    },
  },
});
