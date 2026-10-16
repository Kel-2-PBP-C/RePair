import ssl
from pathlib import Path

import requests.certs
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Ekspor CA yang sudah dipercaya sistem; tidak mengubah atau menonaktifkan verifikasi TLS.'

    def handle(self, *args, **options):
        context = ssl.create_default_context()
        certificates = context.get_ca_certs(binary_form=True)
        if not certificates:
            raise CommandError('Tidak ada sertifikat CA sistem untuk diekspor.')
        target = settings.BASE_DIR / '.test-artifacts' / 'windows-ca-bundle.pem'
        target.parent.mkdir(parents=True, exist_ok=True)
        standard_bundle = Path(requests.certs.where()).read_text(encoding='ascii')
        target.write_text(
            standard_bundle + ''.join(ssl.DER_cert_to_PEM_cert(cert) for cert in certificates),
            encoding='ascii',
        )
        self.stdout.write(self.style.SUCCESS('Bundle CA sistem tersimpan. Isi BOGORTECH_CA_BUNDLE dengan path berikut:'))
        self.stdout.write(str(target.resolve()))
