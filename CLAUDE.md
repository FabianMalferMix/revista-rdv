# Reglas para trabajar en este repositorio

Sitio del colectivo de poesía Repitentes del Verso: Django 5.2 LTS, htmx, PostgreSQL, Celery y Redis, tras Caddy y en Docker. Cada regla, con un ejemplo del propio código, está en `CONTRIBUTING.md` («Reglas del código»).

- El trabajo pendiente está en `docs/backlog-codigo.md`: un ticket, un PR.
- Las decisiones, con su porqué, están en `docs/deferidos-y-decisiones.md`. Una decisión registrada no se reabre sin preguntarle al dueño.
- Algunas reglas describen el destino del backlog. Mientras su ticket no esté hecho, se sigue el patrón vigente más cercano y no se agrava la deuda.

## Código

1. **Dónde va cada cosa.**
   - Las consultas reutilizables, en métodos de QuerySet.
   - Los cambios de estado, en `services.py` o `workflow.py`.
   - Los cálculos visuales, en templatetags.
   - Las señales, en `signals.py`.
   - Lo transversal, en `config/`, nunca en la app que se está tocando.
2. **Lo publicable.** La regla de visibilidad vive en el modelo y no se reescribe a mano. Toda relación hacia algo publicable respeta su estado.
3. **Un dato, una fuente.** Si un valor debe coincidir en varias capas (Python, CSS, JS, plantillas, Caddy), se decide en un lugar y viaja: atributos `data-`, propiedades CSS, `reverse()`. Si no se puede, una prueba de la relación entre la fuente y la copia.
4. **Idioma.**
   - Los identificadores nuevos de Python y de JavaScript, en inglés.
   - En castellano, los textos visibles y el vocabulario del diseño: clases CSS y nombres de componentes (tirada, estante, pliego, cápsula), que se usan tal cual también dentro de nombres en inglés.
   - Lo existente no se renombra.
5. **Comentarios.**
   - Dicen qué hace el código hoy y qué restricción lo explica (CSP, accesibilidad, rendimiento).
   - La historia («antes…», «el dueño pidió…») va en el commit.
   - En el código no van identificadores de ticket, de decisión ni de sesión: `tools/ci/decision_refs.py` los cuenta y el CI falla si crecen.
   - Una garantía de seguridad o de privacidad no se escribe como comentario: se escribe una prueba.
6. **Errores.**
   - Nada de `except Exception: return` sin registro: lo esperado, `logger.warning`; lo inesperado, `logger.exception`.
   - Los controles de privacidad fallan cerrados.
   - Un proceso solo declara éxito cuando lo verificó.
7. **Lo que sale del sistema.** Exportaciones, logs, Sentry y archivos servidos, con listas blancas por fila y por campo. A las tareas se les pasan identificadores, no datos personales.
8. **URL públicas.**
   - Son permanentes: renombrar una ruta exige dejar la vieja con `RedirectView(permanent=True)`.
   - El slug de lo publicado no se cambia, y el GUID de un ítem de feed no cambia nunca.
9. **Tareas y migraciones.**
   - Cada tarea declara sus límites y su política de reintento, y se encola con `delay_on_commit`.
   - Toda migración de datos lleva su prueba.
   - Los cambios de esquema van en dos pasos (primero añadir, después quitar), para que el código anterior siga funcionando mientras se despliega.
   - Los permisos de un modelo nuevo se reparten a los roles de forma explícita.
10. **Pruebas.**
    - Comprueban lo que ve o hace una persona.
    - Un `.css` o un `.js` solo se lee para afirmar una invariante, nunca para buscar el literal que se acaba de escribir.
    - Toda prueba de «no aparece» lleva un control positivo.
    - Los permisos se prueban por HTTP, con los grupos reales.
    - Si una prueba falla tras un cambio de diseño, no se copia el valor nuevo sin preguntarse qué vigilaba.
11. **Herramientas de desarrollo.** No van en las apps de producción ni se protegen con `--force`. Hay un solo camino para poblar desarrollo.

## Flujo

- **Rama y commit.** Una rama desde `main` por ticket, en kebab-case descriptivo. Commit: `rama: qué cambia (Bxx)`.
- **Título del PR:** `rama — qué cambia (Bxx)`, con la lista de `.github/pull_request_template.md` en el cuerpo.
- **Antes de abrir el PR**, dentro del contenedor `web`, en verde: `ruff check .`, `ruff format --check .`, `pytest`, `python manage.py makemigrations --check --dry-run` y `python manage.py check`. Después, el CI de GitHub Actions: pip-audit y gitleaks solo corren allí.
- **Fusión** con commit de fusión (no squash), con el CI en verde, y se borra la rama. «Estado» y el avance del backlog se actualizan en el mismo PR.
- **Archivos uno por uno.** Nunca `git add` de carpetas enteras: en `docs/` hay un documento personal que no es del repositorio.
- **Lo visual.** Lo que cambia algo a la vista se le muestra al dueño antes de fusionar: a 951 px, que es su ventana, y en el teléfono, con alternativas si hay más de una manera. Lo que él aprueba manda.
