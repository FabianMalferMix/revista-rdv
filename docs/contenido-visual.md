# Contenido visual: qué material necesita el sitio y cómo reemplazar los marcadores

> Para el colectivo. Todo lo que hoy se ve en el sitio de desarrollo con la etiqueta
> «provisional» lo dibujó un comando (`seed_material_generico`) para poder diseñar con
> proporciones reales. Cada pieza se reemplaza desde el panel sin tocar código.

## Cómo reemplazar una pieza

1. Panel → **Medios → Recursos → Añadir**: sube el archivo, escribe el texto alternativo
   (qué se ve) y el crédito (quién la hizo). Guarda.
2. Abre el objeto (integrante, evento, publicación, registro, aliado, texto) y en su campo
   de imagen selecciona el recurso nuevo. Guarda.
3. El marcador queda en la biblioteca sin usarse; se puede borrar desde Recursos (todos
   llevan «provisional» en el texto alternativo, así que se filtran fácil).

Los derivados para pantalla (480, 960 y 1440 px) se generan solos al subir; no hace falta
preparar tamaños. La obra de la portada, además, sale en AVIF y WebP hasta 2560 px al
elegirla en el perfil del sitio.

## Lo que falta, pieza por pieza

| Pieza | Formato mínimo | Dónde se usa | Campo del panel |
|---|---|---|---|
| Retrato de cada integrante | 1200×1500 px (4:5), color, fondo neutro, mirando a cámara | rejilla y cinta de integrantes, ficha, dossier | Integrante → Foto |
| Seis fotos por lectura | 3:2, ≥ 2400 px de ancho, con nombre de quien fotografió | galería y ficha del evento | Evento → Fotos (pie y crédito) |
| Afiche de cada evento | PDF o PNG a 300 dpi, el original de imprenta | agenda, próxima actividad, ficha, portada | Evento → Afiche |
| Cubierta de cada publicación y una foto del libro en mano | 1000×1400 px (5:7); foto 3:2 | catálogo, ficha, portada, dossier | Publicación → Cubierta |
| Fotograma de cada registro | 1920×1080 px, un plano nítido de la lectura | placa del reproductor, listado, destacado | Registro → Póster |
| Logo de cada aliado y medio | SVG o PNG ≥ 600 px, sobre fondo transparente o blanco | aliados y dossier | Aliado → Logo; Prensa → Logo |
| Obra de la portada | horizontal, ≥ 2400 px de ancho, con una zona clara y tranquila abajo, donde va el logo en tinta | la primera vista de la portada, a sangre; sin ella va la lámina del colectivo | Perfil del sitio → Imagen de portada |
| Recorte de la obra para el teléfono (opcional) | vertical, ≥ 1080 px de ancho (1:2) | la portada en el teléfono; sin él, se recorta la horizontal por el centro | Perfil del sitio → Imagen de portada para el teléfono |
| Foto de grupo | 2400×1260 px, horizontal | la imagen al compartir en redes y el logo de los datos estructurados (la portada no la usa: lleva el nombre escrito y lo repetiría) | Perfil del sitio → og_image |
| Ciudad o comuna | texto | cejilla de la portada, ficha, dossier | Perfil → Ubicación |
| Correo de gestión | texto, solo si existe de verdad | portada, pie, dossier | Perfil → Correo de gestión |
| Manifiesto propio | 60 a 120 palabras | portada (recortado) y dossier (entero) | Perfil → Manifiesto |
| Lema propio (opcional) | seis palabras o menos | solo si se quiere que sea el titular de la portada | Perfil → Lema |

## Qué no hace falta

- Recortar ni redimensionar: el sitio lo hace.
- Fotos de stock: un marcador honesto vale más que una foto ajena.
- Más de seis fotos por lectura: tres buenas bastan para empezar.

## Para desarrollo

```bash
docker compose exec web python manage.py seed_material_generico            # genera y asigna
docker compose exec web python manage.py seed_material_generico --fotos-por-evento 3
```

Idempotente: vuelve a correr sin duplicar. Nunca reemplaza una pieza cuyo crédito no sea de
marcador, así que es seguro ejecutarlo después de cargar material real.
