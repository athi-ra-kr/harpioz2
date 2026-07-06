def site_settings(request):
    try:
        from .models import SiteSettings
        return {'site_settings': SiteSettings.get()}
    except Exception:
        return {'site_settings': None}
