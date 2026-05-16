from fastapi.templating import Jinja2Templates

from app.core.config import Settings


def build_templates(settings: Settings) -> Jinja2Templates:
    return Jinja2Templates(directory=str(settings.templates_dir))


templates = build_templates(Settings())
