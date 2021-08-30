from cloudify_api import CloudifyAPI
from cloudify_api.routers import audit as audit_router


TITLE = "Cloudify API"
VERSION = "6.3.0.dev1"
DEBUG = False


def create_application() -> CloudifyAPI:
    application = CloudifyAPI(title=TITLE, version=VERSION, debug=DEBUG)
    application.include_router(audit_router, prefix="/api/v3.1")
    return application


app = create_application()
