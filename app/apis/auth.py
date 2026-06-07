import hmac

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

bp_auth = Blueprint("auth", __name__, url_prefix="/demo/auth")


def _verify_credentials(user_id: str, password: str) -> bool:
    """환경 변수로 주입된 단일 데모 계정과 상수 시간 비교로 검증한다."""
    expected_id = current_app.config.get("AUTH_USERNAME", "")
    expected_pw = current_app.config.get("AUTH_PASSWORD", "")
    if not expected_id or not expected_pw:
        current_app.logger.error("AUTH_USERNAME/AUTH_PASSWORD가 설정되지 않았습니다.")
        return False
    # 타이밍 공격 방지를 위해 두 비교 모두 수행한다.
    id_ok = hmac.compare_digest(user_id, expected_id)
    pw_ok = hmac.compare_digest(password, expected_pw)
    return id_ok and pw_ok


@bp_auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user_id = request.form.get("user_id", "")
        password = request.form.get("password", "")
        if _verify_credentials(user_id, password):
            session["user_id"] = user_id
            session.permanent = True
            return redirect(url_for("index"))

        flash("Login Failed. Please check your username and password.")
        return redirect(url_for("auth.login"))

    return render_template("login.html.j2")


@bp_auth.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("auth.login"))
