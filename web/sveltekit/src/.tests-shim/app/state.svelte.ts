/**
 * Shim for `$app/state` in unit tests. SvelteKit provides this module
 * at runtime; under vitest we mount components in isolation so we
 * supply a minimal-but-real $state-backed shape that AppHeader and
 * other shell components read from.
 */
import { goto as _goto } from './navigation';
export { _goto as goto };

class PageState {
  url = $state(new URL('http://localhost/q/test-query'));
  params = $state<Record<string, string>>({ queryId: 'test-query' });
  route = $state<{ id: string | null }>({ id: '/q/[queryId]' });
  data = $state<Record<string, unknown>>({});
  status = $state(200);
  error = $state<Error | null>(null);
  form = $state<unknown>(null);
  state = $state<Record<string, unknown>>({});
}

export const page = new PageState();
export const navigating = $state<{ from: { route: { id: string | null } } | null }>({ from: null });
export const updated = $state({ current: false });
