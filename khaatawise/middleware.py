import logging
import time
from django.utils.deprecation import MiddlewareMixin

request_logger = logging.getLogger("khaatawise.request")


class RequestResponseLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to log incoming requests (input log) and outgoing responses (output log).
    """

    def process_request(self, request):
        # Store start time on the request object for duration calculation
        request._start_time = time.time()
        return None

    def process_response(self, request, response):
        # Calculate request duration
        duration = 0
        if hasattr(request, "_start_time"):
            duration = int((time.time() - request._start_time) * 1000)

        # Extract request info
        user = getattr(request, "user", None)
        username = user.username if user and user.is_authenticated else "anonymous"
        ip = self.get_client_ip(request)

        # Log the request (input log)
        request_logger.info(
            "",
            extra={
                "method": request.method,
                "path": request.get_full_path(),
                "user": username,
                "ip": ip,
                "status": response.status_code,
                "duration": duration,
            },
        )

        return response

    def get_client_ip(self, request):
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")