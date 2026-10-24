from flask import Blueprint, render_template

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    return render_template("scanner.html")


@bp.route("/scanner")
def scanner():
    return render_template("scanner.html")


@bp.route("/data-map")
def data_map():
    return render_template("data_map.html")


@bp.route("/rights-desk")
def rights_desk():
    return render_template("rights_desk.html")


@bp.route("/breach-simulator")
def breach_simulator():
    return render_template("breach_simulator.html")


@bp.route("/risk-analysis")
def risk_analysis():
    return render_template("risk_analysis.html")


@bp.route("/reports")
def reports():
    return render_template("reports.html")


@bp.route("/evidence")
def evidence():
    return render_template("evidence.html")
