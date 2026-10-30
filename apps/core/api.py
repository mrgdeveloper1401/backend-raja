from django_bolt import BoltAPI

api = BoltAPI()


@api.get("/")
async def mission_control_status():
    return {"status": "operational", "message": "app Control Online"}
