"""Unified Ecommerce utilities"""

import base64
import json
import logging
import os
from enum import Flag, auto
from typing import Union
from urllib.parse import quote_plus

import markdown2
from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.http import HttpResponseRedirect
from mitol.common.utils.datetime import now_in_utc

from unified_ecommerce.constants import USER_MSG_COOKIE_MAX_AGE, USER_MSG_COOKIE_NAME

log = logging.getLogger(__name__)

# This is the Django ImageField max path size
IMAGE_PATH_MAX_LENGTH = 100

User = get_user_model()


class FeatureFlag(Flag):
    """
    FeatureFlag enum

    Members should have values of increasing powers of 2 (1, 2, 4, 8, ...)

    """

    EXAMPLE_FEATURE = auto()


def normalize_to_start_of_day(dt):
    """
    Normalizes a datetime value to the start of it's day

    Args:
        dt (datetime.datetime): the datetime to normalize

    Returns:
        datetime.datetime: the normalized datetime
    """  # noqa: D401
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def merge_strings(list_or_str):
    """
    Recursively go through through nested lists of strings and merge into a flattened list.

    Args:
        list_or_str (any): A list of strings or a string

    Returns:
        list of str: A list of strings
    """  # noqa: E501

    list_to_return = []
    _merge_strings(list_or_str, list_to_return)
    return list_to_return


def _merge_strings(list_or_str, list_to_return):
    """
    Recursively go through through nested lists of strings and merge into a flattened list.

    Args:
        list_or_str (any): A list of strings or a string
        list_to_return (list of str): The list the strings will be added to
    """  # noqa: E501
    if isinstance(list_or_str, list):
        for item in list_or_str:
            _merge_strings(item, list_to_return)
    elif list_or_str is not None:
        list_to_return.append(list_or_str)


def filter_dict_keys(orig_dict, keys_to_keep, *, optional=False):
    """
    Returns a copy of a dictionary filtered by a collection of keys to keep

    Args:
        orig_dict (dict): A dictionary
        keys_to_keep (iterable): Keys to filter on
        optional (bool): If True, ignore keys that don't exist in the dict. If False, raise a KeyError.
    """  # noqa: D401, E501
    return {
        key: orig_dict[key] for key in keys_to_keep if not optional or key in orig_dict
    }


def filter_dict_with_renamed_keys(orig_dict, key_rename_dict, *, optional=False):
    """
    Returns a copy of a dictionary with keys renamed according to a provided dictionary

    Args:
        orig_dict (dict): A dictionary
        key_rename_dict (dict): Mapping of old key to new key
        optional (bool): If True, ignore keys that don't exist in the dict. If False, raise a KeyError.
    """  # noqa: D401, E501
    return {
        new_key: orig_dict[key]
        for key, new_key in key_rename_dict.items()
        if not optional or key in orig_dict
    }


def html_to_plain_text(html_str):
    """
    Takes an HTML string and returns text with HTML tags removed and line breaks replaced with spaces

    Args:
        html_str (str): A string containing HTML tags

    Returns:
        str: Plain text
    """  # noqa: D401, E501
    soup = BeautifulSoup(html_str, features="html.parser")
    return soup.get_text().replace("\n", " ")


def markdown_to_plain_text(markdown_str):
    """
    Takes a string and returns text with Markdown elements removed and line breaks
    replaced with spaces

    Args:
        markdown_str (str): A string containing Markdown

    Returns:
        str: Plain text
    """  # noqa: D401
    html_str = markdown2.markdown(markdown_str)
    return html_to_plain_text(html_str).strip()


def prefetched_iterator(query, chunk_size=2000):
    """
    This is a prefetch_related-safe version of what iterator() should do.
    It will sort and batch on the default django primary key

    Args:
        query (QuerySet): the django queryset to iterate
        chunk_size (int): the size of each chunk to fetch

    """  # noqa: D401
    # walk the records in ascending id order
    base_query = query.order_by("id")

    def _next(greater_than_id):
        """Returns the next batch"""  # noqa: D401
        return base_query.filter(id__gt=greater_than_id)[:chunk_size]

    batch = _next(0)

    while batch:
        item = None
        # evaluate each batch query here
        for item in batch:
            yield item

        # next batch starts after the last item.id
        batch = _next(item.id) if item is not None else None


def generate_filepath(filename, directory_name, suffix, prefix):
    """
    Generate and return the filepath for an uploaded image

    Args:
        filename(str): The name of the image file
        directory_name (str): A directory name
        suffix(str): 'small', 'medium', or ''
        prefix (str): A directory name to use as a prefix

    Returns:
        str: The filepath for the uploaded image.
    """
    name, ext = os.path.splitext(filename)  # noqa: PTH122
    timestamp = now_in_utc().replace(microsecond=0)
    path_format = "{prefix}/{directory_name}/{name}-{timestamp}{suffix}{ext}"

    path_without_name = path_format.format(
        timestamp=timestamp.strftime("%Y-%m-%dT%H%M%S"),
        prefix=prefix,
        directory_name=directory_name,
        suffix=suffix,
        ext=ext,
        name="",
    )
    if len(path_without_name) >= IMAGE_PATH_MAX_LENGTH:
        msg = f"path is longer than max length even without name: {path_without_name}"
        raise ValueError(msg)

    max_name_length = IMAGE_PATH_MAX_LENGTH - len(path_without_name)
    return path_format.format(
        name=name[:max_name_length],
        timestamp=timestamp.strftime("%Y-%m-%dT%H%M%S"),
        prefix=prefix,
        directory_name=directory_name,
        suffix=suffix,
        ext=ext,
    )


def extract_values(obj, key):
    """
    Pull all values of specified key from nested JSON.

    Args:
        obj(dict): The JSON object
        key(str): The JSON key to search for and extract

    Returns:
        list of matching key values

    """
    array = []

    def extract(obj, array, key):
        """Recursively search for values of key in JSON tree."""
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == key:
                    array.append(v)
                if isinstance(v, dict | list):
                    extract(v, array, key)
        elif isinstance(obj, list):
            for item in obj:
                extract(item, array, key)
        return array

    return extract(obj, array, key)


def write_to_file(filename, contents):
    """
    Write content to a file in binary mode, creating directories if necessary

    Args:
        filename (str): The full-path filename to write to.
        contents (bytes): What to write to the file.

    """
    if not os.path.exists(os.path.dirname(filename)):  # noqa: PTH110, PTH120
        os.makedirs(os.path.dirname(filename))  # noqa: PTH103, PTH120
    if os.path.exists(filename):  # noqa: PTH110
        with open(filename, "rb") as infile:  # noqa: PTH123
            if infile.read() == contents:
                return
    with open(filename, "wb") as infile:  # noqa: PTH123
        infile.write(contents)


def write_x509_files():
    """Write the x509 certificate and key to files"""
    write_to_file(settings.MIT_WS_CERTIFICATE_FILE, settings.MIT_WS_CERTIFICATE)
    write_to_file(settings.MIT_WS_PRIVATE_KEY_FILE, settings.MIT_WS_PRIVATE_KEY)


class SoftDeleteActiveModel(models.Model):
    """Provides a truthy is_active field for soft-deletable models"""

    class Meta:
        """Meta options for SoftDeleteActiveModel"""

        abstract = True

    @property
    def is_active(self):
        """Return True if the object is active, False otherwise."""

        return self.deleted_on is None


CookieValue = Union[dict, list, str, None]


def encode_json_cookie_value(cookie_value: CookieValue) -> str:
    """
    Encode a JSON-compatible value to be set as the value of a cookie, which
    can then be decoded to get the original JSON value.
    """
    json_str_value = json.dumps(cookie_value)
    return quote_plus(json_str_value.replace(" ", "%20"))


def redirect_with_user_message(
    redirect_uri: str, cookie_value: CookieValue
) -> HttpResponseRedirect:
    """
    Create a redirect response with a user message

    Args:
        redirect_uri (str): the uri to redirect to
        cookie_value (CookieValue): the object to serialize into the cookie
    """
    resp = HttpResponseRedirect(redirect_uri)
    resp.set_cookie(
        key=USER_MSG_COOKIE_NAME,
        value=encode_json_cookie_value(cookie_value),
        max_age=USER_MSG_COOKIE_MAX_AGE,
    )
    return resp


def decode_x_header(request, header):
    """
    Decode an 'X-' header.

    For things that put some JSON-encoded data in a HTTP header, this will both
    base64 decode it and then JSON decode it, and return the resulting dict.
    (This is used for the APISIX code - it puts user data in X-User-Info in
    this format.)

    Args:
        request (HttpRequest): the HTTP request
        header (str): the name of the header to decode
    """
    x_userinfo = request.META.get(header, False)

    if not x_userinfo:
        return None

    decoded_x_userinfo = base64.b64decode(x_userinfo)
    return json.loads(decoded_x_userinfo)
