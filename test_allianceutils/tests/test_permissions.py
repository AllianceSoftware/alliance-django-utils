from unittest.mock import MagicMock
from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.test import TestCase

from allianceutils.api.permissions import SimpleDjangoObjectPermissions


class PermissionTestCase(TestCase):
    def test_object_permission_when_user_has_global_permission(self):
        """
        Test SimpleDjangoObjectPermissions.has_object_permission() when the user
        has requested global permission
        """
        user = Mock()
        def has_perm(permission_required, obj=None):
            return obj is None
        user.has_perm = has_perm
        request = Mock()
        request.user = user
        view = Mock(spec=['permission_required'])
        obj = Mock()

        self.assertTrue(SimpleDjangoObjectPermissions().has_object_permission(request, view, obj))

    def test_object_permission_when_user_has_object_permission(self):
        """
        Test SimpleDjangoObjectPermissions.has_object_permission() when the user
        has requested permission against a supplied object
        """
        user = Mock()
        def has_perm(permission_required, obj=None):
            return obj is not None
        user.has_perm = has_perm
        request = Mock()
        request.user = user
        view = Mock(spec=['permission_required'])
        obj = Mock()

        self.assertTrue(SimpleDjangoObjectPermissions().has_object_permission(request, view, obj))

    def test_object_permission_when_user_has_both_global_permission_and_object_permission_should_fail_assertion(self):
        """
        Ensure that the assert fails if a global permission and object permission are both
        """
        user = Mock()
        user.has_perm.return_value = True
        request = Mock()
        request.user = user
        view = Mock(spec=['permission_required'])
        obj = Mock()

        with self.assertRaises(AssertionError):
            SimpleDjangoObjectPermissions().has_object_permission(request, view, obj)