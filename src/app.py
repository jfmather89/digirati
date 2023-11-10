"""Provide an API to get authors, associated locations and their counts from a
given text in a json post request
"""
from typing import Any, TypedDict

from flask import Flask, request, make_response, Request, jsonify
from werkzeug.exceptions import BadRequest, InternalServerError
import requests


class NERResponse(TypedDict):
    entity_group: str
    score: float
    word: str
    start: int
    end: int



def create_app() -> Flask:
    app = Flask(__name__)

    return app


def handle_post_request(request: Request):
    if not request.is_json:
        return make_response("The content-type is not application/json", 400)


def handle_json_request(request: Request):
    request_json_data = request.get_json(force=True)
    handle_json_data(request_json_data)
    text_file_string = handle_download_file(request_json_data["URL"])


def handle_json_data(json_data: dict[str, Any]):
    if "URL" not in json_data:
        raise BadRequest(
            response=make_response(
                'Bad request: "URL" field not provided in the json request', 400
            )
        )
    url = json_data["URL"]
    if not isinstance(url, str):
        raise BadRequest(response=make_response('The provided value under the field "URL" was not a string'))


def handle_download_file(url: str) -> str:
    response = requests.get(url)
    if not response.ok:
        raise BadRequest(response=make_response(
            f"The url provided: '{url}' gave the following error:\n{response.reason}",
            400
        ))
    return response.content.decode("utf-8")


def handle_text_file_computation(text_string: str):
    ner = get_ner_from_text(text_string)
    


def get_ner_from_text(text_string: str, api_url: str, api_token: str) -> list[NERResponse]:
    headers = {"Authorization": f"Bearer {api_token}"}
    response = requests.post(
        api_url,
        headers=headers,
        json={"inputs": text_string}
    )
    if not response.ok:
        raise InternalServerError("The API used for computing is not functioning. Please try again later")
    ner = response.json()
    return ner

