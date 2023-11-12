"""Provide an API to get authors, associated locations and their counts from a
given text in a json post request
"""
from typing import Any, TypedDict, NotRequired, Literal

from tqdm import tqdm
from flask import Flask, request, make_response, Response
from werkzeug.exceptions import BadRequest, GatewayTimeout
import requests
import spacy
from spacy.tokens import Doc

# Best model I could get to work on my machine without taking 10 mins or using
# up all memory
nlp = spacy.load(
    "en_core_web_sm",
    disable=["tok2vec", "tagger", "parser", "attribute_ruler", "lemmatizer"],
)
# nlp = spacy.load("en_core_web_trf")


class NamedEntityDict(TypedDict):
    """Type hints for dictionary"""

    name: str
    """The name of the entity"""
    count: int
    """The entities appearance count
    """
    locations: NotRequired[
        dict[str, "NamedEntityDict"] | list["NamedEntityDict"]
    ]
    """Associated locations to the entity, optional
    """


class PositionalEntityDict(TypedDict):
    """A named entity with positional fields indicating the its start and end
    word numbers a sequence of words
    """

    name: str
    """The named entity
    """
    start: int
    """The word position of the start word of the entity
    """
    end: int
    """The word position of the end word of the entity
    """


def create_app() -> Flask:
    """Creates the flask app and sets up the following endpoints

    * `/get-people` - This endpoint accepts a json request with the
    following form

        ```
        {"URL": <An url accepting a get request to utf-8 encoded data>}
        ```

    :return: Returns the app
    :rtype: :class:`Flask`
    """
    app = Flask(__name__)

    @app.route("/get-people", methods=["POST"])
    def get_people() -> Response:
        """Handles a JSON POST request to the end point `/get-people`. Will
        accept a request with content
        type that isn't `application/json` as long as the body is serializable
        to json

        :return: Returns the response as JSON with status 200 if the request
        was successful
        :rtype: :class:`Response`
        """
        # handle getting json from the request
        request_json_data = request.get_json(force=True)
        # check is json is in the correct format
        handle_json_data(request_json_data)
        # download the url provided into memory
        text_string = handle_download_file(request_json_data["URL"])
        # extract the named entities form the text
        output = handle_text_file_computation(text_string)
        # create the final JSON response data
        json_to_return = {**request_json_data, "people": output}
        return make_response(json_to_return, 200)

    return app


def handle_json_data(json_data: dict[str, Any]) -> None:
    """Method to check the provided json data is correct

    :param json_data: The JSON request data given
    :type json_data: `dict`[`str`, `Any`]
    :raises BadRequest: Raise a `BadRequest` exception if there is no "URL"
    field
    provided in the json request
    :raises BadRequest: _description_
    """
    if "URL" not in json_data:
        raise BadRequest(
            response=make_response(
                'Bad request: "URL" field not provided in the json request',
                400,
            )
        )
    url = json_data["URL"]
    if not isinstance(url, str):
        raise BadRequest(
            response=make_response(
                'The provided value under the field "URL" was not a string'
            )
        )


def handle_download_file(url: str) -> str:
    """Handles the download of the file from the given url

    :param url: The provided url
    :type url: `str`
    :raises GatewayTimeout: Raises and internal server error when the
    request to the given url times out
    :raises BadRequest: Raises a `BadRequest` exception if the url provided
    fails a get request
    :return: Returns the content decoded as a utf-8 string
    :rtype: `str`
    """
    try:
        response = requests.get(url, timeout=10)
    except TimeoutError:
        raise GatewayTimeout(
            "Download of file from given url timed out, retry later"
        )
    if not response.ok:
        raise BadRequest(
            response=make_response(
                f"The url provided: '{url}' gave the following"
                f"error:\n{response.reason}",
                400,
            )
        )
    return response.content.decode("utf-8")


def handle_text_file_computation(text_string: str) -> list[NamedEntityDict]:
    """Handle getting Named entities People within a document and calculating
    * the number of appearances of each person
    * the locations associated with each person and the number of times they
    are associated with tht person

    :param text_string: The document to extract entities as a string
    :type text_string: `str`
    :return: Returns a list of dictionarys with the :class:`NamedEntityDict`
    structure
    :rtype: `list`[:class:`NamedEntityDict`]
    """
    # split the text into separate lines
    text_lines = text_string.splitlines()
    # create the partia output dictionary
    output_dict: dict[str, NamedEntityDict] = {}
    # create buffer lists for positions of entities of people and locations
    people_entities_buffer: list[PositionalEntityDict] = []
    loc_entities_buffer: list[PositionalEntityDict] = []
    # set the word number offest to 0
    word_number_offset = 0
    # iterate over the lines of the text and extract entities from documents
    for doc in tqdm(nlp.pipe(text_lines), total=len(text_lines)):
        handle_entities_from_doc(
            doc=doc,
            output_dict=output_dict,
            people_entities_buffer=people_entities_buffer,
            loc_entities_buffer=loc_entities_buffer,
            word_number_offset=word_number_offset,
        )
        # update the word number offset for the legnth of each document
        word_number_offset += len(doc)
    # make sure output is in the correct format for the response
    output = [
        NamedEntityDict(
            name=person_dict["name"],
            count=person_dict["count"],
            locations=list(person_dict["locations"].values()),
        )
        for person_dict in output_dict.values()
    ]
    return output


def handle_entities_from_doc(
    doc: Doc,
    output_dict: dict[str, NamedEntityDict],
    people_entities_buffer: list[PositionalEntityDict],
    loc_entities_buffer: list[PositionalEntityDict],
    word_number_offset: int,
) -> None:
    """Method to handle getting the entities PERSON and LOC from a document
    and updating the output dict with the "PERSON" entites with counts and
    their associated locations with counts. Filters out labels that are not
    PERSON or LOC

    :param doc: The object containing the named enties extracted
    :type doc: :class:`Doc`
    :param output_dict: The output dictionary
    :type output_dict: `dict`[`str`, :class:`NamedEntityDict`]
    :param people_entities_buffer: A buffer list of PERSON entites used to
    efficiently get locations within 100 words of the entity
    :type people_entities_buffer: `list`[:class:`PositionalEntityDict`]
    :param loc_entities_buffer: A buffer list of LOC entities used to
    efficiently get people within 100 words of the entity
    :type loc_entities_buffer: :class:`list`[:class:`PositionalEntityDict`]
    :param word_number_offset: An offset used to update the position of words
    relative to the full document
    :type word_number_offset: `int`
    """
    for entity in doc.ents:
        label = entity.label_
        if label not in ["PERSON", "LOC"]:
            continue
        entity_dict = PositionalEntityDict(
            name=str(entity),
            start=entity.start + word_number_offset,
            end=entity.end + word_number_offset,
        )
        handle_positional_entity_update(
            entity_dict=entity_dict,
            output_dict=output_dict,
            people_entities_buffer=people_entities_buffer,
            loc_entities_buffer=loc_entities_buffer,
            label=label,
        )


def handle_positional_entity_update(
    entity_dict: PositionalEntityDict,
    output_dict: dict[str, NamedEntityDict],
    people_entities_buffer: list[PositionalEntityDict],
    loc_entities_buffer: list[PositionalEntityDict],
    label: Literal["PERSON"] | Literal["LOC"],
) -> None:
    """Handle the update of the output dict and positional buffers

    :param entity_dict: The dictionary of the entity and its position used in
    the update
    :type entity_dict: :class:`PositionalEntityDict`
    :param output_dict: The output dictionary
    :type output_dict: `dict`[`str`, :class:`NamedEntityDict`]
    :param people_entities_buffer: A buffer list of PERSON entites used to
    efficiently get locations within 100 words of the entity
    :type people_entities_buffer: `list`[:class:`PositionalEntityDict`]
    :param loc_entities_buffer: A buffer list of LOC entities used to
    efficiently get people within 100 words of the entity
    :type loc_entities_buffer: :class:`list`[:class:`PositionalEntityDict`]
    :param label: The label of the entity
    :type label: `Literal`["PERSON"] | `Literal`["LOC"]
    """
    if label == "PERSON":
        handle_person_entity_update(
            entity_dict=entity_dict,
            output_dict=output_dict,
            people_entities_buffer=people_entities_buffer,
            loc_entities_buffer=loc_entities_buffer,
        )
    else:
        handle_loc_entity_update(
            entity_dict=entity_dict,
            output_dict=output_dict,
            people_entities_buffer=people_entities_buffer,
            loc_entities_buffer=loc_entities_buffer,
        )


def handle_person_entity_update(
    entity_dict: PositionalEntityDict,
    output_dict: dict[str, NamedEntityDict],
    people_entities_buffer: list[PositionalEntityDict],
    loc_entities_buffer: list[PositionalEntityDict],
) -> None:
    """Handles the update of output dicts and buffers if the entity provided
    is a "PERSON"

    :param entity_dict: The dictionary of the entity and its position used in
    the update
    :type entity_dict: :class:`PositionalEntityDict`
    :param output_dict: The output dictionary
    :type output_dict: `dict`[`str`, :class:`NamedEntityDict`]
    :param people_entities_buffer: A buffer list of PERSON entites used to
    efficiently get locations within 100 words of the entity
    :type people_entities_buffer: `list`[:class:`PositionalEntityDict`]
    :param loc_entities_buffer: A buffer list of LOC entities used to
    efficiently get people within 100 words of the entity
    :type loc_entities_buffer: :class:`list`[:class:`PositionalEntityDict`]
    """
    people_entities_buffer.append(entity_dict)
    name = entity_dict["name"]
    if name not in output_dict:
        output_dict[name] = NamedEntityDict(name=name, count=0, locations={})
    output_dict[name]["count"] += 1
    locations = output_dict[name]["locations"]
    for i, loc in enumerate(reversed(loc_entities_buffer)):
        handle_positional_entity_buffer(
            loc_entities_buffer,
            loc["end"],
            entity_dict["start"],
            iteration=i,
            max_range=100,
        )
        update_locations(locations, loc["name"])


def handle_loc_entity_update(
    entity_dict: PositionalEntityDict,
    output_dict: dict[str, NamedEntityDict],
    people_entities_buffer: list[PositionalEntityDict],
    loc_entities_buffer: list[PositionalEntityDict],
) -> None:
    """Handles the update of output dicts and buffers if the entity provided
    is a "LOC"

    :param entity_dict: The dictionary of the entity and its position used in
    the update
    :type entity_dict: :class:`PositionalEntityDict`
    :param output_dict: The output dictionary
    :type output_dict: `dict`[`str`, :class:`NamedEntityDict`]
    :param people_entities_buffer: A buffer list of PERSON entites used to
    efficiently get locations within 100 words of the entity
    :type people_entities_buffer: `list`[:class:`PositionalEntityDict`]
    :param loc_entities_buffer: A buffer list of LOC entities used to
    efficiently get people within 100 words of the entity
    :type loc_entities_buffer: :class:`list`[:class:`PositionalEntityDict`]
    """
    loc_entities_buffer.append(entity_dict)
    for i, person in enumerate(reversed(people_entities_buffer)):
        if handle_positional_entity_buffer(
            people_entities_buffer,
            person["end"],
            entity_dict["start"],
            iteration=i,
            max_range=100,
        ):
            break
        locations = output_dict[person["name"]]["locations"]
        update_locations(locations, entity_dict["name"])


def handle_positional_entity_buffer(
    positional_entity_buffer: list[PositionalEntityDict],
    end: int,
    start: int,
    iteration: int,
    max_range: int,
) -> bool:
    """Method to produce a boolean indicating if the word distance between a
    named entity in the buffer at a given iteration location is outside the
    max range given or not. If it is outside the range the buffer is reduced
    up to that iteration id backwards from the end of the buffer.

    :param positional_entity_buffer: The buffer of positional entities
    :type positional_entity_buffer: `list`[:class:`PositionalEntityDict`]
    :param end: The end word position of the entity in the buffer
    :type end: `int`
    :param start: The start word position of the entity that the distance is
    being compared against in the buffer
    :type start: `int`
    :param iteration: The iteration number for the entity used in the buffer
    in the reversed buffer list
    :type iteration: `int`
    :param max_range: The maximum range the entities can be apart
    :type max_range: `int`
    :return: Returns the boolean indicating if the entities are outside the
    range of one another
    :rtype: bool
    """
    is_outside_max_range = abs(end - start) > max_range
    if is_outside_max_range:
        positional_entity_buffer[len(positional_entity_buffer) - iteration:]
    return is_outside_max_range


def update_locations(
    locations: dict[str, NamedEntityDict], location_name: str
) -> None:
    """Method to update the locations dictionary with the location and its
    count

    :param locations: The dictionary of locations
    :type locations: `dict`[`str`, :class:`NamedEntityDict`]
    :param location_name: The name of the location
    :type location_name: `str`
    """
    if location_name not in locations:
        locations[location_name] = NamedEntityDict(name=location_name, count=0)
    locations[location_name]["count"] += 1


if __name__ == "__main__":
    flask_app = create_app()
    flask_app.run()
