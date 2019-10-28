import json
from django.test import TestCase

from pulp_2to3_migration.app.json_schema import SCHEMA


class TestSchemad(TestCase):
    """Test stored schema"""

    def test_parse_of_schema(self):
        """Test parsing of schema to validate json structure"""
        schema = json.loads(SCHEMA)
        self.assertEqual(dict, schema.__class__)
