from django.db.models import Q
from django.db.models.manager import Manager
from django.db.models.query import QuerySet
from django.utils import timezone


class SoftDeleteQuerySet(QuerySet):
    def alive(self):
        return self.filter(Q(is_deleted=False) | Q(deleted_at__isnull=True))

    def delete(self):
        return super().update(is_deleted=True, deleted_at=timezone.now())


class SoftDeleteManager(Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).alive()
