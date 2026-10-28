<!--
Título: `rama — qué cambia (Bxx)`, con el ticket de docs/backlog-codigo.md.
Cuenta en prosa qué cambia y por qué: es lo que ya no va en los comentarios del código.
-->

**Qué cambia**

**Cómo se comprobó**

**Lista.** Marca lo que se cumple, borra lo que no aplica y explica lo que quede sin marcar.

- [ ] Si cambia el comportamiento de una regla, se actualizaron su comentario y su prueba de contrato.
- [ ] Si añade un modelo, un campo de archivo, una ruta pública, una tarea o un ajuste de entorno, se decidió de forma explícita qué pasa con el sitemap, la exportación de desarrollo, los roles y la limpieza de archivos.
- [ ] Las pruebas nuevas comprueban comportamiento, y ninguna copia un literal de CSS o de JS.
- [ ] Si hay una migración de datos, tiene prueba, y el código anterior sigue funcionando mientras se despliega.
- [ ] Si toca algo que sale del sistema (logs, Sentry, exportaciones, archivos servidos), aquí se dice qué datos viajan ahora.
- [ ] Se probó también con `DEBUG=0`, en la vista previa de producción, y no solo en desarrollo.
- [ ] Si cambia algo a la vista, el dueño lo vio y lo aprobó.
- [ ] «Estado» y el avance del backlog están actualizados.
