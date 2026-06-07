from flask import (
    Blueprint,
    abort,
    redirect,
    render_template,
    url_for,
)
from jinja2 import TemplateNotFound

bp_page = Blueprint("page", __name__, url_prefix="/demo/page")


@bp_page.route("/<service_name>")
def service(service_name: str):
    try:
        service_file = service_name.replace("-", "_")
        template = render_template(f"service/{service_file}.html.j2", current_service=service_name)
        if not template:
            abort(404)
        return template
    except TemplateNotFound:
        return redirect(url_for("index"))


@bp_page.route("/<service_name>/<int:idx>")
def detail(service_name: str, idx: int):
    try:
        service_file = service_name.replace("-", "_")
        template = render_template(
            f"service/{service_file}_detail.html.j2", current_service=service_name, current_id=idx
        )
        if not template:
            abort(404)
        return template
    except TemplateNotFound:
        return redirect(url_for("index"))
