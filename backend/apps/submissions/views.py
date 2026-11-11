import logging

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_safe

from config.ratelimit import rate_limited

from .forms import SubmissionForm
from .models import Call, Submission

logger = logging.getLogger(__name__)

TOO_MANY_SUBMISSIONS = "Has enviado demasiadas propuestas. Inténtalo más tarde."


def _open_call():
    return Call.objects.open_now().first()


def _submit_limited(request, aviso):
    """Pasado el límite, el formulario con el aviso y con lo escrito, para no perder el texto.
    Vuelve como `initial`, sin marcar el formulario como enviado, para no enseñar errores de
    validación que no son. El adjunto no se puede repoblar."""
    messages.error(request, aviso)
    return render(
        request,
        "submissions/submit.html",
        {"form": SubmissionForm(initial=request.POST.dict()), "call": _open_call()},
    )


# El GET enseña el formulario y no cuenta para el límite.
@require_http_methods(["GET", "HEAD", "POST"])
@rate_limited("10/h", notice=TOO_MANY_SUBMISSIONS, limited=_submit_limited, method="POST")
def submit(request):
    if request.method == "POST":
        form = SubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            if form.is_spam:
                # Bot: fingimos éxito sin guardar para no darle pistas.
                return redirect("submissions:submit_thanks")
            submission = form.save(commit=False)
            submission.call = _open_call()
            submission.save()
            return redirect("submissions:submit_thanks")
    else:
        form = SubmissionForm()
    return render(request, "submissions/submit.html", {"form": form, "call": _open_call()})


@require_safe
def submit_thanks(request):
    return render(request, "submissions/submit_thanks.html", {})


@require_safe
@staff_member_required
def submission_file(request, pk):
    """Descarga del adjunto, para quien puede ver los envíos en el panel. No son públicos: sin el
    permiso responde 404, sin decir si el envío existe. Si el archivo ya no está en el disco,
    también 404, y el log lo dice con el número del envío."""
    if not request.user.has_perm("submissions.view_submission"):
        raise Http404
    submission = get_object_or_404(Submission, pk=pk)
    if not submission.file:
        raise Http404
    try:
        handle = submission.file.open("rb")
    except FileNotFoundError:
        # Sin la ruta en el mensaje: el nombre del archivo lo puso quien envió la propuesta.
        logger.warning("El adjunto del envío %s no está en el disco", submission.pk)
        raise Http404 from None
    filename = submission.file.name.rsplit("/", 1)[-1]
    return FileResponse(handle, as_attachment=True, filename=filename)
