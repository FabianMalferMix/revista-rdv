// ESLint para los guiones del sitio, backend/static/js/. Fija su dialecto: ES2020 en guiones
// clásicos (sin módulos), que el navegador ejecuta tal cual, sin compilar; una sintaxis
// posterior no pasa. Las reglas son las recomendadas: variables sin declarar, sin usar o
// repetidas. Se corre desde la raíz del repositorio:
//
//   tools/ux/node_modules/.bin/eslint -c tools/ux/eslint.config.mjs backend/static/js
import js from '@eslint/js';
import globals from 'globals';

export default [
  js.configs.recommended,
  {
    languageOptions: {
      ecmaVersion: 2020,
      sourceType: 'script',
      globals: globals.browser,
    },
  },
];
