"""Reglas del sistema visual que solo fallan al pintar.

La suite no tiene navegador. Estas pruebas fijan sobre la hoja de estilos las decisiones
del backlog UX (docs/backlog-ux-ui.md) cuyo incumplimiento no rompe nada salvo lo que se
ve: una cubierta deformada, un título con las líneas sueltas, una columna de lectura de
cien letras. Las cifras en pantalla se miden aparte, con tools/ux.
"""

import re
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "static" / "css" / "site.css"


def _css():
    """La hoja sin comentarios: varios citan llaves y selectores a modo de ejemplo."""
    return re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.S)


def _reglas():
    """(selector, declaraciones sin espacios) de cada regla, también dentro de @media."""
    return [
        (selector.strip(), re.sub(r"\s+", "", cuerpo))
        for selector, cuerpo in re.findall(r"([^{}]+)\{([^{}]*)\}", _css())
    ]


def _tokens():
    """Las variables de :root con su valor, sin espacios: {"--t2": "19px", ...}."""
    raiz = re.search(r":root\{(.*?)\n\}", _css(), re.S).group(1)
    return {
        nombre: re.sub(r"\s+", "", valor)
        for nombre, valor in re.findall(r"(--[\w-]+):([^;]+);", raiz)
    }


def _px(valor):
    """Valor de un tamaño en px, resolviendo un token. Para un clamp(), (mínimo, máximo)."""
    valor = re.sub(r"\s+", "", valor)
    token = re.fullmatch(r"var\((--[\w-]+)\)", valor)
    if token:
        valor = _tokens()[token.group(1)]
    pinza = re.fullmatch(r"clamp\(([\d.]+)px,[^,]+,([\d.]+)px\)", valor)
    if pinza:
        return float(pinza.group(1)), float(pinza.group(2))
    fijo = re.fullmatch(r"([\d.]+)px", valor)
    assert fijo, f"tamaño que no sé leer: {valor}"
    return float(fijo.group(1)), float(fijo.group(1))


def _regla(selector):
    """La PRIMERA regla con ese selector: la de pantalla. Las que la sobrescriben dentro
    de un @media (impresión, pantalla estrecha) vienen después en la hoja."""
    encontradas = [cuerpo for sel, cuerpo in _reglas() if re.sub(r"\s+", "", sel) == selector]
    assert encontradas, f"no existe la regla «{selector}» en site.css"
    return encontradas[0]


# ── Imágenes ──────────────────────────────────────────────────────────────


def test_las_imagenes_no_heredan_el_alto_del_atributo_html():
    """`_responsive_img.html` emite width y height para reservar el hueco de la imagen.

    Sin `height:auto` ese alto se aplica literal y gana a `aspect-ratio`: las cubiertas
    se dibujaban a 180×780 y las fotos apaisadas de la galería como tiras verticales.
    Ninguna otra prueba lo veía porque el HTML era correcto.
    """
    cuerpo = _regla("img,video")
    assert "height:auto" in cuerpo, "sin height:auto el alto del atributo HTML se aplica literal"
    assert "max-width:100%" in cuerpo, "una imagen más ancha que su caja desbordaría la página"


def test_toda_imagen_con_proporcion_forzada_deja_el_alto_en_auto():
    """Si una regla fija `aspect-ratio` sobre una imagen, el alto debe quedar libre."""
    sin_auto = [
        selector
        for selector, cuerpo in _reglas()
        if "aspect-ratio" in cuerpo
        and re.search(r"\bimg\b", selector)
        and "height:auto" not in cuerpo
    ]
    assert not sin_auto, f"reglas con aspect-ratio sobre <img> sin height:auto: {sin_auto}"


# ── Tipografía ────────────────────────────────────────────────────────────

# El glifo ▾ del desplegable del menú: es un adorno, no texto que haya que leer.
EXENTOS_DEL_MINIMO = {".nav-disclosure summary::after"}


def test_ningun_texto_baja_de_12px():
    """Nueve reglas pintaban texto a 11px; el mínimo legible del sistema es 12. Los tamaños
    son tokens: se resuelven antes de comparar."""
    pequenos = [
        (selector, tam)
        for selector, cuerpo in _reglas()
        if selector not in EXENTOS_DEL_MINIMO and selector != "html"
        for tam in re.findall(r"font-size:([^;]+)", cuerpo)
        if not tam.endswith("pt") and _px(tam)[0] < 12
    ]
    assert not pequenos, f"texto por debajo de 12px: {pequenos}"


def test_la_escala_es_la_unica_fuente_de_tamanos():
    """Había 25 tamaños escritos a mano: 17, 18, 19 y 20 px convivían sin que ninguno
    significara nada. Ahora cada `font-size` es un paso de la escala. Quedan fuera el
    cuerpo base de `html`, que crece con el monitor y del que cuelgan los `rem`, y la hoja
    de impresión, que mide en puntos. Son diez pasos: --t7, que era el nombre de la portada
    hasta que pasó a ser el logo (D18), volvió como el título de los pliegos de la tirada (D19)."""
    sueltos = [
        (selector, tam)
        for selector, cuerpo in _reglas()
        if selector != "html"
        for tam in re.findall(r"font-size:([^;]+)", cuerpo)
        if not re.fullmatch(r"var\(--t-?\d\)", tam) and not tam.endswith("pt")
    ]
    assert not sueltos, f"tamaños fuera de la escala: {sueltos}"
    escala = {
        nombre: valor for nombre, valor in _tokens().items() if re.fullmatch(r"--t-?\d", nombre)
    }
    assert len(escala) == 10, f"la escala tiene {len(escala)} pasos: {sorted(escala)}"
    minimos = [_px(f"var({nombre})")[0] for nombre in sorted(escala, key=lambda n: int(n[3:]))]
    assert minimos == sorted(minimos), f"la escala no crece de paso en paso: {minimos}"


def test_un_titulo_de_seccion_no_mide_menos_que_el_texto_que_encabeza():
    """Los títulos de sección eran rótulos de 12 px sobre párrafos de 17. El cuerpo crece
    hasta 19 px (119 % del tamaño del navegador): el título de sección empieza por encima."""
    minimo, _ = _px(re.search(r"font-size:([^;]+)", _regla(".subhead")).group(1))
    assert minimo > 19, f"el título de sección arranca en {minimo}px, por debajo del cuerpo"
    titulares = next(sel for sel, cuerpo in _reglas() if "font-family:var(--display)" in cuerpo)
    assert ".subhead" in titulares, "el título de sección debe ir en la tipografía de titulares"


def test_los_titulos_no_heredan_la_interlinea_de_lectura():
    """El 1.6 del cuerpo es para leer párrafos; en un título separa sus líneas."""
    interlinea = re.search(r"line-height:var\((--[\w-]+)\)", _regla("h1,h2,h3"))
    assert interlinea, "los títulos deben fijar su interlínea con un token"
    assert float(_tokens()[interlinea.group(1)]) <= 1.2


def test_el_cuerpo_de_lectura_tiene_medida():
    """A 18px en 780px el artículo corría a 102 letras por línea; lo legible es 45–75."""
    medida = re.search(r"--medida:\s*(\d+)ch", _css())
    assert medida, "falta el token --medida"
    assert 45 <= int(medida.group(1)) <= 66, "la medida en ch quedó fuera del rango de lectura"
    for selector in (".article.body", ".dek", ".member-about"):
        assert "max-width:var(--medida)" in _regla(selector), f"«{selector}» perdió la medida"


def test_el_poema_no_se_parte_con_guiones():
    """El guionado automático empareja la prosa; en un poema el corte es del autor."""
    con_guiones = [selector for selector, cuerpo in _reglas() if "hyphens:auto" in cuerpo]
    assert con_guiones, "ya no hay guionado en pantallas estrechas"
    assert not [s for s in con_guiones if "poem" in s], "el guionado alcanza a los poemas"


# ── Componentes ───────────────────────────────────────────────────────────


def test_ningun_estado_hover_se_marca_bajando_la_opacidad():
    """Tres botones se atenuaban al pasar el ratón: el texto perdía contraste justo al ir
    a pulsarlo. El estado se marca con color sólido."""
    atenuados = [sel for sel, cuerpo in _reglas() if ":hover" in sel and "opacity:" in cuerpo]
    assert not atenuados, f"estados hover por opacidad: {atenuados}"


def test_todo_boton_comparte_una_receta():
    """Había cinco botones con cinco recetas. El del formulario y el del reproductor
    heredan ahora la de `.btn`; ninguno vuelve a fijar su tipografía por su cuenta."""
    receta = [
        (sel, cuerpo) for sel, cuerpo in _reglas() if re.sub(r"\s+", "", sel).startswith(".btn,")
    ]
    assert receta, "desapareció la regla común de los botones"
    selector, cuerpo = receta[0]
    for boton in (".btn", ".form button", ".embed-play"):
        assert boton in selector, f"«{boton}» ya no comparte la receta del botón"
    assert "min-height:44px" in cuerpo, "el botón perdió su alto mínimo de 44 px"
    assert "text-transform:none" in cuerpo, "el botón volvió a las mayúsculas"
    sueltos = [
        sel
        for sel, cuerpo in _reglas()
        if sel != selector
        and re.search(r"\.btn|button|embed-play", sel)
        and "font-family" in cuerpo
    ]
    assert not sueltos, f"botones con tipografía propia: {sueltos}"


# Reglas que pintan texto en mayúsculas fuera de la receta de rótulo. Estaba la navegación,
# como deuda con fecha: salió en el ticket 2.3, al pasar a la tipografía de titulares.
MAYUSCULAS_PENDIENTES = set()


def test_las_mayusculas_son_una_sola_receta():
    """Quince reglas ponían texto en mayúsculas, con seis espaciados distintos."""
    con_mayusculas = {sel for sel, cuerpo in _reglas() if "text-transform:uppercase" in cuerpo}
    receta = {sel for sel in con_mayusculas if sel.startswith(".rotulo")}
    assert len(receta) == 1, f"debe haber exactamente una receta de rótulo: {receta}"
    extra = con_mayusculas - receta - MAYUSCULAS_PENDIENTES
    assert not extra, f"mayúsculas fuera de la receta de rótulo: {extra}"
    espaciado = re.search(r"letter-spacing:var\((--[\w-]+)\)", dict(_reglas())[receta.pop()])
    assert espaciado and _tokens()[espaciado.group(1)] == ".1em"


def test_el_movimiento_usa_los_tokens_y_respeta_a_quien_pide_menos():
    css = _css()
    for token in ("--r-1:", "--dur-fast:", "--dur-base:", "--ease:", "--edge:"):
        assert token in css, f"falta el token {token}"
    sueltas = [
        (sel, cuerpo)
        for sel, cuerpo in _reglas()
        if "transition:" in cuerpo and "var(--dur-" not in cuerpo
    ]
    assert not sueltas, f"transiciones con duración escrita a mano: {[s for s, _ in sueltas]}"
    menos = re.search(r"@media \(prefers-reduced-motion:reduce\)\{(.*?)\n\}", css, re.S)
    assert menos, "falta el bloque global de prefers-reduced-motion"
    assert re.search(r"\*,\s*\*::before,\s*\*::after\{", menos.group(1)), (
        "el bloque debe alcanzar a todo (*), no a una lista de componentes"
    )


def test_los_campos_tienen_un_borde_que_se_ve():
    """El borde de un campo lo delimita: WCAG 1.4.11 pide 3:1. `--border` da 1,17:1."""
    campos = (".search input", ".form input, .form textarea, .form select", ".search-page input")
    for selector in campos:
        cuerpos = [cuerpo for sel, cuerpo in _reglas() if sel == selector]
        assert any("border:1pxsolidvar(--edge)" in c for c in cuerpos), (
            f"«{selector}» sin borde visible"
        )


def test_el_foco_se_ve_sobre_la_placa_del_reproductor():
    """El anillo magenta del sitio da 1,32:1 sobre el azul de la placa."""
    assert "outline-color:#fff" in _regla(".player-consent:focus-visible")


def test_el_panel_de_busqueda_se_cierra_al_dejar_de_usarlo():
    regla = _regla(".search:not(:focus-within):not(:hover)#search-results")
    assert "display:none" in regla


# ── Fuente de titulares ───────────────────────────────────────────────────


def test_la_fuente_de_titulares_tiene_reserva_metrica_y_no_cae_a_la_serif():
    """La reserva era la serif de lectura, un 24 % más estrecha: al cargar la fuente de
    titulares (entonces Syne) el nombre del sitio pasaba de 231 a 292 px y todo lo de
    alrededor saltaba. Hoy es Bricolage Grotesque, con su reserva medida."""
    css = _css()
    pila = re.search(r"--display:([^;]+);", css).group(1)
    assert pila.startswith('"Bricolage Grotesque","Bricolage Fallback"')
    assert "var(--serif)" not in pila
    reservas = re.findall(r'@font-face\{[^}]*"Bricolage Fallback"[^}]*\}', css)
    assert len(reservas) >= 2, "la reserva necesita al menos una cara normal y una negrita"
    for cara in reservas:
        assert "size-adjust:" in cara and "local(" in cara


# ── Lienzo: los tres carriles ─────────────────────────────────────────────


def test_el_lienzo_declara_sus_tres_carriles():
    """El sitio tenía un solo contenedor de 820 px para todo, y el texto ocupaba el 54 %
    de una pantalla de 1440. Los carriles son líneas con nombre de una rejilla."""
    carriles = re.search(r"--carriles:([^;]+);", _css())
    assert carriles, "falta la plantilla de columnas del lienzo"
    for linea in (
        "full-start",
        "wide-start",
        "content-start",
        "content-end",
        "wide-end",
        "full-end",
    ):
        assert f"[{linea}]" in carriles.group(1), f"falta la línea «{linea}»"
    assert "grid-template-columns:var(--carriles)" in _regla(".lienzo")
    assert "grid-column:content" in _regla(".lienzo>*"), (
        "por defecto se cae en el carril de lectura"
    )
    assert "grid-column:wide" in _regla(".lienzo--ancho>*")
    assert "grid-column:full" in _regla(".lienzo>.sangre,.lienzo>.band")


def test_la_columna_de_lectura_no_se_ensancha():
    """Lo que crece es el lienzo, no la línea: lo legible son 45–75 letras, en cualquier
    monitor. El carril de lectura mide lo que medía el contenido de la caja de 820 px."""
    css = _css()
    assert re.search(r"--measure:\s*780px", css)
    ancho = re.search(r"--wide:\s*(\d+)px", css)
    assert ancho and 1200 <= int(ancho.group(1)) <= 1440
    assert "max-width:820px" in _regla(".wrap"), "la caja de siempre conserva su valor"


def test_ningun_ancho_usa_unidades_de_viewport():
    """100vw incluye la barra de desplazamiento: en un navegador de escritorio produce
    scroll horizontal. Los márgenes del lienzo salen de pistas 1fr."""
    assert "100vw" not in _css()


def test_las_bandas_no_pintan_su_fondo_con_una_sombra():
    """La banda vivía dentro de la caja estrecha y sacaba su fondo hacia fuera con una
    sombra de 100vmax recortada con clip-path. Ahora ocupa el carril a sangre."""
    banda = _regla(".band")
    assert "box-shadow" not in banda and "clip-path" not in banda
    assert "100vmax" not in _css()


def test_el_carril_ancho_de_cabecera_y_pie_coincide_con_el_del_lienzo():
    """Cabecera y pie viven fuera de <main>: su carril debe medir lo mismo y empezar en la
    misma vertical, o el nombre del sitio no quedaría alineado con el contenido."""
    regla = _regla(".wrap-wide")
    assert "max-width:calc(var(--wide)+2*var(--gutter))" in regla
    assert "padding-inline:var(--gutter)" in regla


# ── Filas, miniaturas y cubiertas (ticket 2.2) ────────────────────────────


def _bloque(cabecera):
    """Las reglas de dentro de un bloque @ (media, container), como texto sin espacios."""
    css = _css()
    inicio = css.index(cabecera)
    abre = css.index("{", inicio)
    nivel, i = 1, abre + 1
    while nivel:
        nivel += {"{": 1, "}": -1}.get(css[i], 0)
        i += 1
    return re.sub(r"\s+", "", css[abre + 1 : i - 1])


def test_la_fila_entera_es_el_enlace_de_su_titulo():
    """Solo era pulsable el texto del título. Una capa del propio enlace cubre la fila;
    los enlaces secundarios (sección, firmas) quedan por encima y siguen siendo propios."""
    assert "position:relative" in _regla(".fila")
    capa = _regla(".fila-tituloa::after")
    assert 'content:""' in capa and "position:absolute" in capa and "inset:0" in capa
    secundarios = _regla(".fila.kickera,.fila-piea")
    assert "position:relative" in secundarios and "z-index:1" in secundarios
    assert "padding-block:6px" in secundarios, "su zona de pulsado bajaría de 24 px"


def test_el_estado_de_la_fila_es_una_hoja_mas_clara_y_no_alcanza_a_las_que_no_enlazan():
    """Un hito no lleva a ninguna parte: su fila no debe prometerlo al pasar el puntero.
    El estado se pinta detrás del contenido (`isolation`) para no tapar el texto."""
    assert "isolation:isolate" in _regla(".fila")
    assert "z-index:-1" in _regla(".fila::before")
    estado = _regla(".fila:has(.fila-tituloa):hover::before,.fila:focus-within::before")
    assert "background-color:var(--paper-2)" in estado
    sueltos = [
        sel
        for sel, cuerpo in _reglas()
        if sel.startswith(".fila")
        and ":hover" in sel
        and "paper-2" in cuerpo
        and ":has(" not in sel
    ]
    assert not sueltos, f"filas que reaccionan aunque no enlacen: {sueltos}"


def test_las_filas_se_disponen_segun_el_ancho_de_su_lista():
    """La misma parcial vive en el carril ancho, en el de lectura y en un teléfono: manda
    el ancho de la lista, no el de la ventana."""
    assert "container:filas/inline-size" in _regla(".filas")
    tres_columnas = _bloque("@container filas (min-width:700px)")
    assert 'grid-template-areas:"fechacuerpopie"' in tres_columnas
    apilada = _regla(".fila")
    assert 'grid-template-areas:"cuerpocuerpo""piefecha"' in apilada, (
        "sin sitio, el título va arriba y los datos debajo"
    )


def test_en_el_carril_ancho_el_poema_ocupa_una_sola_linea():
    """Con el primer verso bajo el título cabían siete poemas por pantalla; en su propia
    columna caben diez. La última columna es fija: si dependiera del largo de cada firma,
    los versos empezarían en una vertical distinta en cada fila."""
    ancho = _bloque("@container filas (min-width:1000px)")
    assert ".fila--poema.fila-cuerpo{display:grid;" in ancho
    assert re.search(r"\.fila--poema\{grid-template-columns:[^;}]*15rem\}", ancho), (
        "la columna de la firma debe tener ancho fijo"
    )
    verso = re.search(r"\.fila--poema\.fila-verso\{([^}]*)\}", ancho).group(1)
    assert "white-space:nowrap" in verso and "text-overflow:ellipsis" in verso


def test_el_filete_y_la_hoja_clara_son_tokens():
    css = _css()
    assert re.search(r"--paper-2:\s*#[0-9a-f]{6}", css)
    assert re.search(r"--line:\s*#[0-9a-f]{6}", css), (
        "falta el valor para quien no conoce color-mix()"
    )
    mejora = _bloque("@supports (color:color-mix(")
    assert ":root{--line:color-mix(insrgb,var(--ink)22%,transparent)}" in mejora
    assert "border-top:1pxsolidvar(--line)" in _regla(".fila")


def test_la_cubierta_se_ensena_como_un_objeto():
    """Sin esquinas redondeadas y con sombra plana; al señalarla la sombra pasa al color
    de estado. Nada se mueve: el sitio solo anima color, fondo y borde."""
    cubierta = _regla(".pub-cardimg,.pub-cover-fallback")
    assert "box-shadow:8px8px0var(--line)" in cubierta
    assert "border-radius" not in cubierta
    assert "aspect-ratio:5/7" in cubierta
    senalada = [
        cuerpo
        for sel, cuerpo in _reglas()
        if ".pub-card a:hover img" in sel and ".pub-card a:focus-visible img" in sel
    ]
    assert senalada and "box-shadow:8px8px0var(--accent)" in senalada[0]
    assert "transform" not in senalada[0]


def test_un_catalogo_corto_no_se_arrincona():
    """Con tres títulos en una rejilla de cinco columnas, el 40 % de la pantalla quedaba
    vacío a la derecha. Es una mejora: sin :has() queda la rejilla general."""
    desde_900 = _bloque("@media (min-width:900px){\n  .pub-grid")
    assert (
        ".pub-grid:not(:has(>:nth-child(5))){grid-template-columns:repeat(4,minmax(0,1fr))}"
        in desde_900
    )
    assert (
        ".lienzo>.pub-grid:not(:has(>:nth-child(4))){grid-template-columns:repeat(3,minmax(0,1fr))}"
        in desde_900
    )
    assert "minmax(240px,1fr)" in _bloque("@media (min-width:720px){\n  .pub-grid")


def test_la_miniatura_de_registro_es_16_9_y_lleva_marca_de_reproduccion():
    miniatura = _regla(".rec-miniatura")
    assert "aspect-ratio:16/9" in miniatura and "background:var(--caratula)" in miniatura
    # El cartel va en posición absoluta: la marca necesita z-index o queda debajo.
    for capa in (".rec-miniatura::before", ".rec-miniatura::after"):
        assert "z-index:1" in _regla(capa), f"«{capa}» quedaría tapada por el cartel"
    assert "inset:0" in _regla(".recording-cardh2a::after"), "la tarjeta entera es el enlace"


def test_rejillas_que_reparten_el_ancho_entre_lo_que_haya():
    """`auto-fill` deja columnas vacías a la derecha cuando hay pocos elementos; con
    `auto-fit` los que hay se reparten la fila. El tope evita que uno solo se estire."""
    for lista, tarjeta in (
        (".recording-list", ".recording-card"),
        (".album-grid", ".album-card"),
    ):
        assert "repeat(auto-fit," in _regla(lista), f"«{lista}» vuelve a dejar columnas vacías"
        assert "max-width:" in _regla(tarjeta), f"«{tarjeta}» se estiraría de lado a lado"
    assert "repeat(auto-fit," in _regla(".event-list")


def test_la_hoja_de_contactos_fija_la_proporcion_en_la_hoja_no_en_cada_foto():
    hoja = _regla(".hoja")
    assert "grid-template-columns:2fr1fr" in hoja and "aspect-ratio:9/4" in hoja
    fotos = _regla(".hojaimg")
    assert "height:100%" in fotos and "object-fit:cover" in fotos
    assert "aspect-ratio" not in fotos


# ── Serif de lectura y monoespaciada (ticket 2.3) ─────────────────────────


def test_la_serif_de_lectura_es_propia_y_tiene_reserva_metrica():
    """La pila de sistema daba Palatino en un Mac, Times en Linux y Georgia en Windows: el
    sitio tenía tres voces. Ahora la serif viaja con el sitio, y mientras llega la ocupa una
    reserva escalada para que el texto no salte al cambiar."""
    css = _css()
    pila = re.search(r"--serif:([^;]+);", css).group(1)
    assert pila.startswith('"RdV Serif","RdV Serif Fallback"'), pila
    propias = re.findall(r'@font-face\{[^}]*font-family:"RdV Serif";[^}]*\}', css)
    estilos = sorted(re.search(r"font-style:(\w+)", cara).group(1) for cara in propias)
    assert estilos == ["italic", "normal"], f"faltan la redonda o la cursiva: {estilos}"
    for cara in propias:
        assert "font-display:swap" in cara and re.search(
            r'url\("\.\./fonts/rdv-serif[\w-]*\.woff2"\)', cara
        )
    reservas = re.findall(r'@font-face\{[^}]*"RdV Serif Fallback"[^}]*\}', css)
    assert len(reservas) >= 3, "la reserva necesita redonda, negrita y cursiva"
    for cara in reservas:
        assert (
            "size-adjust:" in cara
            and 'local("Liberation Serif' in cara
            and "ascent-override:" in cara
        )


def test_ninguna_familia_lleva_el_nombre_reservado_de_la_fuente():
    """Source Serif 4 tiene «Source» como nombre reservado (OFL, cláusula 3): una versión
    modificada —y el subconjunto lo es— no puede llamarse así."""
    familias = re.findall(r'font-family:\s*"([^"]+)"', _css())
    assert familias, "no se encontró ninguna familia declarada"
    assert not [f for f in familias if "source" in f.lower()], familias


# Reglas que pueden pintar en monoespaciada, cada una por su papel. Decisión D3: la mono
# queda para rótulos y datos; lo demás se lee en la serif o en la de titulares.
MONO_PERMITIDA = {
    ".rotulo,.kicker,.foot-grouph2,.reviewedh2,.event-month,.tag,"
    ".cinta-piea,.nav-disclosuresummary,.member-role,.foot-group-titulo": (
        "rótulo, también el cargo de cada integrante y los grupos del menú del teléfono"
    ),
    ".meta,.muted": "dato: firma, fecha, lugar",
    ".stats-strip": "etiquetas de las cifras",
    ".pagination-pagesa,.pagination-pagesspan": "números de página",
    ".lightboxfigcaption": "pie de foto",
    ".article.bodypre": "texto preformateado del autor: una partitura, una tabla hecha con espacios",
    ".article.bodycode": "código o un nombre de archivo dentro de un texto",
    ".htmx-indicator": "indicador de carga",
}


def test_la_monoespaciada_queda_en_rotulos_y_datos():
    """La navegación, el pie, los botones y las cifras iban en monoespaciada: la voz del
    sitio era la de un panel de control. Una regla nueva que la use tiene que justificarse
    aquí."""
    con_mono = {
        re.sub(r"\s+", "", sel) for sel, cuerpo in _reglas() if "font-family:var(--mono)" in cuerpo
    }
    sobrantes = con_mono - set(MONO_PERMITIDA)
    assert not sobrantes, f"monoespaciada fuera de rótulos y datos: {sorted(sobrantes)}"
    assert "font-family" not in _regla(".nava"), "la navegación toma la familia de los titulares"
    titulares = next(sel for sel, cuerpo in _reglas() if "font-family:var(--display)" in cuerpo)
    assert ".nav a" in titulares
    assert "font-family" not in _regla(".site-foot"), "el pie hereda la serif del cuerpo"


# ── Sala de lectura, fichas y pie (ticket 2.4) ────────────────────────────


def test_la_sala_de_lectura_pone_la_ancla_al_lado_solo_si_cabe():
    """Ancla y texto lado a lado desde 840 px de ventana: por debajo no caben y la ancla
    va encima. El reparto es 4:7; la línea sigue limitada por --medida."""
    assert "grid-template-columns:minmax(0,1fr)" in _regla(".lectura-sala")
    dos = _bloque("@media (min-width:840px){\n  .lectura-sala")
    assert ".lectura-sala{grid-template-columns:minmax(220px,4fr)minmax(0,7fr)" in dos
    fija = _bloque("@media (min-width:840px) and (min-height:700px)")
    assert ".lectura-ancla{position:sticky;" in fija, "la ancla solo acompaña si hay alto para ella"
    assert "position:sticky" not in _regla(".lectura-ancla>:first-child")


def test_un_bloque_preformateado_no_empuja_la_pagina():
    """Con sus líneas enteras, la partitura de un ensayo de prueba empujaba la página hacia
    los lados a cualquier ancho: el bloque se desplaza dentro de su caja."""
    bloque = _regla(".article.bodypre")
    assert "max-width:100%" in bloque and "overflow-x:auto" in bloque


def test_la_columna_ancla_que_no_cabe_se_desplaza_por_dentro():
    """Una columna ancla más alta que la pantalla (un título de doscientas letras, cuatro
    firmas, ocho etiquetas) dejaba su final fuera de la vista durante toda la lectura."""
    fija = _bloque("@media (min-width:840px) and (min-height:700px)")
    assert "max-height:calc(100dvh-var(--alto-cabecera)-2*var(--s3));overflow-y:auto" in fija


def test_un_titulo_larguisimo_baja_un_paso_y_se_divide_con_guion():
    """Unas diez letras caben por línea en la columna ancla: una palabra más larga se partía
    por la mitad y sin guion. Donde el navegador sabe dividir en español, divide."""
    assert "hyphens:auto" in _regla(".lectura-anclah1")
    assert "font-size:var(--t5)" in _regla(".poem.lectura-anclah1.titulo-largo")
    assert "font-size:var(--t4)" in _regla(".article.lectura-anclah1.titulo-largo")


def test_un_verso_largo_continua_con_sangria_francesa():
    """Sin sangría francesa, la continuación de un verso que no cabe se lee como un verso
    nuevo. El salto de estrofa mide una línea: el que dejó el autor."""
    verso = _regla(".verso")
    for declaracion in (
        "display:block",
        "white-space:pre-wrap",
        "padding-left:1.5em",
        "text-indent:-1.5em",
    ):
        assert declaracion in verso, f"al verso le falta «{declaracion}»"
    assert "margin-top:calc(var(--lh-verso)*1em)" in _regla(".estrofa+.estrofa")


def test_cada_salida_del_pie_se_pulsa_entera():
    assert "position:relative" in _regla(".pie-entidadli")
    assert 'content:""' in _regla(".pie-entidada::after") and "inset:0" in _regla(
        ".pie-entidada::after"
    )


def test_los_retratos_nuevos_no_son_circulos():
    """El retrato es 4:5, como el del colectivo; el círculo es el avatar de una app de
    mensajería (ticket 3.6). En los listados era un círculo de 72 px."""
    for selector in (
        ".firma-retrato",
        ".ficha-retrato",
        ".ficha-monograma",
        ".retrato",
        ".monograma",
    ):
        assert "border-radius" not in _regla(selector), f"«{selector}» redondea el retrato"
    for selector in (".ficha-retrato", ".retrato"):
        assert "aspect-ratio:4/5" in _regla(selector), f"«{selector}» no es 4:5"
    assert "border-radius:50%" not in _css(), "queda un círculo en la hoja"


# ── Superficies, tinta y amarillo (tickets 3.1 y 3.2) ─────────────────────


def _pantalla():
    """Las reglas de pantalla: sin la hoja de impresión, que pinta todo en blanco a propósito."""
    css = _css()
    inicio = css.index("@media print")
    abre = css.index("{", inicio)
    nivel, i = 1, abre + 1
    while nivel:
        nivel += {"{": 1, "}": -1}.get(css[i], 0)
        i += 1
    return [
        (re.sub(r"\s+", " ", selector.strip()), re.sub(r"\s+", "", cuerpo))
        for selector, cuerpo in re.findall(r"([^{}]+)\{([^{}]*)\}", css[:inicio] + css[i:])
    ]


# Lo único que puede ir en blanco: los campos de formulario, lo que flota sobre la página
# y los objetos (retratos, cubiertas, logotipos), más el botón y la marca de reproducción
# que se apoyan en la placa azul del reproductor.
BLANCO_PERMITIDO = {
    ".search input",
    ".search-page input",
    ".newsletter input[type=email]",
    ".form input, .form textarea, .form select",
    "#search-results:not(:empty)",
    ".pub-card img, .pub-cover-fallback",
    ".embed-play",
    ".embed-play:hover::after",
    ".rec-miniatura::before",
    ".recording-card:hover .rec-miniatura::after, .recording-card:focus-within .rec-miniatura::after",
}


def test_el_blanco_es_para_campos_y_objetos():
    """Las bandas y cinco avisos eran cajas blancas: el mismo blanco que los campos y las
    cubiertas, así que la página no se distinguía de las cosas que lleva encima (D6)."""
    blancas = {
        selector
        for selector, cuerpo in _pantalla()
        if re.search(r"background(-color)?:(var\(--surface\)|#fff\b|#ffffff\b|white\b)", cuerpo)
    }
    assert not blancas - BLANCO_PERMITIDO, f"superficies blancas: {blancas - BLANCO_PERMITIDO}"


def test_los_avisos_son_hoja_clara_sin_borde():
    """La fecha de la agenda, la próxima actividad, el contacto del dossier, la obra reseñada
    y los mensajes eran cajas blancas con borde de 1 px. Pasan a la hoja clara; los que
    llevan filete a la izquierda lo conservan, porque marca, no encierra."""
    for selector in (".event-date", ".next-event", ".dossier-contact", ".reviewed", ".flash"):
        cuerpo = _regla(selector)
        assert "background:var(--paper-2)" in cuerpo, f"«{selector}» no está en la hoja clara"
        assert not re.search(r"(?<![-\w])border:", cuerpo), f"«{selector}» sigue encerrado"
        assert "border-radius" not in cuerpo, f"«{selector}» sigue siendo una caja redondeada"


def test_la_banda_es_la_hoja_clara_y_la_fila_senalada_sobre_ella_pasa_al_papel():
    assert "background:var(--paper-2)" in _regla(".band")
    # La hoja clara es también la fila señalada: sobre una banda, el estado sería invisible.
    estado = _regla(".band.fila:has(.fila-tituloa):hover::before,.band.fila:focus-within::before")
    assert "background-color:var(--paper)" in estado


# Lo único que puede pintar un fondo de tinta: los botones y sus estados, el filete de
# 3 px que firma el territorio de prensa (una línea, no una superficie) y el pie.
TINTA_PERMITIDA = {
    ".btn:hover",
    ".index-head[data-territorio] h1::after, .seccion-cabeza[data-territorio] h2::after",
    ".btn--primary, .form button",
    ".pagination-pages a:hover",
    ".sello-convocatoria:hover",
    ".site-foot",
}


def test_la_tinta_como_superficie_es_solo_del_pie():
    """El registro destacado fue una banda de tinta de borde a borde. El dueño del sitio la
    descartó porque rompía la portada: la tinta como superficie queda para el pie."""
    con_tinta = {
        selector
        for selector, cuerpo in _pantalla()
        if re.search(r"background(-color)?:var\(--ink\)", cuerpo)
    }
    assert not con_tinta - TINTA_PERMITIDA, f"fondos de tinta: {con_tinta - TINTA_PERMITIDA}"
    plantillas = Path(__file__).resolve().parent.parent / "templates"
    con_banda = [
        p.name for p in plantillas.rglob("*.html") if "band--tinta" in p.read_text("utf-8")
    ]
    assert not con_banda, f"plantillas con banda de tinta: {con_banda}"


def test_la_placa_del_reproductor_fija_el_blanco_de_sus_datos():
    """El gris de `.meta` no se lee sobre el azul de la placa (2,12:1 con el de la tinta).
    Sin JavaScript la placa enseña un enlace al proveedor, que también es un dato."""
    assert "color:#fff" in _regla(".player-consent.meta,.player-consent.metaa")


def test_el_pie_es_de_tinta():
    pie = _regla(".site-foot")
    assert "background:var(--ink)" in pie and "color:var(--muted-on-ink)" in pie
    assert "color:var(--paper)" in _regla(".site-foota")
    assert "outline-color:var(--paper)" in _regla(".site-foot:focus-visible")
    boton = _regla(".site-foot.btn")
    assert "border-color:var(--paper)" in boton and "color:var(--paper)" in boton
    # Sin filete: la tinta ya separa el pie de la página.
    assert "border-top" not in pie


def _impresion():
    """El cuerpo de la hoja de impresión, sin espacios."""
    css = _css()
    abre = css.index("{", css.index("@media print"))
    nivel, i = 1, abre + 1
    while nivel:
        nivel += {"{": 1, "}": -1}.get(css[i], 0)
        i += 1
    return re.sub(r"\s+", "", css[abre + 1 : i - 1])


def test_al_imprimir_las_fotos_a_una_tinta_no_salen_en_blanco():
    """El duotono aclara la foto en gris sobre un fondo azul (`screen`), y el navegador no
    imprime los fondos: sobre el blanco de la hoja, la foto aclarada salía en blanco. Lo
    medido: los doce retratos de /integrantes/ impresos eran doce cajas vacías."""
    impresion = _impresion()
    assert ".riso-duoimg{filter:none;mix-blend-mode:normal}" in impresion
    assert ".riso-duo::after{content:none}" in impresion


def test_el_amarillo_es_el_trazo_de_las_cifras_del_dossier_y_nunca_texto():
    """El amarillo del cartel da 1,03:1 sobre el papel: solo puede entrar como fondo. Fue un
    plano de lado a lado del carril, que el dueño del sitio encontró invasivo, y después un
    trazo de marcador bajo las cifras de la portada (D5). Las quitó de la portada
    (2026-10-14) y el trazo pasó a las cifras del dossier (ticket 5.1): es su único uso, la
    mitad baja del número y no un plano."""
    con_amarillo = [
        selector
        for selector, cuerpo in _pantalla()
        if "riso-amarillo" in cuerpo and selector != ":root"
    ]
    assert con_amarillo == [".dossier-cifras strong"], (
        f"el amarillo se salió del trazo: {con_amarillo}"
    )
    trazo = _regla(".dossier-cifrasstrong")
    assert "background:linear-gradient(totop,transparent.06em,var(--riso-amarillo).06em," in trazo
    assert "print-color-adjust:exact" in trazo, "el trazo tiene que salir también en papel"
    assert not re.search(r"(?<![-\w])color:var\(--riso-amarillo\)", _css())


def test_la_firma_de_territorio_es_un_filete_de_tres_pixeles():
    """La misma en las cabeceras de índice y en las secciones de la portada (ticket 4.3):
    un solo selector por color, para que no se separen."""
    firma = _regla(
        ".index-head[data-territorio]h1::after,.seccion-cabeza[data-territorio]h2::after"
    )
    assert "height:3px" in firma and "background-color:var(--ink)" in firma
    assert "background-color:var(--accent)" in _regla(
        '.index-head[data-territorio="obra"]h1::after,.seccion-cabeza[data-territorio="obra"]h2::after'
    )
    assert "background-color:var(--caratula)" in _regla(
        '.index-head[data-territorio="colectivo"]h1::after,'
        '.seccion-cabeza[data-territorio="colectivo"]h2::after'
    )


def test_el_sello_de_convocatoria_esta_quieto():
    """Un timbre girado, no un aviso que se mueve: nada que distraiga de leer."""
    sello = _regla(".sello-convocatoria")
    assert "transform:rotate(-3deg)" in sello
    assert "animation" not in sello and "riso-amarillo" not in sello


# ── Ajustes tras la revisión del paso 13 ──────────────────────────────────


def _todas(selector):
    """Todas las reglas con ese selector, también las de dentro de un @media, en orden."""
    return [cuerpo for sel, cuerpo in _reglas() if re.sub(r"\s+", "", sel) == selector]


def test_el_pie_queda_abajo_en_una_pagina_corta():
    """En una página corta el pie terminaba a media altura y dejaba papel debajo: con el
    pie en tinta, un hueco. La página mide al menos la ventana y el lienzo crece."""
    cuerpo = _regla("body")
    for declaracion in ("display:flex", "flex-direction:column", "min-height:100dvh"):
        assert declaracion in cuerpo, f"a `body` le falta «{declaracion}»"
    lienzo = _regla(".lienzo")
    assert "flex:10auto" in lienzo, "el lienzo no crece hasta el pie"
    assert "align-content:start" in lienzo, "el alto sobrante separaría las filas del lienzo"
    assert "width:100%" in _regla(".wrap-wide"), (
        "en una columna flexible, un hijo con margen automático se encoge a su contenido"
    )


def test_el_pie_usa_el_ancho_para_medir_menos_de_alto():
    """Medía 435 px a 951 de ancho. El orden es el del ticket 4.4 (la identidad, el mapa, el
    boletín y lo legal) sin volver a subir el alto: desde 900 px la identidad va al lado de
    los grupos y el boletín comparte línea con lo legal; desde 1100, todo en una fila. Entre
    720 y 899 la identidad va sola en su línea: al lado de los grupos, se salían."""
    rejillas = " ".join(_todas(".site-foot>.wrap-wide"))
    assert 'grid-template-areas:"identidad""mapa""news""legal"' in rejillas
    assert 'grid-template-areas:"identidadidentidad""mapamapa""newslegal"' in rejillas
    assert 'grid-template-areas:"identidadmapamapa""newsnewslegal"' in rejillas
    assert 'grid-template-areas:"identidadmapanews""identidadmapalegal"' in rejillas
    grupos = " ".join(_todas(".foot-groups"))
    assert "grid-template-columns:repeat(4,max-content)" in grupos, (
        "los cuatro grupos, a la medida de su contenido"
    )


def test_el_sello_del_pie_va_en_blanco_como_el_de_la_cabecera():
    """La regla de los enlaces del pie pinta los enlaces en el color del papel: el sello es
    un enlace y quedaba en ese azul claro sobre el magenta."""
    assert "color:#fff" in _regla(".site-foot.brand")


def test_la_tirada_se_desliza_con_iman_y_cambia_solo_de_tinta():
    """La tirada (D19): un carril nativo con imán y la barra a la vista, que funciona sin
    JavaScript. Al pasar un pliego al frente solo cambian colores (las tintas registradas con
    @property), y solo para quien no pidió menos movimiento. El magenta es un estado: lo
    lleva el pliego al frente, nunca uno en reposo."""
    carril = _regla(".tirada-carril")
    for declaracion in ("overflow-x:auto", "scroll-snap-type:xmandatory", "scrollbar-width:thin"):
        assert declaracion in carril
    for tinta in ("--tinta", "--sobre", "--trama", "--marca", "--sello"):
        assert f"@property {tinta}" in _css(), f"la tinta {tinta} no está registrada"
    movimiento = _bloque(
        "@media (prefers-reduced-motion:no-preference){\n  .tirada.con-js .pliego{"
    )
    transiciones = re.findall(r"transition:([^;}]+)", movimiento)
    propiedades = {
        t.split("var(")[0] for parte in transiciones for t in parte.split(",") if t.strip()
    }
    assert propiedades <= {
        "--tinta",
        "--trama",
        "--marca",
        "--sello",
        "--sobre",
        "border-color",
        "outline-color",
    }
    sobre = [sel for sel, cuerpo in _reglas() if "--sobre:var(--accent)" in cuerpo]
    assert sobre == [".tirada.con-js .pliego[aria-current]"]
    assert "font-size:var(--t7)" in _regla(".pliego-titulo")


def test_en_la_portada_el_poster_de_la_tirada_se_queda_a_una_tinta():
    """Decisión 3 del tablero de los registros: al señalar o enfocar un pliego, el póster no
    pasa al original a color (eso queda para la ficha)."""
    senalan = [sel for sel, cuerpo in _reglas() if ".riso-duo" in sel and "filter:none" in cuerpo]
    assert senalan and not any("pliego" in sel or "tirada" in sel for sel in senalan)


# ── Duotono y retratos (tickets 3.3 y 3.6) ────────────────────────────────


def test_el_duotono_es_una_tinta_sobre_el_papel():
    """La tinta va de fondo, la foto en gris se aclara encima y el papel se multiplica por
    arriba: cada gris cae entre la tinta y el papel. Una sola tinta en todo el sitio, el
    azul del cartel; sin `isolation` la mezcla alcanzaría lo que hay detrás de la foto."""
    duo = _regla(".riso-duo")
    assert "isolation:isolate" in duo and "background-color:var(--caratula)" in duo
    foto = _regla(".riso-duoimg")
    assert "filter:grayscale(1)" in foto and "mix-blend-mode:screen" in foto
    papel = _regla(".riso-duo::after")
    assert "mix-blend-mode:multiply" in papel and "background-color:var(--paper)" in papel
    assert "pointer-events:none" in papel, "la capa del papel no puede tapar el enlace"
    # La tinta es el fondo de las reglas del duotono que no son la capa del papel.
    tintas = {
        tinta
        for selector, cuerpo in _reglas()
        if "riso-duo" in selector and "::after" not in selector
        for tinta in re.findall(r"background-color:var\((--[\w-]+)\)", cuerpo)
    }
    assert tintas == {"--caratula"}, f"más de una tinta de duotono: {tintas}"


def test_al_senalar_o_enfocar_se_ve_el_original():
    """Hay que quitar a la vez el filtro y la mezcla: si solo se quita uno, el original sale
    teñido. Y la capa del papel se vuelve transparente. Una sola regla con `:is()` dice
    dónde se señala: un enlace, la cinta, las tarjetas, la placa, una fila."""
    lugares = (
        "a",
        ".cinta-caja",
        ".recording-card",
        ".event-card",
        ".player-consent",
        ".fila",
        ".next-event",
    )
    reglas = {re.sub(r"\s+", "", sel): cuerpo for sel, cuerpo in _reglas()}
    estado = ":is(:hover,:focus-within)"
    for capa, declaracion in ((".riso-duoimg", "filter:none"), (".riso-duo::after", "transparent")):
        selector = next(s for s in reglas if s.endswith(estado + capa))
        assert all(lugar in selector.split(")")[0] for lugar in lugares), selector
        assert declaracion in reglas[selector]
    original = next(c for s, c in reglas.items() if s.endswith(estado + ".riso-duoimg"))
    assert "mix-blend-mode:normal" in original


# El duotono va en las imágenes de los listados: tarjetas de integrante, cinta, hoja de
# contactos, pósters de los registros (índice y placa, D10), imágenes de los textos y afiches
# de la agenda, la trayectoria y la próxima actividad de la portada. Las cubiertas de las
# publicaciones, los logos y las fichas se ven tal cual.
CON_DUOTONO = {
    "_member_card.html",
    "_member_card_cinta.html",
    "gallery.html",
    "_player.html",
    "recording_index.html",
    "_article_card.html",
    "_event_card.html",
    "trayectoria.html",
    "home.html",
    # La placa y la hoja de contactos de la tirada de registros (D19).
    "_tirada.html",
}


def test_el_duotono_solo_va_en_los_listados():
    plantillas = Path(__file__).resolve().parent.parent / "templates"
    con_duo = {p.name for p in plantillas.rglob("*.html") if "riso-duo" in p.read_text("utf-8")}
    assert con_duo == CON_DUOTONO, f"duotono en: {sorted(con_duo)}"


def test_toda_la_tarjeta_de_integrante_es_el_enlace():
    """El rol y la reseña quedaban fuera del enlace: la capa del enlace cubre la tarjeta."""
    assert "position:relative" in _regla(".member-card")
    capa = _regla(".member-card>a::after")
    assert 'content:""' in capa and "inset:0" in capa


# ── Reproductor: póster o carátula (ticket 3.4, D10) ──────────────────────


def test_el_mando_de_la_placa_es_un_panel_solido_con_la_marca_del_indice():
    """El aviso tiene que leerse sobre cualquier póster: va en un panel del azul de la
    placa. El botón es la marca de reproducción del índice, cuadrada (sin círculos)."""
    assert "position:absolute" in _regla(".player-mando") and "bottom:0" in _regla(".player-mando")
    aviso = _regla(".embed-note")
    assert "background:var(--caratula)" in aviso and "color:#fff" in aviso
    boton = _regla(".embed-play")
    assert "width:64px" in boton and "border-radius:0" in boton
    assert "clip-path:polygon(" in _regla(".embed-play::after"), "el botón perdió su triángulo"
    # El foco va por dentro del botón blanco: fuera quedaría sobre el póster, a 1,2:1.
    foco = _regla(".player-consent.embed-play:focus-visible")
    assert "outline-offset:-" in foco and "var(--caratula-rotulo)" in foco


def test_la_placa_no_tiene_marco_ni_esquinas():
    placa = _regla(".player-frame")
    assert "border-radius" not in placa and "border:" not in placa
    assert "container:placa/inline-size" in placa, "el título de la carátula crece con la placa"


# ── Las imágenes del modelo en los listados (ticket 3.5) ──────────────────


def test_la_miniatura_de_una_fila_es_un_area_de_su_rejilla():
    """No un flotante: en una lista estrecha va junto al título, con la fecha debajo; con
    sitio, es la última columna. Se alinea arriba, no por la línea base del texto."""
    assert 'grid-template-areas:"cuerpomini""piefecha"' in _regla(".fila--con-miniatura")
    ancha = _bloque("@container filas (min-width:700px)")
    assert 'grid-template-areas:"fechacuerpopiemini"' in ancha
    miniatura = _regla(".fila-miniatura")
    assert "grid-area:mini" in miniatura and "align-self:start" in miniatura
    assert "aspect-ratio:3/4" in _regla(".fila-miniaturaimg")


def test_los_logos_se_imprimen_en_gris_y_toman_color_al_senalar():
    """Multiplicados con el papel, el fondo blanco de un logo desaparece; en gris hasta que
    se señalan, el mismo gesto que las fotos a una tinta."""
    logo = _regla(".partner-logo")
    for declaracion in (
        "width:160px",
        "height:80px",
        "object-fit:contain",
        "filter:grayscale(1)",
        "mix-blend-mode:multiply",
    ):
        assert declaracion in logo, f"al logo le falta «{declaracion}»"
    assert "filter:none" in _regla(
        ".partner-item:hover.partner-logo,.partner-item:focus-within.partner-logo"
    )


def test_un_aliado_sin_logo_no_se_oscurece_al_mezclarse_con_el_papel():
    """La caja sin logo es la hoja clara: multiplicada con el papel, quedaba más oscura que
    él. Va sin mezcla ni filtro, y con su nombre en la tipografía de titulares."""
    caja = _regla(".partner-logo--texto")
    for declaracion in ("mix-blend-mode:normal", "filter:none", "background:var(--paper-2)"):
        assert declaracion in caja, f"a la caja le falta «{declaracion}»"
    assert "font-family:var(--display)" in caja


# ── La ficha de un evento y sus fotos (ticket 5.2) ────────────────────────


def test_el_afiche_llega_a_420_px_si_al_texto_le_quedan_360():
    ficha = _bloque("@media (min-width:720px){\n  .ficha-cabecera{")
    assert (
        ".ficha-cabecera--afiche{grid-template-columns:minmax(200px,420px)minmax(360px,1fr)}"
        in ficha
    )
    assert "box-shadow:8px8px0var(--line)" in _regla(".ficha-afiche"), "el afiche no es un objeto"


def test_el_mosaico_no_deja_huecos_con_ninguna_cantidad_de_fotos():
    """Seis columnas: tercios por defecto; la primera a doble tamaño con tres fotos o con
    seis o más; a medias con dos o cuatro, y las dos primeras con cinco; a todo el ancho
    con una."""
    assert "grid-template-columns:repeat(6,minmax(0,1fr))" in _regla(
        ".photo-grid,.photo-grid-resto"
    )
    celda = _regla(".photo-grid>li,.photo-grid-resto>li")
    assert "grid-column:span2" in celda and "aspect-ratio:3/2" in celda
    assert "grid-column:1/-1" in _regla(".photo-grid>li:only-child")
    assert "grid-column:span3" in _regla(
        ".photo-grid:has(>:nth-child(2):last-child)>li,"
        ".photo-grid:has(>:nth-child(4):last-child)>li,"
        ".photo-grid:has(>:nth-child(5):last-child)>li:nth-child(-n+2)"
    )
    doble = _regla(
        ".photo-grid:has(>:nth-child(3):last-child)>li:first-child,"
        ".photo-grid:has(>:nth-child(6))>li:first-child"
    )
    assert "grid-column:span4" in doble and "grid-row:span2" in doble


def test_la_regla_de_las_miniaturas_no_alcanza_a_la_vista_ampliada():
    """`.photo-grid img` también recortaba a 8:5 la foto ampliada, que está dentro de la
    misma lista: no se veía entera. Las reglas del mosaico van por hijos directos."""
    selectores = [re.sub(r"\s+", "", sel) for sel, _ in _reglas()]
    assert ".photo-gridimg" not in selectores and ".photo-grida" not in selectores
    assert "object-fit:cover" in _regla(".photo-grid>li>aimg,.photo-grid-resto>li>aimg")


def test_la_vista_ampliada_cubre_toda_la_pantalla():
    """Una <figure> trae márgenes (40 px a los lados): la capa no llegaba a los bordes y la
    foto quedaba corrida."""
    capa = _regla(".lightbox")
    assert "position:fixed" in capa and "inset:0" in capa and "margin:0" in capa


def test_el_pie_de_la_vista_ampliada_se_lee():
    """Contador, pie y crédito a 13 px: a 12 era la letra más pequeña del sitio."""
    assert "font-size:var(--t-1)" in _regla(".lightboxfigcaption")


# ── La marca (ticket 3.7, con lo que eligió el dueño) ─────────────────────


def test_el_sello_de_la_cabecera_sigue_siendo_magenta_con_su_monograma():
    """El dueño se quedó con el sello magenta y le añadió el monograma RV dentro."""
    sello = _regla(".brand")
    assert "background:var(--accent)" in sello and "color:#fff" in sello
    assert "display:inline-flex" in sello, "el monograma y el nombre van en una fila"
    assert "fill:#fff" in _regla(".brand-mono-r")
    assert "fill:var(--celeste)" in _regla(".brand-mono-v")


# ── Cabecera de una fila (ticket 4.1) ─────────────────────────────────────


def test_la_cabecera_es_fija_y_lo_fijo_queda_debajo_de_ella():
    """La cabecera se queda arriba al bajar. Su alto es un token: la ancla de la lectura,
    el año de la trayectoria y el salto a un ancla lo usan para no quedar tapados."""
    cabecera = _regla(".masthead")
    assert "position:sticky" in cabecera and "top:0" in cabecera
    assert "--alto-cabecera" in _tokens()
    assert "scroll-padding-top:calc(var(--alto-cabecera)" in " ".join(_todas("html"))
    # Todo lo fijo, también lo que se añada mañana: no solo los que hay hoy.
    fijos = [(sel, cuerpo) for sel, cuerpo in _reglas() if "position:sticky" in cuerpo]
    assert {sel for sel, _ in fijos} >= {".masthead", ".lectura-ancla", ".year-mark"}
    for selector, cuerpo in fijos:
        if selector == ".portada-arte":
            # La obra de la portada (D18) va bajo la franja a propósito: arriba de la portada
            # la franja está vacía. Lo que no debe quedar tapado es la hoja, que no es fija.
            assert "top:0" in cuerpo
        elif selector != ".masthead":
            assert "top:calc(var(--alto-cabecera)" in cuerpo, (
                f"«{selector}» quedaría tapado por la cabecera fija"
            )


def test_los_enlaces_de_la_barra_se_pulsan_en_44_px():
    """La auditoría pide 44 px de alto en los enlaces de la barra (ticket 6.1). Medían 23:
    el alto de su texto (15 px por 1,55). Con 11 px arriba y abajo, 45, sin mover nada: la
    fila mide 64 y la marca de la página actual es un subrayado, que va con el texto."""
    for selector in (".nava", ".subnava"):
        assert "padding-block:11px" in _regla(selector), f"«{selector}» vuelve a medir 23 px"


def test_el_subrayado_de_la_pagina_actual_no_alcanza_al_separador():
    actual = _regla(".nava[aria-current],.subnava[aria-current]")
    assert "text-decoration-thickness:2px" in actual
    assert "display:inline-block" in _regla(".nava:not(:last-child)::after"), (
        "sin inline-block, el punto separador hereda el subrayado de la página actual"
    )


def test_en_el_telefono_el_boton_del_dossier_se_guarda_en_el_menu():
    """El botón le gana a la regla general de `.btn` solo con `.masthead` delante."""
    movil = _bloque("@media (max-width:899px){\n  .brand{padding:3px")
    assert ".masthead.masthead-cta{display:none}" in movil


def test_la_cabecera_del_telefono_llega_hasta_donde_cabe_la_fila_entera():
    """La fila entera (sello, cinco enlaces, lupa y «Dossier») pide unos 880 px de ventana:
    con el corte en 720, a 768 y a 820 el botón quedaba fuera de la pantalla. Los dos cortes
    se tocan, para que ningún ancho se quede con las dos cabeceras o sin ninguna. En el
    teléfono los huecos son de 8 px: con los de 24, a 320 px «Menú» no cabía."""
    css = _css()
    telefono = re.search(r"@media \(max-width:(\d+)px\)\{\n  \.brand\{padding:3px", css)
    escritorio = re.search(r"@media \(min-width:(\d+)px\)\{\n  :root\{--alto-cabecera:64px\}", css)
    assert int(telefono[1]) + 1 == int(escritorio[1]), "un ancho con dos cabeceras, o sin ninguna"
    assert int(escritorio[1]) >= 880, "la fila entera no cabe por debajo de unos 880 px"
    assert ".masthead-fila{column-gap:8px}" in _bloque(telefono[0])


def test_en_el_telefono_menu_va_en_tinta_como_la_lupa():
    """La receta de los rótulos, más abajo en la hoja, lo dejaba en gris: con `.masthead`
    delante gana la regla de la cabecera, y el magenta queda para el paso del ratón y para
    cuando está abierto, como en la lupa."""
    movil = _bloque("@media (max-width:899px){\n  .brand{padding:3px")
    menu = re.search(r"\.masthead\.nav-disclosuresummary\{([^}]*)\}", movil)
    assert menu and "color:var(--ink)" in menu[1], "«Menú» se queda en el gris de los rótulos"
    assert ".masthead.nav-disclosure[open]summary" in movil


def test_el_campo_del_buscador_ocupa_su_panel():
    """El «…» de htmx, invisible mientras no se busca, le quitaba al campo 35 px: va en el
    margen del panel. El panel acaba donde el botón «Dossier», no en el borde de la ventana."""
    assert "flex:1" in _regla(".searchinput")
    assert "position:absolute" in _regla(".busqueda.htmx-indicator")
    assert "right:var(--gutter)" in _regla(".busqueda.search")


# ── Titular de la portada (ticket 4.2, la opción A del dueño) ─────────────


def test_la_obra_de_la_portada_llega_a_lo_alto_y_deja_asomar_la_hoja():
    """La portada como obra (D18): la obra sube bajo la franja vacía de la cabecera y se
    detiene antes del borde, donde asoma la hoja. Alto mínimo y no fijo: con el zoom al
    400 % nada se recorta. svh, con vh para quien no lo conoce."""
    obra = _regla(".portada-arte")
    assert "margin-top:calc(-1*var(--alto-cabecera))" in obra
    assert (
        "min-height:max(460px,100vh-var(--asomo));min-height:max(460px,100svh-var(--asomo))" in obra
    )
    assert not re.search(r"(?<![-\w])height:", obra), "un alto fijo recortaría la obra"
    assert "overflow" not in obra
    assert "background:var(--paper)" in obra, "sin la imagen, el papel"
    assert "--asomo:112px" in _tokens_de(":root")
    assert ":root{--asomo:96px}" in _bloque("@media (max-width:719px){\n  :root{--asomo")
    assert "object-fit:cover" in _regla(".portada-imagenimg")
    # Con un aviso entre la cabecera y <main>, la obra empieza debajo y no lo tapa.
    assert "margin-top:0" in _regla(".mensajes+.lienzo>.portada-arte")


def _tokens_de(selector):
    return " ".join(_todas(selector))


def test_el_logo_de_la_portada_va_en_tinta_sobreimpreso():
    """El logo cruza la obra al pie, de lado a lado, multiplicado como una plancha de riso. En
    el teléfono pasa a la versión en dos líneas."""
    mancheta = _regla(".portada-mancheta")
    for declaracion in ("left:var(--gutter)", "right:var(--gutter)", "mix-blend-mode:multiply"):
        assert declaracion in mancheta
    assert "color:var(--ink)" in _regla(".portada-logo")
    assert "width:100%" in _regla(".portada-logosvg")
    telefono = _bloque("@media (max-width:719px){\n  .portada-logo")
    assert ".portada-logo.logo-horizontal{display:none}" in telefono
    assert ".portada-logo.logo-apilado{display:block}" in telefono
    forzados = _bloque("@media (forced-colors: active){\n  .portada-mancheta")
    assert "background:Canvas" in forzados


def test_el_telon_solo_con_movimiento_y_si_la_obra_cabe():
    """La obra se queda quieta y la hoja sube encima, solo para quien no pide menos
    movimiento y en una ventana donde la obra cabe entera: más alta que la ventana, quieta
    arriba, su pie no se vería nunca."""
    telon = _bloque("@media (prefers-reduced-motion:no-preference) and (min-height:460px){")
    assert ".portada-arte{position:sticky;top:0}" in telon
    assert ".portada-arte:focus-within{z-index:2}" in telon
    fuera = [sel for sel, cuerpo in _reglas() if sel == ".portada-arte" and "sticky" in cuerpo]
    assert len(fuera) == 1, "la obra solo es fija dentro de su bloque"
    hoja = _regla(".portada-telon")
    for declaracion in (
        "position:relative",
        "z-index:1",
        "background:var(--paper)",
        "grid-template-columns:var(--carriles)",
    ):
        assert declaracion in hoja


def test_el_boton_del_titular_se_oculta_donde_aparece_el_de_la_cabecera():
    """Un solo botón principal por pantalla: el dossier del titular se oculta en el mismo
    ancho en el que la cabecera enseña el suyo."""
    cabecera = re.search(r"@media \(min-width:(\d+)px\)\{\n  :root\{--alto-cabecera:64px\}", _css())
    titular = _bloque(f"@media (min-width:{cabecera[1]}px){{\n  .hero-dossier")
    assert ".hero-dossier{display:none}" in titular


def test_el_sello_de_la_convocatoria_ya_no_flota():
    """Flotaba a la derecha del lema, donde fue después el objeto: no debía taparlo."""
    flotantes = [
        sel for sel, cuerpo in _reglas() if "sello-convocatoria" in sel and "float:" in cuerpo
    ]
    assert not flotantes, f"el sello vuelve a flotar: {flotantes}"


# ── La portada completa (ticket 4.3) ──────────────────────────────────────


def test_la_obra_va_a_dos_columnas_solo_con_poemas_y_textos():
    """Con una sola de las dos listas va a todo el ancho: en media columna quedaba un hueco."""
    obra = _bloque("@media (min-width:900px){\n  .home-obra-columnas")
    assert ".home-obra-columnas:has(>:nth-child(2)){display:grid" in obra


def test_las_puertas_del_cierre_van_en_una_fila_sin_huecos():
    """Una columna por puerta desde 900 px, tres o cuatro según haya correo: en la rejilla de
    tres, «Escríbenos» quedaba sola en la segunda fila. En el teléfono, de dos en dos."""
    assert "grid-auto-flow:column" in _bloque(
        "@media (min-width:900px){\n  .home-cierre .pie-entidad ul"
    )
    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in _regla(".home-cierre.pie-entidadul")


def test_las_cubiertas_de_la_portada_no_pasan_de_240_px():
    """Una columna por cubierta: con dos, a todo el ancho, cada una medía 470 px."""
    publicaciones = _bloque("@media (min-width:900px){\n  .home-publicaciones .band-in")
    assert "grid-auto-columns:minmax(0,240px)" in publicaciones
