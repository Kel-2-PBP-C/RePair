from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, UsernameField
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone

from .models import Profile
from . import regions

User = get_user_model()
username_model_field = User._meta.get_field(User.USERNAME_FIELD)


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
        label="Kontak pilihan", max_length=200, required=False,
        help_text="Opsional. Isi kontak yang Anda pilih, misalnya WhatsApp, LINE, atau username media sosial.",
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
        # Validasi kemiripan password juga memakai nama profil.
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
            # Username yang berisi @ diperiksa sebelum pencarian email.
            return super().clean()
        except forms.ValidationError:
            matches = list(User.objects.filter(email__iexact=identifier)[:2])
            if len(matches) != 1:
                raise self.get_invalid_login_error() from None
            self.cleaned_data["username"] = matches[0].get_username()


            return super().clean()


class RegionSelectionMixin:
    def clean(self):
        cleaned_data = super().clean()
        code = cleaned_data.get("domicile_code", "")
        if "domicile_code" in self.errors:
            self.add_error("domicile", "Pilihan lokasi tidak valid. Cari dan pilih daerah lagi.")
        elif code and not (
            code == self.instance.domicile_code
            and cleaned_data.get("domicile") == self.instance.domicile
        ):
            try:
                region = regions.lookup_region(code)
            except regions.RegionServiceError:
                self.add_error(
                    "domicile",
                    "Pilihan lokasi belum dapat diverifikasi. Coba lagi atau ketik lokasi secara manual.",
                )
            else:
                if region is None:
                    self.add_error("domicile", "Pilihan lokasi tidak valid. Cari dan pilih daerah lagi.")
                elif "domicile" in cleaned_data:
                    cleaned_data["domicile"] = region["label"]
                    cleaned_data["domicile_code"] = region["code"]
        return cleaned_data


class ProfileForm(ProfileFieldsMixin, RegionSelectionMixin, forms.ModelForm):
    username = UsernameField(
        label="Username", max_length=username_model_field.max_length,
        validators=username_model_field.validators,
        widget=forms.TextInput(attrs={"autocomplete": "username"}),
    )
    full_name = forms.CharField(label="Nama lengkap", max_length=150)
    email = forms.EmailField(label="Email", max_length=254)
    domicile_code = forms.CharField(required=False, max_length=20, widget=forms.HiddenInput)
    preferred_categories = forms.MultipleChoiceField(
        label="Kategori barang pilihan", choices=Profile.CATEGORY_CHOICES,
        required=False, widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Profile
        fields = (
            "username", "full_name", "email", "domicile", "domicile_code",
            "preferred_categories", "birth_date", "social_contact",
        )
        labels = {"social_contact": "Kontak pilihan"}
        help_texts = {
            "social_contact": (
                "Opsional. Isi kontak yang Anda pilih, misalnya WhatsApp, LINE, "
                "atau username media sosial."
            )
        }
        widgets = {"birth_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}

    def __init__(self, *args, user, **kwargs):
        self.current_user = user
        self.is_google_account = hasattr(user, "google_identity")
        super().__init__(*args, **kwargs)
        self._original_domicile = self.instance.domicile
        self.fields["username"].initial = user.get_username()
        self.fields["username"].required = not self.is_bound or "username" in self.data
        self.fields["full_name"].initial = user.get_full_name()
        self.fields["email"].initial = user.email
        self.fields["full_name"].widget.attrs["autocomplete"] = "name"
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        if self.is_google_account:
            self.fields["email"].disabled = True
            self.fields["email"].help_text = (
                "Email terverifikasi dari akun Google dan tidak dapat diubah di sini."
            )
        for field in ("domicile", "birth_date"):
            self.fields[field].required = True

    def clean_email(self):
        if self.is_google_account:
            # Email Google tidak boleh diganti lewat POST.
            return self.current_user.email
        return super().clean_email()

    def clean_username(self):
        if self.is_bound and "username" not in self.data:
            return self.current_user.get_username()
        username = User.normalize_username(self.cleaned_data["username"])
        if User.objects.filter(**{User.USERNAME_FIELD: username}).exclude(pk=self.current_user.pk).exists():
            raise forms.ValidationError("Username ini sudah digunakan oleh akun lain.")
        return username

    def clean_preferred_categories(self):
        if self.is_bound and not self.data.get("preferred_categories_present") and "preferred_categories" not in self.data:
            return self.instance.preferred_categories
        return self.cleaned_data["preferred_categories"]

    def clean_domicile_code(self):
        if self.is_bound and "domicile_code" not in self.data and self.cleaned_data.get("domicile") == self._original_domicile:
            return self.instance.domicile_code
        return self.cleaned_data.get("domicile_code", "")

    @transaction.atomic
    def save(self, commit=True):
        profile = super().save(commit=False)
        if profile.domicile != self._original_domicile and not self.cleaned_data.get("domicile_code"):
            # Lokasi manual tidak boleh menyimpan kode wilayah dari pilihan sebelumnya.
            profile.domicile_code = ""
        self.current_user.first_name = self.cleaned_data["full_name"]
        self.current_user.last_name = ""
        self.current_user.email = self.cleaned_data["email"]
        self.current_user.username = self.cleaned_data["username"]
        if commit:
            self.current_user.save(update_fields=["first_name", "last_name", "email", "username"])
            profile.save()
        return profile


class GoogleProfileCompletionForm(RegionSelectionMixin, forms.ModelForm):
    username = UsernameField(
        label="Username", max_length=username_model_field.max_length,
        validators=username_model_field.validators,
        widget=forms.TextInput(attrs={"autocomplete": "username"}),
    )
    domicile_code = forms.CharField(
        required=False, max_length=20, widget=forms.HiddenInput,
    )
    preferred_categories = forms.MultipleChoiceField(
        label="Kategori barang preferred", choices=Profile.CATEGORY_CHOICES,
        required=False, widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Profile
        fields = ("username", "domicile", "domicile_code", "preferred_categories")
        labels = {"domicile": "Location"}
        widgets = {"domicile": forms.TextInput(attrs={"autocomplete": "address-level2"})}

    def __init__(self, *args, user, **kwargs):
        self.current_user = user
        super().__init__(*args, **kwargs)
        self.fields["username"].initial = user.get_username()
        self.fields["domicile"].required = True

    def clean_username(self):
        username = User.normalize_username(self.cleaned_data["username"])
        if User.objects.filter(**{User.USERNAME_FIELD: username}).exclude(pk=self.current_user.pk).exists():
            raise forms.ValidationError("Username ini sudah digunakan oleh akun lain.")
        return username

    @transaction.atomic
    def save(self, commit=True):
        profile = super().save(commit=False)
        self.current_user.username = self.cleaned_data["username"]
        profile.onboarding_completed = True
        if commit:
            self.current_user.save(update_fields=["username"])
            profile.save()
        return profile


class GoogleCredentialsForm(forms.Form):
    username = UsernameField(
        label="Username",
        max_length=username_model_field.max_length,
        validators=username_model_field.validators,
        widget=forms.TextInput(attrs={"autocomplete": "username"}),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Type Your Password Here"}),
    )

    def __init__(self, *args, user, setup, **kwargs):
        self.user = user
        self.setup = setup
        super().__init__(*args, **kwargs)
        self.fields["password"].widget.attrs["autocomplete"] = (
            "new-password" if setup else "current-password"
        )

    def clean_username(self):
        username = User.normalize_username(self.cleaned_data["username"])
        if self.setup:
            users = User.objects.filter(
                **{User.USERNAME_FIELD: username}
            ).exclude(pk=self.user.pk)
            if users.exists():
                raise forms.ValidationError("Username ini sudah digunakan oleh akun lain.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        if self.setup and "username" in cleaned_data and "password" in cleaned_data:
            password_user = User(
                **{
                    User.USERNAME_FIELD: cleaned_data["username"],
                    "email": self.user.email,
                    "first_name": self.user.first_name,
                    "last_name": self.user.last_name,
                }
            )
            try:
                validate_password(cleaned_data["password"], user=password_user)
            except forms.ValidationError as error:
                self.add_error("password", error)
        return cleaned_data


class PreferencesForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ("email_notifications", "profile_visibility", "language")


class DeactivateAccountForm(forms.Form):
    password = forms.CharField(
        label="Password saat ini", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password", "id": "id_deactivate_password"}),
    )
    confirm = forms.BooleanField(
        label=(
            "Saya memahami bahwa akun, profil, dan semua data milik saya akan dihapus "
            "permanen dan tidak dapat dipulihkan."
        ),
        required=True,
    )

    def __init__(self, *args, user, google_authenticated=False, **kwargs):
        self.user = user
        self.is_google_account = hasattr(user, "google_identity")
        self.google_authenticated = google_authenticated
        super().__init__(*args, **kwargs)
        self.requires_google_reauth = self.is_google_account and not user.has_usable_password()
        if self.requires_google_reauth:
            self.fields.pop("password")

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("Password tidak benar.")
        return password

    def clean(self):
        cleaned_data = super().clean()
        if self.requires_google_reauth and not self.google_authenticated:
            raise forms.ValidationError(
                "Verifikasi ulang akun Google terlebih dahulu sebelum menghapus akun."
            )
        return cleaned_data


class GoogleAccountLinkForm(forms.Form):
    username = UsernameField(
        label="Username",
        max_length=username_model_field.max_length,
        validators=username_model_field.validators,
        widget=forms.TextInput(attrs={"autocomplete": "username"}),
    )

    password = forms.CharField(
        label="Kata sandi RePair lama",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    confirm = forms.BooleanField(
        label="Saya ingin menautkan akun RePair ini dengan akun Google yang dipilih.",
        required=True,
    )

    def clean_username(self):
        return User.normalize_username(self.cleaned_data["username"])
