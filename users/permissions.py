from rest_framework.permissions import BasePermission
from .models import SystemSettings

class IsServiceActive(BasePermission):
  # Custom permission to check if the carpooling service is active based on SystemSettings.
    message = "The carpooling service is currently suspended by the administrator."

    def has_permission(self, request, view):
        # Fetch the single row of settings. If it doesn't exist, assume True.
        settings = SystemSettings.objects.first()
        if settings:
            return settings.is_carpool_active
        return True