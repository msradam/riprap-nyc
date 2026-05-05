import js from '@eslint/js';
import ts from 'typescript-eslint';
import svelte from 'eslint-plugin-svelte';
import globals from 'globals';

/** @type {import('eslint').Linter.Config[]} */
export default [
  js.configs.recommended,
  ...ts.configs.recommended,
  ...svelte.configs['flat/recommended'],
  {
    languageOptions: {
      globals: { ...globals.browser, ...globals.node }
    }
  },
  {
    files: ['**/*.svelte'],
    languageOptions: {
      parserOptions: { parser: ts.parser, extraFileExtensions: ['.svelte'] }
    }
  },
  {
    languageOptions: {
      globals: {
        // GeoJSON namespace lives in @types/geojson, available in TS but
        // not declared as a runtime global — silence ESLint's no-undef.
        GeoJSON: 'readonly'
      }
    },
    rules: {
      // Svelte 5 prop-as-state idiom — `let { x } = $props()` shadows are fine.
      'no-self-assign': 'off',
      'no-unused-vars': 'off',
      '@typescript-eslint/no-unused-vars': ['error', {
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_'
      }],
      '@typescript-eslint/no-explicit-any': 'warn',
      // Permitted in Svelte 5 reactive blocks where the rune is the trigger.
      '@typescript-eslint/no-unused-expressions': ['error', { allowShortCircuit: true, allowTernary: true }],
      // External (https://) links and runtime-built /q/<query> URLs don't
      // benefit from SvelteKit's resolve() helper.
      'svelte/no-navigation-without-resolve': 'off'
    }
  },
  {
    ignores: [
      'build/**',
      '.svelte-kit/**',
      'node_modules/**',
      'playwright-report/**',
      'test-results/**'
    ]
  }
];
