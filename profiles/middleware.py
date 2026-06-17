from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone


class UserTimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                user_timezone = request.user.profile.timezone
            except ObjectDoesNotExist:
                user_timezone = None

            if user_timezone:
                timezone.activate(user_timezone)
            else:
                timezone.deactivate()
        else:
            timezone.deactivate()

        return self.get_response(request)