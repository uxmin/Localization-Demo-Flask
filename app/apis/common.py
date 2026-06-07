import json
import os

from flask import (
    Blueprint,
    current_app,
    jsonify,
    request,
)

from app.schemas.error import ErrorCode
from app.schemas.response import Response

bp_common = Blueprint("common", __name__, url_prefix="/demo/common")


@bp_common.route("/restaurant", methods=["POST"])
def write_restaurant():
    try:
        data = request.get_json()

        restaurant_info_path = os.path.join(current_app.root_path, "data", "jsons", "restaurant.json")
        with open(restaurant_info_path, "r", encoding="utf-8") as f:
            restaurants = json.load(f)

        names = [restaurant["name"] for restaurant in restaurants]

        if data.get("name", "") in names:
            return jsonify(Response().error_response(ErrorCode.DUPLICATE_ENTRY).model_dump())

        restaurants.append(data)
        with open(restaurant_info_path, "w", encoding="utf-8") as f:
            json.dump(restaurants, f, ensure_ascii=False, indent=2)

        return jsonify(Response().successful_response({"message": "success"}).model_dump())
    except FileNotFoundError:
        return jsonify(Response().error_response(ErrorCode.PROMPT_NOT_FOUND).model_dump())
    except Exception as e:
        current_app.logger.error(f"Error processing Excel file: {str(e)}")
        return jsonify(Response().error_response(ErrorCode.INTERNAL_SERVER_ERROR).model_dump())


@bp_common.route("/restaurant", methods=["DELETE"])
def delete_restaurant():
    try:
        data = request.get_json()
        restaurant_name = data.get("name", "")

        restaurant_info_path = os.path.join(current_app.root_path, "data", "jsons", "restaurant.json")
        with open(restaurant_info_path, "r", encoding="utf-8") as f:
            restaurants = json.load(f)

        updated_restaurants = [restaurant for restaurant in restaurants if restaurant["name"] != restaurant_name]

        if len(updated_restaurants) == len(restaurants):
            return jsonify(Response().error_response(ErrorCode.DATA_NOT_FOUND).model_dump())

        with open(restaurant_info_path, "w", encoding="utf-8") as f:
            json.dump(updated_restaurants, f, ensure_ascii=False, indent=2)

        return jsonify(Response().successful_response({"message": "Restaurant deleted successfully"}).model_dump())
    except FileNotFoundError:
        return jsonify(Response().error_response(ErrorCode.PROMPT_NOT_FOUND).model_dump())
    except Exception as e:
        current_app.logger.error(f"Error processing request: {str(e)}")
        return jsonify(Response().error_response(ErrorCode.INTERNAL_SERVER_ERROR).model_dump())
