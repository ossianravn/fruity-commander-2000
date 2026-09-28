"""Schema reuse must not share mutable results or retain stale model contracts."""

import unittest

from pydantic import BaseModel, Field
from pydantic.json_schema import GenerateJsonSchema

from scripts.startup_schemas import reuse_startup_schemas


class StartupSchemasTest(unittest.TestCase):
    def test_repeated_build_reuses_work_but_not_mutable_schema_objects(self):
        class Result(BaseModel):
            values: list[int]

        class CountingGenerator(GenerateJsonSchema):
            calls = 0

            def generate(self, *args, **kwargs):
                type(self).calls += 1
                return super().generate(*args, **kwargs)

        expected = Result.model_json_schema()
        with reuse_startup_schemas():
            first = Result.model_json_schema(schema_generator=CountingGenerator)
            first["properties"]["values"]["items"]["type"] = "string"
            second = Result.model_json_schema(schema_generator=CountingGenerator)
            self.assertEqual(second, expected)
            self.assertEqual(CountingGenerator.calls, 1)

    def test_options_and_rebuild_keep_separate_contracts(self):
        class Result(BaseModel):
            value: int = Field(alias="external")

        with reuse_startup_schemas():
            aliased = Result.model_json_schema(by_alias=True)
            named = Result.model_json_schema(by_alias=False)
            self.assertIn("external", aliased["properties"])
            self.assertIn("value", named["properties"])
            Result.model_config["title"] = "Rebuilt result"
            Result.model_rebuild(force=True)
            rebuilt = Result.model_json_schema(by_alias=True)
            self.assertEqual(rebuilt["title"], "Rebuilt result")
            self.assertNotEqual(rebuilt, aliased)

    def test_exception_restores_method_before_runtime_calls(self):
        original = BaseModel.__dict__["model_json_schema"]
        with self.assertRaisesRegex(RuntimeError, "registration failed"):
            with reuse_startup_schemas():
                raise RuntimeError("registration failed")
        self.assertIs(BaseModel.__dict__["model_json_schema"], original)


if __name__ == "__main__":
    unittest.main()
