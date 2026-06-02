import re
import json
from app.prompt_builder import render_prompt, build_request_body


class TestRenderPrompt:
    def test_no_placeholders_returns_same_text(self):
        text = "Hello, can you help me with something?"
        result = render_prompt(text, [])
        assert result == text

    def test_placeholders_get_replaced(self):
        text = "My name is {name} and SSN is {ssn}"
        result = render_prompt(text, ["name", "ssn"])
        assert "{name}" not in result
        assert "{ssn}" not in result
        assert re.search(r"\d{3}-\d{2}-\d{4}", result)

    def test_unknown_placeholder_left_as_is(self):
        text = "Value is {unknown_thing}"
        result = render_prompt(text, [])
        assert "{unknown_thing}" in result

    def test_multiple_calls_produce_different_data(self):
        text = "SSN: {ssn}"
        results = [render_prompt(text, ["ssn"]) for _ in range(20)]
        assert len(set(results)) > 1


class TestBuildRequestBody:
    def test_text_only_request(self):
        body = build_request_body("What is the weather?", image_base64=None)
        assert body["request"]["model"] == "gpt-4"
        msg = body["request"]["messages"][0]
        assert msg["role"] == "user"
        assert msg["content"] == "What is the weather?"

    def test_image_request_uses_content_array(self):
        body = build_request_body(
            "Describe this image",
            image_base64="data:image/png;base64,abc123"
        )
        msg = body["request"]["messages"][0]
        assert isinstance(msg["content"], list)
        assert len(msg["content"]) == 2
        assert msg["content"][0]["type"] == "text"
        assert msg["content"][0]["text"] == "Describe this image"
        assert msg["content"][1]["type"] == "image_url"
        assert msg["content"][1]["image_url"]["url"] == "data:image/png;base64,abc123"

    def test_body_is_json_serializable(self):
        body = build_request_body("test", image_base64=None)
        json.dumps(body)
