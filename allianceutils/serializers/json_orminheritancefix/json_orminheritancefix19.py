"""
JSON serializer with the following properties:
 - output is ordered (so revision control diffs are sane)
 - Fixes multi-table inheritance as per
    - https://code.djangoproject.com/ticket/24607
	    - Bug report
    - First patch: https://github.com/django/django/pull/4477/files
	    - Was accepted but then reverted due to creating spurious migrations
		- Rebased version: https://github.com/levic/django/tree/inheritance-natural-key
    - New patch: https://github.com/django/django/pull/8370/files
		- Due to internal meta changes, can only be applied with django>=1.9
    - This implementation checks the django version and uses two different patches to work with both <1.9 and >=1.9

To use, in your settings.py add:

SERIALIZATION_MODULES = {
    'json_orminheritancefix': 'allianceutils.serializers.json_orminheritancefix',
    'json': 'allianceutils.serializers.json_orminheritancefix',
}

- We have to override the built-in json because we want to deserialize .json files correctly
- There is no way to override django.core.serializers.python.Deserializer in part so this is a cut & paste
  of both the json & python deserializers with patches applied
"""
import json
import sys

import django
from django.apps import apps
from django.conf import settings
from django.core.serializers import base
from django.core.serializers.base import DeserializationError
from django.db import DEFAULT_DB_ALIAS
from django.db import models
from django.utils import six
from django.utils.encoding import force_text

import allianceutils.serializers.json_ordered

assert (1, 9) <= django.VERSION < (1, 12), 'json_orminheritancefix19 only works with django 1.9-1.11'

_NONE = object()


class Serializer(allianceutils.serializers.json_ordered.Serializer):
    def serialize(self, queryset, **options):
        options = options.copy()
        if options.get('use_natural_primary_keys', False):
            options['use_natural_foreign_keys'] = True

        return super(Serializer, self).serialize(queryset, **options)

    def get_dump_pk(self, obj, level):
        pk = obj._meta.pk
        if pk.remote_field:
            if self.use_natural_foreign_keys:
                return self.get_dump_pk(getattr(obj, pk.remote_field.field.name), level + 1)
            else:
                return force_text(obj.pk, strings_only=True)
        elif self.use_natural_primary_keys and hasattr(obj, "natural_key"):
            return _NONE if level == 0 else obj.natural_key()
        else:
            return force_text(obj.pk, strings_only=True)

    def get_dump_object(self, obj):
        data = super(Serializer, self).get_dump_object(obj)
        # overwrite default PK if necessary to handle where the PK is a FK
        pk = self.get_dump_pk(obj, 0)
        if pk is not _NONE:
            data["pk"] = pk
        data['fields'] = self._current
        return data


# No changes here except to use the PythonDeserializer function in this module
def Deserializer(stream_or_string, **options):
    """
    Deserialize a stream or string of JSON data.
    """
    if not isinstance(stream_or_string, (bytes, six.string_types)):
        stream_or_string = stream_or_string.read()
    if isinstance(stream_or_string, bytes):
        stream_or_string = stream_or_string.decode('utf-8')
    try:
        objects = json.loads(stream_or_string)
        for obj in _PythonDeserializer(objects, **options):
            yield obj
    except GeneratorExit:
        raise
    except Exception as e:
        # Map to deserializer error
        six.reraise(DeserializationError, DeserializationError(e), sys.exc_info()[2])


def _get_by_natural_pk(model, npk):
    while True:
        pk = model._meta.pk
        if pk.remote_field:
            model = pk.remote_field.model
        else:
            return model._default_manager.get_by_natural_key(*npk).pk


def _PythonDeserializer(object_list, **options):
    """
    Deserialize simple Python objects back into Django ORM instances.
    It's expected that you pass the Python objects themselves (instead of a
    stream or a string) to the constructor
    """
    db = options.pop('using', DEFAULT_DB_ALIAS)
    ignore = options.pop('ignorenonexistent', False)
    field_names_cache = {}  # Model: <list of field_names>

    for d in object_list:
        # Look up the model and starting build a dict of data for it.
        try:
            Model = _get_model(d["model"])
        except base.DeserializationError:
            if ignore:
                continue
            else:
                raise
        data = {}
        if 'pk' in d:
            pk = d.get("pk", None)
            if isinstance(pk, (list, tuple)):
                pk = _get_by_natural_pk(Model, pk)
            else:
                try:
                    pk = Model._meta.pk.to_python(pk)
                except Exception as e:
                    raise base.DeserializationError.WithData(e, d['model'], pk, None)
            data[Model._meta.pk.attname] = pk
        m2m_data = {}

        if Model not in field_names_cache:
            field_names_cache[Model] = {f.name for f in Model._meta.get_fields()}
        field_names = field_names_cache[Model]

        # Handle each field
        for (field_name, field_value) in six.iteritems(d["fields"]):

            if ignore and field_name not in field_names:
                # skip fields no longer on model
                continue

            if isinstance(field_value, str):
                field_value = force_text(
                    field_value, options.get("encoding", settings.DEFAULT_CHARSET), strings_only=True
                )

            field = Model._meta.get_field(field_name)

            # Handle M2M relations
            if field.remote_field and isinstance(field.remote_field, models.ManyToManyRel):
                model = field.remote_field.model
                if hasattr(model._default_manager, 'get_by_natural_key'):
                    def m2m_convert(value):
                        if hasattr(value, '__iter__') and not isinstance(value, six.text_type):
                            return model._default_manager.db_manager(db).get_by_natural_key(*value).pk
                        else:
                            return force_text(model._meta.pk.to_python(value), strings_only=True)
                else:
                    def m2m_convert(v):
                        return force_text(model._meta.pk.to_python(v), strings_only=True)

                try:
                    m2m_data[field.name] = []
                    for pk in field_value:
                        m2m_data[field.name].append(m2m_convert(pk))
                except Exception as e:
                    raise base.DeserializationError.WithData(e, d['model'], d.get('pk'), pk)

            # Handle FK fields
            elif field.remote_field and isinstance(field.remote_field, models.ManyToOneRel):
                model = field.remote_field.model
                if field_value is not None:
                    try:
                        default_manager = model._default_manager
                        field_name = field.remote_field.field_name
                        if hasattr(default_manager, 'get_by_natural_key'):
                            if hasattr(field_value, '__iter__') and not isinstance(field_value, six.text_type):
                                obj = default_manager.db_manager(db).get_by_natural_key(*field_value)
                                value = getattr(obj, field.remote_field.field_name)
                                # If this is a natural foreign key to an object that
                                # has a FK/O2O as the foreign key, use the FK value
                                if model._meta.pk.remote_field:
                                    value = value.pk
                            else:
                                value = model._meta.get_field(field_name).to_python(field_value)
                            data[field.attname] = value
                        else:
                            data[field.attname] = model._meta.get_field(field_name).to_python(field_value)
                    except Exception as e:
                        raise base.DeserializationError.WithData(e, d['model'], d.get('pk'), field_value)
                else:
                    data[field.attname] = None

            # Handle all other fields
            else:
                try:
                    data[field.name] = field.to_python(field_value)
                except Exception as e:
                    raise base.DeserializationError.WithData(e, d['model'], d.get('pk'), field_value)

        obj = base.build_instance(Model, data, db)
        yield base.DeserializedObject(obj, m2m_data)


def _get_model(model_identifier):
    """
    Helper to look up a model from an "app_label.model_name" string.
    """
    try:
        return apps.get_model(model_identifier)
    except (LookupError, TypeError):
        raise base.DeserializationError("Invalid model identifier: '%s'" % model_identifier)
