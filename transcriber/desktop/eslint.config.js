/*
 * eslint.config.js
 * Check source and test code without linting generated builds or Python assets.
 */
import js from '@eslint/js';
import tseslint from 'typescript-eslint';
export default tseslint.config(
  {
    ignores: [
      'dist/**',
      'src-tauri/**',
      'test-results/**',
      'node_modules/**',
      'packaging/generated/**',
      'tests/fixtures/**',
    ],
  },
  { ...js.configs.recommended, files: ['**/*.{js,mjs,ts,tsx}'] },
  ...tseslint.configs.recommended,
  {
    languageOptions: {
      globals: {
        console: 'readonly',
        process: 'readonly',
        setTimeout: 'readonly',
        clearTimeout: 'readonly',
        URL: 'readonly',
        fetch: 'readonly',
      },
    },
  },
  { files: ['**/*.{js,mjs}'], rules: { '@typescript-eslint/no-require-imports': 'off' } },
);
