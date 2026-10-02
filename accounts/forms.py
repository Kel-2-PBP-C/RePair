from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, UsernameField
from django.db import transaction
from django.utils import timezone

from .models import Profile

User = get_user_model()


class ProfileFieldsMixin:
    def clean_birth_date(self):
        birth_date = self.cleaned_data.get("birth_date")
        if birth_date and birth_date > timezone.localdate():
            raise forms.ValidationError("Tanggal lahir tidak boleh di masa depan.")
        return birth_date

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        users = User.objects.filter(email__iexact=email)
        current_user = getattr(self, "current_user", None)
        if current_user is not None:
            users = users.exclude(pk=current_user.pk)
        if users.exists():
            raise forms.ValidationError("Email ini sudah digunakan oleh akun lain.")
        return email


class RegistrationForm(ProfileFieldsMixin, UserCreationForm):
    full_name = forms.CharField(label="Nama lengkap", max_length=150)
    email = forms.EmailField(label="Email", max_length=254)
    domicile = forms.CharField(label="Domisili", max_length=150)
    birth_date = forms.DateField(
        label="Tanggal lahir", widget=forms.DateInput(attrs={"type": "date"})
    )
    social_contact = forms.CharField(
        label="Kontak media sosial", max_length=200, required=False,
        help_text="Opsional, contoh: Instagram @nama atau nomor WhatsApp.",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "username", "full_name", "email", "domicile", "birth_date",
            "social_contact", "password1", "password2",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Username"
        self.fields["password1"].label = "Password"
        self.fields["password2"].label = "Konfirmasi password"
        self.fields["username"].widget.attrs["autocomplete"] = "username"
        self.fields["full_name"].widget.attrs["autocomplete"] = "name"
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        self.fields["password1"].widget.attrs["autocomplete"] = "new-password"
        self.fields["password2"].widget.attrs["autocomplete"] = "new-password"

    def _post_clean(self):
        # Include the profile name in Django's password similarity checks.
        self.instance.first_name = self.cleaned_data.get("full_name", "")
        super()._post_clean()

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data["full_name"]
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            Profile.objects.update_or_create(
                user=user,
                defaults={
                    field: self.cleaned_data[field]
                    for field in ("domicile", "birth_date", "social_contact")
                },
            )
        return user


class LoginForm(AuthenticationForm):
    username = UsernameField(
        label="Username atau email",
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}),
    )
    password = forms.CharField(
        label="Password", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].max_length = 254
        self.fields["username"].widget.attrs["maxlength"] = 254

    def clean(self):
        identifier = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if not identifier or not password:
            return super().clean()
        try:
            # Usernames may contain @. Authenticate that username before trying
            # email so a matching email on another account cannot shadow it.
            return super().clean()
        except forms.ValidationError:
            matches = list(User.objects.filter(email__iexact=identifier)[:2])
            if len(matches) != 1:
                raise self.get_invalid_login_error() from None
            self.cleaned_data["username"] = matches[0].get_username()
            # Both attempts use Django's backend, including its inactive-user
            # check. Failed attempts expose only the normal generic error.
            return super().clean()


class ProfileForm(ProfileFieldsMixin, forms.ModelForm):
    full_name = forms.CharField(label="Nama lengkap", max_length=150)
    email = forms.EmailField(label="Email", max_length=254)

    class Meta:
        model = Profile
        fields = ("full_name", "email", "domicile", "birth_date", "social_contact")
        widgets = {"birth_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}

    def __init__(self, *args, user, **kwargs):
        self.current_user = user
        super().__init__(*args, **kwargs)
        self.fields["full_name"].initial = user.get_full_name()
        self.fields["email"].initial = user.email
        self.fields["full_name"].widget.attrs["autocomplete"] = "name"
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        for field in ("domicile", "birth_date"):
            self.fields[field].required = True

    @transaction.atomic
    def save(self, commit=True):
        profile = super().save(commit=False)
        self.current_user.first_name = self.cleaned_data["full_name"]
        self.current_user.last_name = ""
        self.current_user.email = self.cleaned_data["email"]
        if commit:
            self.current_user.save(update_fields=["first_name", "last_name", "email"])
            profile.save()
        return profile


class PreferencesForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ("email_notifications", "profile_visibility", "language")


class DeactivateAccountForm(forms.Form):
    password = forms.CharField(
        label="Password saat ini", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password", "id": "id_deactivate_password"}),
    )
    confirm = forms.BooleanField(label="Saya ingin menonaktifkan akun ini.")

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("Password tidak benar.")
        return password
