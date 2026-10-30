from typing import Union

from django_bolt.serializers import Serializer


class StationSerializer(Serializer):
    Code: Union[str, int]
    Name: str
    EnglishName: str
    TelCode: str
    Group: str
    IsCarTicket: bool
    IsExclusion: bool
