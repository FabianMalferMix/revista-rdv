from apps.media.tasks import process_image


def process_portada_images(sender, instance, **kwargs):
    """Las copias de la obra de la portada (AVIF y WebP) se piden al servicio de imágenes al
    elegirla, no al pedir la portada, y se hacen fuera de la petición, con el perfil ya
    guardado. Las que ya existen no se rehacen."""
    for image_id in {instance.hero_image_id, instance.hero_image_phone_id} - {None}:
        process_image.delay_on_commit(image_id)
