# Plan de ejecución del backlog UX/UI

> Ejecución lineal, paso a paso, en sesiones con Claude. Cada paso es un PR. Las casillas
> son el estado: tras un corte, se retoma en el primer paso sin marcar. Fuente de los
> tickets: `docs/backlog-ux-ui.md`; fuente de los hallazgos: `docs/auditoria-ux-ui.md`.
> Inicio: 2026-10-08.

## Reglas de la sesión

- Un paso = una rama desde `main` y un PR; con su CI en verde,
  `gh pr merge --merge --delete-branch --subject "Merge <rama> — <efecto>"` y `git pull --ff-only`
  en `main`. Es el flujo de §0 del backlog.
- Antes de cada PR: `ruff check` y `ruff format`, la suite completa en verde, y capturas de
  las páginas afectadas con `tools/ux` (desde el paso 2). Las capturas quedan en
  `tools/ux/out/<rama>/`; la tabla de métricas va en la descripción del PR.
- Después de cada merge: comprobar que el CI de `main` queda verde antes de abrir el siguiente.
- La base de desarrollo lleva la identidad real y el material genérico del comando
  `seed_material_generico`: no ejecutar `seed_demo`.
- Puntos de control (◆): el dueño del sitio mira el resultado en el navegador y aprueba
  seguir. Son los momentos donde el aspecto cambia de verdad.
- Si un ticket cita una línea o archivo que ya no coincide, se corrige el backlog en el mismo PR.

## Pasos

- [x] **0. Material genérico.** Comando `seed_material_generico` con pruebas,
  `docs/contenido-visual.md` y README. Ejecutado en desarrollo: 66 imágenes y manifiesto
  provisional. Entra al repo en el paso 1.
- [x] **1. PR `docs-auditoria-y-backlog`.** Sube auditoría, backlog, este plan,
  contenido-visual, el comando con sus pruebas y el README. Sin cambios de interfaz.
- [x] **2. PR `ux-0-herramienta-y-linea-base`.** Tickets 0.1 y 0.2: `tools/ux` y la línea
  base en `tools/ux/out/baseline/` (no versionada: se regenera con `capture.js`).
- [x] **3. PR `ux-1a-imagenes-y-lectura`.** Tickets 1.1 y 1.3. El arreglo más visible del
  sitio: proporción real de imágenes, medida de lectura, interlíneas, mínimos de 12 px.
- [x] **4. PR `ux-1b-indices-y-lenguaje`.** Tickets 1.2 y 1.12: cabecera de índice en los
  once índices, cejillas sin repetir, títulos de pestaña.
- [x] **5. PR `ux-1c-cinta`.** Ticket 1.4: pausa real, icono de pausa discreto sin JS, fila en táctil (D1, D12).
- [ ] **6. PR `ux-1d-componentes`.** Tickets 1.5, 1.6, 1.7 y 1.8: buscador en el viewport,
  tokens de motion, `.rotulo` y `.btn`, preload de Syne.
- [ ] **7. PR `ux-1e-color`.** Ticket 1.9: reasignación del magenta y matriz de pares.
- [ ] **8. PR `ux-1f-paginacion-formulario-vacios`.** Tickets 1.10, 1.11 y 1.13.
- ◆ **Punto de control A.** Portada, un índice, la cinta y el formulario.
- [ ] **9. PR `ux-2-1-reticula`.** Ticket 2.1: tres carriles, `main` sin `.wrap`, raíz fluida (D7).
- [ ] **10. PR `ux-2-2-indices-y-rejillas`.** Ticket 2.2: filas tipográficas y rejillas anchas.
- [ ] **11. PR `ux-2-3-tipografia`.** Ticket 2.3: Source Serif 4 autoalojada, tokens, mono
  reducida (D3, D4). Requiere descargar la fuente y subconjuntarla con fonttools en local.
- [ ] **12. PR `ux-2-4-lectura-y-fichas`.** Ticket 2.4: sala de lectura, fichas a dos columnas.
- ◆ **Punto de control B.** Poema, artículo, integrantes y publicaciones a 1440 y 1920.
- [ ] **13. PR `ux-3a-superficies-y-amarillo`.** Tickets 3.1 y 3.2 (D5, D6).
- [ ] **14. PR `ux-3b-duotono-y-retratos`.** Tickets 3.3 y 3.6.
- [ ] **15. PR `ux-3c-reproductor`.** Ticket 3.4 (D10).
- [ ] **16. PR `ux-3d-imagenes-del-modelo`.** Ticket 3.5.
- [ ] **17. PR `ux-3e-marca`.** Ticket 3.7: glifo, favicon, theme-color, tarjeta og.
- ◆ **Punto de control C.** Registros, galería, aliados y la marca en la cabecera.
- [ ] **18. PR `ux-4-1-cabecera`.** Ticket 4.1 (D2, D9: cambia `test_ia.py`).
- [ ] **19. PR `ux-4-2-hero`.** Ticket 4.2 (D8, D9: cambia `test_catalog.py`). Si se alarga,
  partir en dos: hero sin objeto; luego objeto, cifras y línea de respaldo.
- [ ] **20. PR `ux-4-3-portada`.** Ticket 4.3: orden y bloques, poemas en portada.
- [ ] **21. PR `ux-4-4-pie-y-enlaces`.** Tickets 4.4 y 4.5.
- ◆ **Punto de control D.** Portada completa en 1440, 1920 y 390. Avisar al colectivo de D9
  (barra de cinco, prensa y aliados de vuelta como línea de respaldo).
- [ ] **22. PR `ux-5-1-dossier`.** Ticket 5.1 (D11).
- [ ] **23. PR `ux-5-2-agenda-galeria-aliados`.** Tickets 5.2 y 5.3.
- [ ] **24. PR `ux-5-4-busqueda`.** Ticket 5.4.
- [ ] **25. PR `ux-6-cierre`.** Tickets 6.1, 6.2 y 6.3: accesibilidad, métricas finales
  contra la línea base, documentación y decisiones registradas.
- ◆ **Punto de control final.** Tabla antes/después y criterios de §10 de la auditoría.

## Sesiones previstas

| Sesión | Pasos | Nota |
|---|---|---|
| 1 | 1 a 8 | mecánica; Sonnet alcanza si hay que ahorrar |
| 2 | 9 a 12 | la retícula y la tipografía cambian todo: modelo capaz |
| 3 | 13 a 17 | imagen y color |
| 4 | 18 a 21 | portada y navegación: modelo capaz; tocan pruebas de decisiones |
| 5 | 22 a 25 | secundarias y cierre |

## Cómo retomar tras un corte

1. `git status` y `git branch --show-current`. Si hay una rama abierta, terminar su PR; si
   está en `main` limpio, seguir con el primer paso sin casilla.
2. `docker compose up -d` y comprobar `http://localhost:8000`. No resembrar.
3. Releer §0 y §1 del backlog y el ticket del paso.
4. Marcar la casilla de cada paso en este archivo dentro del PR que lo cierra.
