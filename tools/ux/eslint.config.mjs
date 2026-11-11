// ESLint para los guiones del sitio: los de backend/static/js/ y el que arranca el editor del panel,
// backend/static/admin/richtext_init.js. Fija su dialecto: ES2020 en guiones clásicos (sin
// módulos), que el navegador ejecuta tal cual, sin compilar. Una sintaxis posterior no pasa, y la
// de antes de ES2015 tampoco cuando ES2020 tiene la suya: `let` y `const` en vez de `var` (y
// `const` si no se reasigna), funciones flecha en las llamadas de vuelta, plantillas en vez de
// concatenar textos, la forma corta de los objetos, `...` en vez de `arguments`, `apply` u
// `Object.assign`, y `**` en vez de `Math.pow`. Los guiones clásicos de una página comparten el
// ámbito global: ninguno deja nombres sueltos en él, y lo que comparten va en `window.common`
// (common.js). Además, las recomendadas: variables sin declarar, sin usar o repetidas. Se corre
// desde la raíz del repositorio:
//
//   tools/ux/node_modules/.bin/eslint -c tools/ux/eslint.config.mjs backend/static/js backend/static/admin/richtext_init.js
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
    rules: {
      'no-var': 'error',
      'prefer-const': 'error',
      'prefer-arrow-callback': 'error',
      'prefer-template': 'error',
      'object-shorthand': 'error',
      'prefer-rest-params': 'error',
      'prefer-spread': 'error',
      'prefer-object-spread': 'error',
      'prefer-exponentiation-operator': 'error',
      'no-implicit-globals': ['error', { lexicalBindings: true }],
    },
  },
];
