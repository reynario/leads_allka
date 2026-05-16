"""Inicializacao do Jinja2Templates compartilhado pelos routers UI."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _format_status(value: str | None) -> str:
    labels = {
        "pending": "Pendente",
        "processing": "Processando",
        "completed": "Completo",
        "failed": "Falhou",
        "sent_to_bitrix": "Enviado",
    }
    return labels.get(value or "", value or "")


def _format_yesno(value):  # noqa: ANN001
    if value is True:
        return "Sim"
    if value is False:
        return "Nao"
    return "—"


def _format_datetime(value):  # noqa: ANN001
    if value is None:
        return "—"
    return value.strftime("%d/%m/%Y %H:%M")


templates.env.filters["status_label"] = _format_status
templates.env.filters["yesno"] = _format_yesno
templates.env.filters["br_datetime"] = _format_datetime
