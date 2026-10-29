from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django_ratelimit.decorators import ratelimit

from .forms import SubmissionForm
from .models import Call, Submission


def _open_call():
    return Call.objects.open_now().first()


@ratelimit(key="ip", rate="10/h", method="POST", block=False)
def submit(request):
    if request.method == "POST":
        if getattr(request, "limited", False):  # rate-limit por IP superado
            messages.error(request, "Has enviado demasiadas propuestas. Inténtalo más tarde.")
            # Rehidratamos con lo escrito (como `initial`, sin marcar el form como
            # enviado para no mostrar errores de validación espurios) para no perder
            # el texto del usuario — hallazgo #28. El adjunto no se puede repoblar.
            return render(
                request,
                "submissions/submit.html",
                {"form": SubmissionForm(initial=request.POST.dict()), "call": _open_call()},
            )
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


def submit_thanks(request):
    return render(request, "submissions/submit_thanks.html", {})


@staff_member_required
def submission_file(request, pk):
    """Descarga del adjunto, para quien puede ver los envíos en el panel. No son públicos: sin el
    permiso responde 404, sin decir si el envío existe."""
    if not request.user.has_perm("submissions.view_submission"):
        raise Http404
    submission = get_object_or_404(Submission, pk=pk)
    if not submission.file:
        raise Http404
    filename = submission.file.name.rsplit("/", 1)[-1]
    return FileResponse(submission.file.open("rb"), as_attachment=True, filename=filename)
