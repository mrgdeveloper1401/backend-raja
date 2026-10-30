from django.db.models import Q
from django.db.models.manager import Manager
from django.db.models.query import QuerySet


class SoftDeleteQuerySet(QuerySet):
    def alive(self):
        return self.filter(
            Q(deleted_at__isnull=True)
            | Q(is_deleted=False)
            | Q(deleted_at__isnull=True)
        )


class SoftDeleteManager(Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).alive()
