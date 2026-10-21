from whitenoise.storage import CompressedManifestStaticFilesStorage


class StaticFilesStorage(CompressedManifestStaticFilesStorage):
    """Manifest static storage that degrades gracefully.

    Django's default ``manifest_strict`` behaviour raises ``ValueError`` when a
    static file is missing from the generated manifest, which turns a missing
    asset into a 500 error. Product catalogue images are resolved at runtime
    through ``django.contrib.staticfiles.finders``, so a single unmatched
    upload should not take a page down. With ``manifest_strict = False`` the
    unhashed URL is returned instead and the request simply 404s.
    """

    manifest_strict = False
