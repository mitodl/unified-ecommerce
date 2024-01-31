"""Unified Ecommerce utilities"""

import logging
import os
from enum import Flag, auto

import markdown2
from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from mitol.common.utils.datetime import now_in_utc
from oauthlib.oauth2 import (
    BackendApplicationClient,
    InvalidGrantError,
    TokenExpiredError,
)
from requests_oauthlib import OAuth2Session

from authentication.models import KeycloakAdminToken
from unified_ecommerce.celery import app

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


def keycloak_get_user(user: User):
    """Get a user from Keycloak."""

    token_url = (
        f"{settings.KEYCLOAK_ADMIN_URL}/auth/realms/master/"
        "protocol/openid-connect/token"
    )
    userinfo_url = (
        f"{settings.KEYCLOAK_ADMIN_URL}/auth/admin/"
        f"realms/{settings.KEYCLOAK_ADMIN_REALM}/users/"
    )

    token = KeycloakAdminToken.latest()
    client = BackendApplicationClient(client_id=settings.KEYCLOAK_ADMIN_CLIENT_ID)

    auto_refresh_kwargs = {
        "client_id": settings.KEYCLOAK_ADMIN_CLIENT_ID,
        "client_secret": settings.KEYCLOAK_ADMIN_CLIENT_SECRET,
    }

    def update_token(token):
        log_str = f"Refreshing Keycloak token {token}"
        log.warning(log_str)
        KeycloakAdminToken.objects.all().delete()
        KeycloakAdminToken.objects.create(
            authorization_token=token.get("access_token"),
            refresh_token=token.get("refresh_token", None),
            authorization_token_expires_in=token.get("access_token_expires_in", 60),
            refresh_token_expires_in=token.get("refresh_token_expires_in", 60),
        )

    try:
        log_str = f"Trying to start up a session with token {token.token_formatted}"
        log.warning(log_str)

        session = OAuth2Session(
            client=client,
            token=token.token_formatted,
            auto_refresh_url=token_url,
            auto_refresh_kwargs=auto_refresh_kwargs,
            token_updater=update_token,
        )

        keycloak_info = session.get(
            userinfo_url, verify=False, params={"email": user.username}
        ).json()
    except (InvalidGrantError, TokenExpiredError) as ige:
        log_str = f"Token error, trying to get a new token: {ige}"
        log.warning(log_str)

        session = OAuth2Session(client=client)
        token = session.fetch_token(
            token_url=token_url,
            client_id=settings.KEYCLOAK_ADMIN_CLIENT_ID,
            client_secret=settings.KEYCLOAK_ADMIN_CLIENT_SECRET,
            verify=False,
        )

        update_token(token)
        session = OAuth2Session(client=client, token=token)
        keycloak_info = session.get(
            userinfo_url, verify=False, params={"email": user.username}
        ).json()

    log_str = f"Keycloak URL for userinfo is: {userinfo_url}"
    log.warning(log_str)

    log.warning("Keycloak info follows!")
    log.warning(keycloak_info)

    if len(keycloak_info) != 1:
        log.warning("Keycloak didn't return anything")
        return None

    return keycloak_info[0]


@app.task
def keycloak_update_user_account(user: int):
    """Update the user account using info from Keycloak asynchronously."""

    user = User.objects.get(id=user)

    keycloak_user = keycloak_get_user(user)

    if keycloak_user is None:
        return

    user.first_name = keycloak_user["firstName"]
    user.last_name = keycloak_user["lastName"]
    user.email = keycloak_user["email"]
    user.save()
