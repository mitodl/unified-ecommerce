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
from django.urls.conf import URLPattern, URLResolver
from mitol.common.utils.datetime import now_in_utc

from unified_ecommerce.constants import USER_MSG_COOKIE_MAX_AGE, USER_MSG_COOKIE_NAME
from users.models import UserProfile

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
    Returns:
    dict of decoded values, or None if the header isn't found
    """
    x_userinfo = request.META.get(header, False)

    if not x_userinfo:
        return None

    decoded_x_userinfo = base64.b64decode(x_userinfo)
    return json.loads(decoded_x_userinfo)


def decode_apisix_headers(request, model="auth_user"):
    """
    Decode the APISIX-specific headers.

    APISIX delivers user information via the X-User-Info header that it
    attaches to the request. This data can contain an arbitrary amount of
    information, so this returns just the data that we care about, normalized
    into a structure we expect (or rather ones that match Django objects).

    This mapping can be adjusted by changing the APISIX_USERDATA_MAP setting.
    This is a nested dict: the top level is the model that the mapping belongs
    to, and it is set to a dict of the mappings of model field names to APISIX
    field names. Model names are in app_model form (like the table name).

    Args:
    - request (Request): the current HTTP request object
    - model (string): the model data to retrieve (defaults to "auth_user")

    Returns: dict of applicable data or None if no data
    """

    if model not in settings.APISIX_USERDATA_MAP:
        error = "Model %s is invalid"
        raise ValueError(error, model)

    data_mapping = settings.APISIX_USERDATA_MAP[model]

    try:
        apisix_result = decode_x_header(request, "HTTP_X_USERINFO")
        if not apisix_result:
            log.debug(
                "decode_apisix_headers: No APISIX-specific header found",
            )
            return None
    except json.JSONDecodeError:
        log.debug(
            "decode_apisix_headers: Got bad APISIX-specific header: %s",
            request.META.get("HTTP_X_USERINFO", ""),
        )

        return None

    log.debug("decode_apisix_headers: Got %s", apisix_result)

    return {
        modelKey: apisix_result[data_mapping[modelKey]]
        for modelKey in data_mapping
        if data_mapping[modelKey] in apisix_result
    }


def get_user_from_apisix_headers(request):
    """Get a user based on the APISIX headers."""

    decoded_headers = decode_apisix_headers(request)

    if not decoded_headers:
        return None

    log.debug("decoded headers: %s", decoded_headers)

    email = decoded_headers.get("email", None)
    global_id = decoded_headers.get("global_id", None)
    username = decoded_headers.get("username", None)
    given_name = decoded_headers.get("given_name", None)
    family_name = decoded_headers.get("family_name", None)
    name = decoded_headers.get("name", None)

    log.debug("get_user_from_apisix_headers: Authenticating %s", global_id)

    user, created = User.objects.update_or_create(
        global_id=global_id,
        defaults={
            "global_id": global_id,
            "username": username,
            "email": email,
            "first_name": given_name,
            "last_name": family_name,
            "name": name,
        },
    )

    if created:
        log.debug(
            "get_user_from_apisix_headers: User %s not found, created new",
            global_id,
        )
        user.set_unusable_password()
        user.is_active = True
        user.save()
    else:
        log.debug(
            "get_user_from_apisix_headers: Found existing user for %s: %s",
            global_id,
            user,
        )

        if not user.is_active:
            log.debug(
                "get_user_from_apisix_headers: User %s is inactive",
                global_id,
            )
            msg = "User is inactive"
            raise KeyError(msg)

    profile_data = decode_apisix_headers(request, "authentication_userprofile")

    if profile_data:
        log.debug(
            "get_user_from_apisix_headers: Setting up additional profile for %s",
            global_id,
        )

        _, profile = UserProfile.objects.filter(user=user).get_or_create(
            defaults=profile_data
        )
        profile.save()
        user.refresh_from_db()

    return user


def parse_readable_id(readable_id: str) -> tuple[str, str]:
    """
    Parse a readable ID into a resource ID and a run ID.

    Readable IDs look like "course-v1:MITxT+12.345x" but they may also have a run
    tacked onto the end ("+1T2024" for instance). If the readable ID isn't for a
    run of the resource, you'll get a None in the run position.

    Args:
        readable_id (str): The readable ID to parse

    Returns:
        tuple[str, str]: The resource ID and the run ID (or None)
    """
    if readable_id.count("+") > 1:
        resource, run = readable_id.rsplit("+", 1)
    else:
        resource = readable_id
        run = None

    return resource, run


# This is a temporary add - getting this into mitol-django-common is in progress
# Adding it manually here so we can have the prefixed URLs work in CI/QA now
def prefix_url_patterns(
    urlpatterns: list[URLPattern],
) -> Union[tuple[URLResolver], list[URLPattern]]:
    """Add a prefix to all current app urlpatterns"""
    from django.urls import include, path

    if settings.MITOL_APP_PATH_PREFIX:
        return (
            path(
                f"{settings.MITOL_APP_PATH_PREFIX.rstrip('/')}/", include(urlpatterns)
            ),
        )
    return urlpatterns
