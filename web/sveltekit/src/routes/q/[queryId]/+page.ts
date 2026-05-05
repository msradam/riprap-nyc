// Live route: SSE-driven, must NOT be prerendered (the queryId is dynamic
// and the data comes from the FastAPI backend at runtime).
export const prerender = false;
export const ssr = false;
