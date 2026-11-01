from django.apps import AppConfig


class TicketConfig(AppConfig):
    name = "apps.ticket"

    def ready(self):
        import apps.ticket.signals
