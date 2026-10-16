import hashlib

from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import GoogleAccountLinkChallenge, GoogleIdentity, GoogleLoginAttempt


@transaction.atomic
def permanently_delete_account(*, user_id, password, google_authenticated=False, session_key=None):
    User = get_user_model()
    user = User.objects.select_for_update().get(pk=user_id)
    if user.has_usable_password():
        # Periksa password lagi setelah lock agar perubahan serentak tidak melewati verifikasi.
        if not user.check_password(password):
            raise ValidationError("Password tidak benar. Akun belum dihapus.")
    elif not (google_authenticated and GoogleIdentity.objects.filter(user=user).exists()):
        raise ValidationError("Verifikasi ulang akun Google terlebih dahulu sebelum menghapus akun.")

    session_keys = set()
    session_digests = set(
        GoogleAccountLinkChallenge.objects.filter(user=user).values_list("session_digest", flat=True)
    )
    if session_key:
        session_keys.add(session_key)
        session_digests.add(hashlib.sha256(session_key.encode("utf-8")).hexdigest())

    # Session Django tidak memiliki FK pengguna; decode diperlukan untuk menghapus semua sesi.
    for session in Session.objects.all().iterator(chunk_size=100):
        digest = hashlib.sha256(session.session_key.encode("utf-8")).hexdigest()
        if str(session.get_decoded().get(SESSION_KEY, "")) == str(user.pk) or digest in session_digests:
            session_keys.add(session.session_key)
            session_digests.add(digest)
    if session_keys:
        Session.objects.filter(session_key__in=session_keys).delete()
    if session_digests:
        GoogleLoginAttempt.objects.filter(session_digest__in=session_digests).delete()


    user.delete()
