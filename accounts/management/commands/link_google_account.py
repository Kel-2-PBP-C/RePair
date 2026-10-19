from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from accounts.models import GoogleIdentity


class Command(BaseCommand):
    help = 'Tautkan akun lama setelah pengelola memverifikasi kendali akun dan Google subject.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--subject', required=True)
        parser.add_argument('--email', required=True)
        parser.add_argument('--confirm-verified', action='store_true')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        if not options['confirm_verified']:
            raise CommandError('Verifikasi kendali akun lama dan subject dari ID token Google yang sah terlebih dahulu; lalu gunakan --confirm-verified.')
        subject = options['subject'].strip()
        email = options['email'].strip().lower()
        if not subject or not subject.isascii() or len(subject) > 255:
            raise CommandError('Google subject tidak valid.')
        try:
            with transaction.atomic():
                User = get_user_model()
                user = User.objects.select_for_update().get(username=options['username'])
                if not user.is_active:
                    raise CommandError('Akun tidak aktif; periksa status akun sebelum penautan.')
                if user.email.strip().lower() != email:
                    raise CommandError('Email terverifikasi harus cocok dengan email akun lama.')
                if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
                    raise CommandError('Email akun lama berbenturan. Selesaikan benturan melalui pengelola.')
                identity = GoogleIdentity.objects.filter(user=user).first()
                if identity:
                    if identity.subject != subject:
                        raise CommandError('Akun sudah terhubung ke identitas Google lain.')
                    self.stdout.write('Akun sudah tertaut; tidak ada perubahan.')
                    return
                if GoogleIdentity.objects.filter(subject=subject).exists():
                    raise CommandError('Identitas Google sudah digunakan oleh akun lain.')
                if options['dry_run']:
                    self.stdout.write('Pemeriksaan berhasil. Dry run: tidak ada perubahan data.')
                    return
                GoogleIdentity.objects.create(user=user, subject=subject, email=email)
        except User.DoesNotExist:
            raise CommandError('Username akun lama tidak ditemukan.') from None
        except IntegrityError:
            raise CommandError('Penautan berbenturan dengan identitas lain; tidak ada perubahan data.') from None
        self.stdout.write(self.style.SUCCESS('Akun lama berhasil ditautkan. Role dan relasi existing dipertahankan.'))
