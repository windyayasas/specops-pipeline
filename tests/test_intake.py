"""Tests for spec intake and parsing."""

import pytest

from specops.models.spec import SpecModel
from specops.stages.intake import parse_spec_file


class TestSpecIntake:
    """Spec intake and parsing tests."""

    def test_parse_json_spec(self, sample_spec_json):
        """Test parsing JSON spec file."""
        spec = parse_spec_file(sample_spec_json)

        assert isinstance(spec, SpecModel)
        assert spec.feature_objective == "Implement health check endpoint"
        assert spec.user_story == "As a DevOps engineer, I want a health endpoint"
        assert len(spec.business_rules) == 2
        assert "Read-only" in spec.business_rules
        assert len(spec.acceptance_criteria) == 1
        assert len(spec.non_functional_requirements) == 1
        assert len(spec.out_of_scope) == 1

    def test_parse_yaml_spec(self, sample_spec_yaml):
        """Test parsing YAML spec file."""
        spec = parse_spec_file(sample_spec_yaml)

        assert isinstance(spec, SpecModel)
        assert spec.feature_objective == "Implement health check endpoint"
        assert len(spec.business_rules) == 2

    def test_parse_markdown_spec(self, sample_spec_markdown):
        """Test parsing Markdown spec with YAML frontmatter."""
        spec = parse_spec_file(sample_spec_markdown)

        assert isinstance(spec, SpecModel)
        assert spec.feature_objective == "Implement health check endpoint"
        assert len(spec.business_rules) == 2

    def test_parse_nonexistent_file(self):
        """Test that parsing nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            parse_spec_file("/nonexistent/spec.json")

    def test_parse_invalid_json(self, tmp_path):
        """Test that invalid JSON raises ValueError."""
        invalid_json = tmp_path / "invalid.json"
        with open(invalid_json, "w") as f:
            f.write("{ invalid json }")

        with pytest.raises(ValueError):
            parse_spec_file(invalid_json)

    def test_parse_missing_required_field(self, tmp_path):
        """Test that missing required field raises ValidationError."""
        import json

        incomplete_spec = tmp_path / "incomplete.json"
        with open(incomplete_spec, "w") as f:
            json.dump(
                {
                    "featureObjective": "Test",
                    # Missing userStory
                },
                f,
            )

        with pytest.raises(ValueError):
            parse_spec_file(incomplete_spec)

    def test_spec_model_with_all_fields(self, sample_spec_json):
        """Test SpecModel accepts all expected fields."""
        spec = parse_spec_file(sample_spec_json)

        assert spec.feature_objective
        assert spec.user_story
        assert spec.business_rules
        assert spec.acceptance_criteria
        assert spec.non_functional_requirements
        assert spec.out_of_scope

    def test_spec_model_serialization(self, sample_spec_json):
        """Test SpecModel can be serialized to dict."""
        spec = parse_spec_file(sample_spec_json)
        spec_dict = spec.model_dump()

        assert spec_dict["feature_objective"]
        assert spec_dict["user_story"]
        assert isinstance(spec_dict["business_rules"], list)

    def test_spec_model_default_empty_lists(self):
        """Test SpecModel defaults empty lists for optional fields."""
        spec = SpecModel(
            feature_objective="Test",
            user_story="Test user story",
        )

        assert spec.business_rules == []
        assert spec.acceptance_criteria == []
        assert spec.non_functional_requirements == []
        assert spec.out_of_scope == []
