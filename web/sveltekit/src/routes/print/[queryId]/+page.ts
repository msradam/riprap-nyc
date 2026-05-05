// The print route hydrates from localStorage on the client; nothing to
// prerender or SSR. SPA fallback (200.html) handles the URL.
export const prerender = false;
export const ssr = false;
