"""Testing utils"""

import abc
import datetime
import json
import traceback
from contextlib import contextmanager
from unittest.mock import Mock

import pytest
import pytz
from deepdiff import DeepDiff
from django.conf import settings
from django.core.serializers import serialize
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpRequest
from django.http.response import HttpResponse
from rest_framework.renderers import JSONRenderer


def any_instance_of(*classes):
    """
    Returns a type that evaluates __eq__ in isinstance terms

    Args:
        classes (list of types): variable list of types to ensure equality against

    Returns:
        AnyInstanceOf: dynamic class type with the desired equality
    """  # noqa: D401

    class AnyInstanceOf(abc.ABC):  # noqa: B024
        """Dynamic class type for __eq__ in terms of isinstance"""

        def __init__(self, classes):
            self.classes = classes

        def __eq__(self, other):
            return isinstance(other, self.classes)

        def __str__(self):  # pragma: no cover
            return f"AnyInstanceOf({', '.join([str(c) for c in self.classes])})"

        def __repr__(self):  # pragma: no cover
            return str(self)

    for c in classes:
        AnyInstanceOf.register(c)
    return AnyInstanceOf(classes)


@contextmanager
def assert_not_raises():
    """Used to assert that the context does not raise an exception"""  # noqa: D401
    try:
        yield
    except AssertionError:
        raise
    except Exception:  # pylint: disable=broad-except  # noqa: BLE001
        pytest.fail(f"An exception was not raised: {traceback.format_exc()}")


class MockResponse(HttpResponse):
    """
    Mocked HTTP response object that can be used as a stand-in for request.Response and
    django.http.response.HttpResponse objects
    """

    def __init__(self, content, status_code):
        """
        Args:
            content (str): The response content
            status_code (int): the response status code
        """
        self.status_code = status_code
        self.decoded_content = content
        super().__init__(content=(content or "").encode("utf-8"), status=status_code)

    def json(self):
        """Return content as json"""
        return json.loads(self.decoded_content)


def drf_datetime(dt):
    """
    Returns a datetime formatted as a DRF DateTimeField formats it

    Args:
        dt(datetime): datetime to format

    Returns:
        str: ISO 8601 formatted datetime
    """  # noqa: D401
    return dt.isoformat().replace("+00:00", "Z")


def _sort_values_for_testing(obj):
    """
    Sort an object recursively if possible to do so

    Args:
        obj (any): A dict, list, or some other JSON type

    Returns:
        any: A sorted version of the object passed in, or the same object if no sorting can be done
    """
    if isinstance(obj, dict):
        return {key: _sort_values_for_testing(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        items = [_sort_values_for_testing(value) for value in obj]
        # this will produce incorrect results since everything is converted to a string
        # for example [10, 9] will be sorted like that
        # but here we only care that the items are compared in a consistent way so tests pass
        return sorted(items, key=json.dumps)
    else:
        return obj


def queryset_to_json(queryset):
    """
    Convert a queryset to JSON using the Django JSON serializer.

    The Django JSON serializer renders some things (notably Decimal) as strings, which is
    useful for testing with assert_json_equal. This does some reformatting of the serialized
    object as well as the serializer includes some extra info and doesn't put the primary
    key in the right spot for our purposes.

    The queryset should be for the individual item that we're looking for. If there's more
    than one, this will throw an exception. (If there's zero, it'll return an empty dict.)

    Args:
    - queryset (QuerySet): the queryset to serialize

    Returns:
    - dict of the fields in the retrieved model object (plus the PK) in a JSON-friendly format

    Raises:
    - AssertionError: if there's more than one object in the queryset
    """
    dj_serializer = serialize("json", queryset, cls=DjangoJSONEncoder)
    dj_serializer = json.loads(dj_serializer)

    if len(dj_serializer) < 1:
        return []

    if len(dj_serializer) > 1:
        exception_string = "queryset_to_json only works for single objects"
        raise AssertionError(exception_string)

    dj_serializer[0]["fields"]["id"] = dj_serializer[0]["pk"]
    return dj_serializer[0]["fields"]


def assert_json_equal(obj1, obj2, ignore_order=False):  # noqa: FBT002
    """
    Assert that two objects are equal after a round trip through JSON
    serialization/deserialization. Particularly helpful when testing DRF serializers
    where you may get back OrderedDict and other such objects.

    Args:
        obj1 (object): the first object
        obj2 (object): the second object
        ignore_order (bool): Boolean to ignore the order in the result
    """
    json_renderer = JSONRenderer()
    converted1 = json.loads(json_renderer.render(obj1))
    converted2 = json.loads(json_renderer.render(obj2))
    if ignore_order:
        assert DeepDiff(converted1, converted2, ignore_order=ignore_order) == {}
    else:
        assert converted1 == converted2


def make_timestamps_matchable(objs, **kwargs):
    """
    Convert the standard timestamp datetimes that are usually in a model object to
    a set equivalent, so the object can be compared to another more easily. For
    a TimestampedModel, this is created_on and updated_on. Optionally, you can specify
    the fields to set, or skip the standard timestamp fields.

    This generates an aware timestamp at the start, which is used for all the dicts
    that have been passed in.

    Args:
    - objs (list of dict): the objects to modify

    Keyword Args:
    - fields (list): additional fields to convert
    - skip_timestamps (bool): skip the regular timestamps (so, just what you specify in
      fields)

    Returns:
    - list of dict: the passed in dicts, with the created_on and updated_on timestamps
      converted to anys equivalents
    """

    time_data = datetime.datetime.now(tz=pytz.timezone(settings.TIME_ZONE))
    fields = kwargs.get("fields", [])

    if not kwargs.get("skip_timestamps", False):
        fields = [*fields, "created_on", "updated_on", "deleted_on"]

    timestamps = {}

    for field in fields:
        timestamps[field] = time_data

    return [
        {
            **obj,
            **timestamps,
        }
        for obj in objs
    ]


def generate_mocked_request(user):
    """
    Generate a mocked request for test_process_cybersource_*.

    The RequestFactory misses some stuff, so instead just make a full-fat
    HttpRequest and add the things in that we need.

    Args:
    - user (User): The user to set in the request.

    Returns:
    - HttpRequest: The mocked request.
    """
    mocked_request = HttpRequest()
    mocked_request.user = user
    mocked_request.META["REMOTE_ADDR"] = "127.0.0.1"
    mocked_request.META["HTTP_HOST"] = "localhost"

    return mocked_request


class PickleableMock(Mock):
    """
    A Mock that can be passed to pickle.dumps()

    Source: https://github.com/testing-cabal/mock/issues/139#issuecomment-122128815
    """

    def __reduce__(self):
        """Required method for being pickleable"""  # noqa: D401
        return (Mock, ())


class ViewSetNotConfiguredError(Exception):
    """
    Raised when a viewset is not configured correctly.
    """


class BaseSerializerTest:
    """
    Base class for serializer tests.

    Class variables:
    - model_class (class): the model class to test
    - serializer_class (class): the serializer class to test
    - factory_class (class): the factory class to use for creating instances
    - queryset (QuerySet): the queryset to use, if you need a custom one
    - only_fields (list): a list of field names that should be included in the serialized output
    """

    model_class = None
    serializer_class = None
    factory_class = None
    queryset = None
    only_fields = None

    def test_serialize(self):
        """Test that the serializer can serialize an instance."""
        instance = self.factory_class()

        if self.queryset:
            instance_qs = self.queryset.filter(pk=instance.pk)
        else:
            instance_qs = self.model_class.objects.filter(pk=instance.pk)

        serializer = self.serializer_class(instance)

        if self.only_fields:
            dj_serializer = instance_qs.values(*self.only_fields).get()
        else:
            dj_serializer = queryset_to_json(instance_qs)

        assert_json_equal(*make_timestamps_matchable([serializer.data, dj_serializer]))


class BaseViewSetTest:
    """
    Base class for viewset tests.

    Set viewset_class, factory_class and queryset to the appropriate values for your
    viewset. `list_url` should be the root URL for the list view, and the `object_url` should
    be contain a format string for individual objects in the viewset. DRF convention is that
    the URLs remains the same but will get used with different HTTP verbs according
    to the test being run (i.e. update sends a PATCH, etc.).

    The tests that perform writes to the dataset require subclassing. They're more
    abstractions of the HTTP request than an actual test; you'll need to provide some
    logic for the test to check the operation succeeded with the model you're using.
    """

    viewset_class = None
    factory_class = None
    queryset = None

    # URLs for these actions
    list_url = None
    object_url = None

    def _test_retrieval(self, api_client, url, url_name, **kwargs):
        """
        Test that hitting the specified URL works with the specified client.

        You still need to test for the proper response code; this will just
        check for 500s and 403.

        Args:
        - api_client (APIClient): the client to use
        - url (str): the URL to test with
        - url_name (str): the name of the URL (used for the skip message if it's not defined)

        Keyword Args:
        - test_non_authenticated (bool): whether or not this should expect a 403

        Returns:
        - response (Response): the response from the API
        """
        if not url:
            exception_string = f"{url_name} is not defined"
            raise ViewSetNotConfiguredError(exception_string)

        response = api_client.get(url)
        assert response.status_code < 500
        if kwargs["test_non_authenticated"]:
            assert response.status_code == 403
        return response

    def test_get_queryset(self):
        """Test that the viewset returns the correct queryset."""
        queryset = self.viewset_class().get_queryset()
        assert queryset.count() == self.queryset.count()

    def test_get_serializer_class(self):
        """Test that the viewset returns the correct serializer class."""
        serializer_class = self.viewset_class().get_serializer_class()
        assert serializer_class == self.viewset_class.serializer_class

    @pytest.mark.parametrize("is_logged_in", [True, False])
    def test_list(self, is_logged_in, client, user_client):
        """
        Test that the viewset can list objects.

        Args:
        - is_logged_in (bool): whether or not the client is logged in
        - client (APIClient): the client to use for non-logged in requests
        - user_client (APIClient): the client to use for logged in requests
        """

        response = self._test_retrieval(
            user_client if is_logged_in else client,
            self.list_url,
            "list_url",
            test_non_authenticated=not is_logged_in,
        )

        if is_logged_in:
            assert "count" in response.data
            assert response.data["count"] == self.queryset.count()

    @pytest.mark.parametrize("is_logged_in", [True, False])
    def test_retrieve(self, is_logged_in, client, user_client):
        """
        Test that the viewset can retrieve an object.

        Args:
        - is_logged_in (bool): whether or not the client is logged in
        - client (APIClient): the client to use for non-logged in requests
        - user_client (APIClient): the client to use for logged in requests
        """
        instance = self.factory_class()
        instance_qs = self.queryset.filter(pk=instance.pk)

        response = self._test_retrieval(
            user_client if is_logged_in else client,
            self.object_url.format(instance.pk),
            "object_url",
            test_non_authenticated=not is_logged_in,
        )

        if is_logged_in and instance.is_active:
            dj_serializer = queryset_to_json(instance_qs)
            assert_json_equal(
                *make_timestamps_matchable([response.data, dj_serializer])
            )

        if is_logged_in and not instance.is_active:
            # Deleted items should return a 404.
            assert response.status_code == 404

    def test_update(self, update_data, is_logged_in, client, user_client):
        """
        Test that the viewset can update an object.

        Args:
        - update_data (dict): the data to use for the update
        - is_logged_in (bool): whether or not the client is logged in
        - client (APIClient): the client to use for non-logged in requests
        - user_client (APIClient): the client to use for logged in requests

        Returns:
        - tuple of (instance, response): the instance that was updated and the response
        """
        instance = self.factory_class()

        use_client = user_client if is_logged_in else client
        response = use_client.patch(
            self.object_url.format(instance.pk), data=update_data
        )

        assert response.status_code < 500

        if not is_logged_in:
            assert response.status_code == 403

        return (instance, response)

    def test_delete(self, is_logged_in, client, user_client):
        """
        Test that the viewset can delete an object. Note that this will actually test
        deletion.

        Args:
        - is_logged_in (bool): whether or not the client is logged in
        - client (APIClient): the client to use for non-logged in requests
        - user_client (APIClient): the client to use for logged in requests

        Returns:
        - tuple of (instance, response): the instance that was deleted and the response
        """
        instance = self.factory_class()

        before_count = self.queryset.count()

        use_client = user_client if is_logged_in else client
        response = use_client.delete(self.object_url.format(instance.pk))

        assert response.status_code < 500
        assert response.status_code == 403 if not is_logged_in else 204

        assert (
            self.queryset.count() == before_count - 1 if is_logged_in else before_count
        )

        return (instance, response)

    def test_create(self, create_data, is_logged_in, client, user_client):
        """
        Test that the viewset can create an object.

        Args:
        - create_data (dict): the data to use for the update
        - is_logged_in (bool): whether or not the client is logged in
        - client (APIClient): the client to use for non-logged in requests
        - user_client (APIClient): the client to use for logged in requests

        Returns:
        - response (Response): the response from the API
        """
        use_client = user_client if is_logged_in else client
        response = use_client.post(self.list_url, data=create_data)

        assert response.status_code < 500

        if not is_logged_in:
            assert response.status_code == 403

        return response


class AuthVariegatedModelViewSetTest(BaseViewSetTest):
    """
    Extends the BaseViewSetTest class to add support for auth variegated
    viewsets. These viewsets use different serializers based on the user's
    session.

    Set read_only_viewset_class and read_write_viewset_class to the appropriate
    values for your viewset.
    """

    read_only_serializer_class = None
    read_write_serializer_class = None

    @pytest.mark.parametrize("is_logged_in", [True, False])
    def test_get_serializer_class(self, is_logged_in, user):
        """Test the viewset returns the right serializer class."""

        viewset = self.viewset_class()

        if is_logged_in:
            # Forcing staff/superuser to get the read-write serializer.
            user.is_staff = True
            user.is_superuser = True
            viewset.request = generate_mocked_request(user)
            assert viewset.get_serializer_class() == self.read_write_serializer_class
        else:
            assert viewset.get_serializer_class() == self.read_only_serializer_class

    def _test_retrieval(self, api_client, url, url_name, **kwargs):  # noqa: ARG002
        """
        Test that hitting the specified URL works with the specified client.
        This will expect a 200 regardless of what you're requesting as you'll
        get a different result set and not a denial for these viewsets.

        noqa ARG002 so the API matches the parent class.

        Args:
        - api_client (APIClient): the client to use
        - url (str): the URL to test with
        - url_name (str): the name of the URL (used for the skip message if it's not defined)

        Keyword Args:
        - test_non_authenticated (bool): whether or not this should expect a 403

        Returns:
        - response (Response): the response from the API
        """
        if not url:
            exception_string = f"{url_name} is not defined"
            raise ViewSetNotConfiguredError(exception_string)

        response = api_client.get(url)
        assert response.status_code < 500
        return response

    def _determine_client_wrapper(  # noqa: PLR0913
        self, is_logged_in, use_staff_user, client, user_client, staff_client
    ):
        """
        Determine the client to use for the test.

        Args:
        - is_logged_in (bool): whether or not the client is logged in
        - use_staff_user (bool): use the staff user client, rather than the regular user client
        - client (APIClient): the client to use for non-logged in requests
        - user_client (APIClient): the client to use for logged in regular user requests
        - staff_client (APIClient): the client to use for staff user requests

        Returns:
        - client (APIClient): the client to use for the test
        """
        if is_logged_in:
            if use_staff_user:
                return staff_client
            else:
                return user_client
        else:
            return client

    @pytest.mark.parametrize(
        ("is_logged_in", "use_staff_user"),
        [(True, False), (True, True), (False, False)],
    )
    def test_retrieve(self, *args):
        """
        Test that the viewset can retrieve an object, and returns the correct
        dataset depending on the status of the user.

        If the user is anonymous _or_ a regular user, we should receive a
        dataset that matches the read-only serializer class. Otherwise, we
        should receive a dataset that matches the read-write serializer class.

        Args:
        - is_logged_in (bool): whether or not the client is logged in
        - use_staff_user (bool): use the staff user client, rather than the regular user client
        - client (APIClient): the client to use for non-logged in requests
        - user_client (APIClient): the client to use for logged in regular user requests
        - staff_client (APIClient): the client to use for staff user requests
        """
        instance = self.factory_class()

        is_logged_in = args[0]
        use_staff_user = args[1]

        use_client = self._determine_client_wrapper(*args)

        response = self._test_retrieval(
            use_client,
            self.object_url.format(instance.pk),
            "object_url",
        )

        if instance.is_active:
            if is_logged_in and use_staff_user:
                dj_serializer = self.read_write_serializer_class(instance).data
            else:
                dj_serializer = self.read_only_serializer_class(instance).data

            assert_json_equal(
                *make_timestamps_matchable([response.data, dj_serializer])
            )

        if not instance.is_active:
            # Deleted items should return a 404.
            assert response.status_code == 404

    @pytest.mark.parametrize(
        ("is_logged_in", "use_staff_user"),
        [(True, False), (True, True), (False, False)],
    )
    def test_update(self, update_data, *args):
        """
        Test that the viewset can update an object.

        Args:
        - update_data (dict): the data to use for the update
        - is_logged_in (bool): whether or not the client is logged in
        - use_staff_user (bool): use the staff user client, rather than the regular user client
        - client (APIClient): the client to use for non-logged in requests
        - user_client (APIClient): the client to use for logged in regular user requests
        - staff_client (APIClient): the client to use for staff user requests

        Returns:
        - tuple of (instance, response): the instance that was updated and the response
        """
        instance = self.factory_class()

        use_client = self._determine_client_wrapper(*args)

        is_logged_in = args[0]
        use_staff_user = args[1]

        response = use_client.patch(
            self.object_url.format(instance.pk), data=update_data
        )

        assert response.status_code < 500

        if not is_logged_in or not use_staff_user:
            assert response.status_code == 403

        return (instance, response)

    @pytest.mark.parametrize(
        ("is_logged_in", "use_staff_user"),
        [(True, False), (True, True), (False, False)],
    )
    def test_delete(self, *args):
        """
        Test that the viewset can delete an object. Note that this will actually test
        deletion.

        Args:
        - is_logged_in (bool): whether or not the client is logged in
        - use_staff_user (bool): use the staff user client, rather than the regular user client
        - client (APIClient): the client to use for non-logged in requests
        - user_client (APIClient): the client to use for logged in regular user requests
        - staff_client (APIClient): the client to use for staff user requests

        Returns:
        - tuple of (instance, response): the instance that was deleted and the response
        """
        instance = self.factory_class()

        before_count = self.queryset.count()

        use_client = self._determine_client_wrapper(*args)
        is_logged_in = args[0]
        use_staff_user = args[1]

        response = use_client.delete(self.object_url.format(instance.pk))

        assert response.status_code < 500
        assert (
            response.status_code == 403
            if not is_logged_in or not use_staff_user
            else 204
        )

        assert (
            self.queryset.count() == before_count - 1
            if is_logged_in and use_staff_user
            else before_count
        )

        return (instance, response)

    @pytest.mark.parametrize(
        ("is_logged_in", "use_staff_user"),
        [(True, False), (True, True), (False, False)],
    )
    def test_create(self, create_data, *args):
        """
        Test that the viewset can create an object.

        Args:
        - create_data (dict): the data to use for the update
        - is_logged_in (bool): whether or not the client is logged in
        - use_staff_user (bool): use the staff user client, rather than the regular user client
        - client (APIClient): the client to use for non-logged in requests
        - user_client (APIClient): the client to use for logged in regular user requests
        - staff_client (APIClient): the client to use for staff user requests

        Returns:
        - response (Response): the response from the API
        """
        use_client = self._determine_client_wrapper(*args)
        is_logged_in = args[0]
        use_staff_user = args[1]

        response = use_client.post(self.list_url, data=create_data)

        assert response.status_code < 500

        if not is_logged_in or not use_staff_user:
            assert response.status_code == 403

        return response
