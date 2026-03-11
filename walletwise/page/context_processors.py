from decimal import Decimal
from .models import UserProfile


def sidebar_context(request):
    """Inject net_balance into every page for the sidebar balance display."""
    if not request.user.is_authenticated:
        return {}
    try:
        profile = request.user.profile
        net_balance = profile.get_net_balance()
    except Exception:
        net_balance = Decimal('0')
    return {'net_balance': net_balance}