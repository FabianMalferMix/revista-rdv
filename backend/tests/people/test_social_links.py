"""Una persona tiene un solo enlace por red social."""

import pytest
from django.db import IntegrityError

from apps.people.models import Contributor, SocialLink

pytestmark = pytest.mark.django_db


def test_sociallink_unique_per_platform():
    contributor = Contributor.objects.create(slug="c1", display_name="Colaboradora")
    SocialLink.objects.create(contributor=contributor, platform="twitter", url="https://x/a")
    with pytest.raises(IntegrityError):
        SocialLink.objects.create(contributor=contributor, platform="twitter", url="https://x/b")
