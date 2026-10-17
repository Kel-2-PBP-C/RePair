import logging
import re


class OAuthCallbackFilter(logging.Filter):
    pattern = re.compile(r'(/accounts/google/callback/)\?[^\s\"]*')

    def filter(self, record):
        record.msg = self.pattern.sub(r'\1?<redacted>', record.getMessage())
        record.args = ()
        return True
