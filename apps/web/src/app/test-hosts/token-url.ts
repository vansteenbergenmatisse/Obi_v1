/**
 * Plain (non-"use client") helper so the server-component `page.tsx` files can call it directly
 * at render time — a Server Component may only render a "use client" file's exports as JSX, never
 * call a plain function from one (Next.js RSC boundary rule; this used to live inside
 * `test-host-content.tsx` and broke `next build`'s static prerender of every `/test-hosts/*` page
 * with "Attempted to call tokenUrlFor() from the server but tokenUrlFor is on the client").
 */
export function tokenUrlFor(name: string): string {
  return `/api/test-hosts/${name}/obi-token`;
}
