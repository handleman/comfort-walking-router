import js from '@eslint/js'
import svelte from 'eslint-plugin-svelte'
import globals from 'globals'
import ts from 'typescript-eslint'

export default ts.config(
  { ignores: ['dist/', 'node_modules/', 'package-lock.json'] },
  js.configs.recommended,
  ...ts.configs.recommended,
  ...svelte.configs['flat/recommended'],
  {
    languageOptions: {
      globals: { ...globals.browser },
    },
  },
  {
    files: ['**/*.svelte'],
    languageOptions: {
      parserOptions: {
        parser: ts.parser,
        extraFileExtensions: ['.svelte'],
      },
    },
    rules: {
      // typescript-eslint's no-unused-vars crashes on Svelte components
      // (`getDefinedMessageData` TypeError); the base rule is enough here.
      '@typescript-eslint/no-unused-vars': 'off',
    },
  },
  // Must stay last: turns off rules that conflict with Prettier formatting.
  ...svelte.configs['flat/prettier'],
)
