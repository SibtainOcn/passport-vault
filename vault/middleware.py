class PrivacyHeaders:
    def __init__(self, get_response): self.get_response = get_response
    def __call__(self, request):
        response = self.get_response(request)
        response['Cache-Control'] = 'no-store'
        response['Referrer-Policy'] = 'no-referrer'
        response['X-Frame-Options'] = 'DENY'
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        response['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; connect-src 'self'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
        return response
