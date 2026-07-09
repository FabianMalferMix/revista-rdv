from django.contrib.admin.views.decorators import staff_member_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.content.permissions import is_editor

from .forms import SubmissionForm
from .models import Call, Submission


def _open_call():
    now = timezone.now()
    return Call.objects.filter(opens_at__lte=now, closes_at__gte=now).first()


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
    return render(
        request, "submissions/submit.html", {"form": form, "call": _open_call()}
    )


def submit_thanks(request):
    return render(request, "submissions/submit_thanks.html", {})


@staff_member_required
def submission_file(request, pk):
    """Descarga del adjunto, solo para editores. Los envíos no son públicos."""
    if not is_editor(request.user):
        raise Http404
    submission = get_object_or_404(Submission, pk=pk)
    if not submission.file:
        raise Http404
    filename = submission.file.name.rsplit("/", 1)[-1]
    return FileResponse(
        submission.file.open("rb"), as_attachment=True, filename=filename
    )
