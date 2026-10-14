import httpx
from supabase import create_client

try:
    from supabase import ClientOptions
except ImportError:
    from supabase.lib.client_options import SyncClientOptions as ClientOptions

from core.config import SUPABASE_URL, SUPABASE_SERVICE_KEY

# Errors that mean "the connection dropped", not "the server said no"
_DROPPED = (httpx.RemoteProtocolError, httpx.ReadError, httpx.ConnectError)


class RetryClient(httpx.Client):
    """Retries once if the connection drops during a read-only (GET) request."""

    def send(self, request, **kwargs):
        try:
            return super().send(request, **kwargs)
        except _DROPPED:
            if request.method in ("GET", "HEAD", "OPTIONS"):
                return super().send(request, **kwargs)
            raise


_http = RetryClient(
    http2=False,
    timeout=httpx.Timeout(30.0),
    limits=httpx.Limits(keepalive_expiry=5.0),
    follow_redirects=True,
)

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY,
    options=ClientOptions(httpx_client=_http),
)
