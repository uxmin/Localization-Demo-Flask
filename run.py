import json
import os

from flask import (
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app import app


@app.context_processor
def inject_menus():
    service_info_path = os.path.join(current_app.root_path, "data", "jsons", "service.json")
    with open(service_info_path, "r") as f:
        services = json.load(f)
    active_services = [service for service in services if service["use"]]
    return dict(services=active_services)


@app.before_request
def before_request():
    if "user_id" not in session and request.endpoint not in ("auth.login", "static", "favicon.ico"):
        session.modified = True
        return redirect(url_for("auth.login"))


@app.route("/demo/")
@app.route("/demo/index")
@app.route("/demo/home")
def index():
    restaurant_info_path = os.path.join(current_app.root_path, "data", "jsons", "restaurant.json")
    with open(restaurant_info_path, "r") as f:
        restaurants = json.load(f)
    return render_template("index.html.j2", restaurants=restaurants)


if __name__ == "__main__":
    app.run(debug=app.config.get("DEBUG"))
