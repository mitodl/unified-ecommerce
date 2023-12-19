"""Testing utils"""

import abc
import json
import traceback
from contextlib import contextmanager
from unittest.mock import Mock

import pytest
from django.core.serializers import serialize
from django.core.serializers.json import DjangoJSONEncoder
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


def assert_json_equal(obj1, obj2, sort=False, **kwargs):  # noqa: FBT002
    """
    Asserts that two objects are equal after a round trip through JSON serialization/deserialization.
    Particularly helpful when testing DRF serializers where you may get back OrderedDict and other such objects.

    Args:
        obj1 (object): the first object
        obj2 (object): the second object
        sort (bool): If true, sort items which are iterable before comparing

    Keyword Args:
        ignore_timestamps: If true, ignore timestamps in the comparison
    """  # noqa: D401
    renderer = JSONRenderer()
    converted1 = json.loads(renderer.render(obj1))
    converted2 = json.loads(renderer.render(obj2))

    if kwargs.get("ignore_timestamps"):
        converted1.pop("created_on", None)
        converted1.pop("updated_on", None)
        converted2.pop("created_on", None)
        converted2.pop("updated_on", None)

    if sort:
        converted1 = _sort_values_for_testing(converted1)
        converted2 = _sort_values_for_testing(converted2)
    assert converted1 == converted2


class PickleableMock(Mock):
    """
    A Mock that can be passed to pickle.dumps()

    Source: https://github.com/testing-cabal/mock/issues/139#issuecomment-122128815
    """

    def __reduce__(self):
        """Required method for being pickleable"""  # noqa: D401
        return (Mock, ())


class BaseSerializerTest:
    """Base class for serializer tests."""

    model_class = None
    serializer_class = None
    factory_class = None
    queryset = None

    def test_serialize(self):
        """Test that the serializer can serialize an instance."""
        instance = self.factory_class()

        if self.queryset:
            instance_qs = self.queryset.filter(pk=instance.pk)
        else:
            instance_qs = self.model_class.objects.filter(pk=instance.pk)

        serializer = self.serializer_class(instance)
        dj_serializer = queryset_to_json(instance_qs)

        assert_json_equal(serializer.data, dj_serializer, ignore_timestamps=True)


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
            pytest.skip(exception_string)

        response = api_client.get(url)
        assert response.status_code == 403 if kwargs["test_non_authenticated"] else 200
        return response

    def test_get_queryset(self):
        """Test that the viewset returns the correct queryset."""
        queryset = self.viewset_class().get_queryset()
        assert queryset.count() == self.queryset.count()

    def test_get_serializer_class(self):
        """Test that the viewset returns the correct serializer class."""
        serializer_class = self.viewset_class().get_serializer_class()
        assert serializer_class == self.viewset_class.serializer_class

    @pytest.mark.parametrize("isLoggedIn", [True, False])
    def test_list(self, isLoggedIn, client, user_client):
        """
        Test that the viewset can list objects.

        Args:
        - isLoggedIn (bool): whether or not the client is logged in
        - client (APIClient): the client to use for non-logged in requests
        - user_client (APIClient): the client to use for logged in requests
        """

        response = self._test_retrieval(
            user_client if isLoggedIn else client,
            self.list_url,
            "list_url",
            test_non_authenticated=not isLoggedIn,
        )

        if isLoggedIn:
            assert len(response.data) == self.queryset.count()

    @pytest.mark.parametrize("isLoggedIn", [True, False])
    def test_retrieve(self, isLoggedIn, client, user_client):
        """
        Test that the viewset can retrieve an object.

        Args:
        - isLoggedIn (bool): whether or not the client is logged in
        - client (APIClient): the client to use for non-logged in requests
        - user_client (APIClient): the client to use for logged in requests
        """
        instance = self.factory_class()
        instance_qs = self.queryset.filter(pk=instance.pk)

        response = self._test_retrieval(
            user_client if isLoggedIn else client,
            self.object_url.format(instance.pk),
            "object_url",
            test_non_authenticated=not isLoggedIn,
        )

        if isLoggedIn and instance.is_active:
            dj_serializer = queryset_to_json(instance_qs)
            assert_json_equal(response.data, dj_serializer, ignore_timestamps=True)

    def test_update(self, update_data, isLoggedIn, client, user_client):
        """
        Test that the viewset can update an object.

        Args:
        - update_data (dict): the data to use for the update
        - isLoggedIn (bool): whether or not the client is logged in
        - client (APIClient): the client to use for non-logged in requests
        - user_client (APIClient): the client to use for logged in requests

        Returns:
        - tuple of (instance, response): the instance that was updated and the response
        """
        instance = self.factory_class()

        use_client = user_client if isLoggedIn else client
        response = use_client.patch(
            self.object_url.format(instance.pk), data=update_data
        )

        if not isLoggedIn:
            assert response.status_code == 403
        return (instance, response)

    def test_delete(self, isLoggedIn, client, user_client):
        """
        Test that the viewset can delete an object. Note that this will actually test
        deletion.

        Args:
        - isLoggedIn (bool): whether or not the client is logged in
        - client (APIClient): the client to use for non-logged in requests
        - user_client (APIClient): the client to use for logged in requests

        Returns:
        - tuple of (instance, response): the instance that was deleted and the response
        """
        instance = self.factory_class()

        use_client = user_client if isLoggedIn else client
        response = use_client.delete(self.object_url.format(instance.pk))

        assert response.status_code == 403 if not isLoggedIn else 204

        if isLoggedIn:
            assert self.queryset.filter(pk=instance.pk).count() == 0

        return (instance, response)

    def test_create(self, create_data, isLoggedIn, client, user_client):
        """
        Test that the viewset can create an object.

        Args:
        - create_data (dict): the data to use for the update
        - isLoggedIn (bool): whether or not the client is logged in
        - client (APIClient): the client to use for non-logged in requests
        - user_client (APIClient): the client to use for logged in requests

        Returns:
        - response (Response): the response from the API
        """
        use_client = user_client if isLoggedIn else client
        response = use_client.post(self.list_url, data=create_data)

        if not isLoggedIn:
            assert response.status_code == 403
        return response
