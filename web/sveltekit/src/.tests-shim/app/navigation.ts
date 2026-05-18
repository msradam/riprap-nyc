/**
 * Shim for `$app/navigation` — no-op in unit tests. Tests that need
 * to assert on navigation can spy on these via vi.mock.
 */
export async function goto(_url: string | URL, _opts?: unknown): Promise<void> {
  return;
}
export async function invalidate(_url?: string | URL): Promise<void> { return; }
export async function invalidateAll(): Promise<void> { return; }
export async function preloadData(_url: string | URL): Promise<unknown> { return null; }
export async function preloadCode(_urls: string | URL | string[]): Promise<void> { return; }
export function pushState(_url: string | URL, _state: unknown): void { return; }
export function replaceState(_url: string | URL, _state: unknown): void { return; }
export function afterNavigate(_fn: () => void): void { return; }
export function beforeNavigate(_fn: () => void): void { return; }
export function onNavigate(_fn: () => void): void { return; }
export function disableScrollHandling(): void { return; }
