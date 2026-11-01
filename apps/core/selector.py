from asgiref.sync import sync_to_async

from apps.core.models import Station


@sync_to_async
def station_selector():
    return [
        {
            "Code": item["code"],
            "Name": item["name"],
            "EnglishName": item["english_name"],
            "TelCode": item["tel_code"],
            "Group": item["group"],
            "IsCarTicket": item["is_car_ticket"],
            "IsExclusion": item["is_exclusion"],
        }
        for item in Station.objects.values(
            "code",
            "name",
            "english_name",
            "tel_code",
            "group",
            "is_car_ticket",
            "is_exclusion",
        )
    ]
