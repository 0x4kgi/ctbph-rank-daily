"""Regression tests for scripts/discord_webhook.py."""
import unittest
from unittest.mock import patch

from scripts.discord_webhook import embed_maker, send_webhook


class TestEmbedMaker(unittest.TestCase):
    def test_none_values_dropped(self):
        e = embed_maker(title="t", description=None, color=123)
        self.assertEqual(e, {"title": "t", "color": 123})

    def test_all_none_gives_empty_dict(self):
        self.assertEqual(embed_maker(), {})

    def test_all_fields_kept(self):
        e = embed_maker(
            title="t", description="d", url="u", color=1,
            fields=[{"name": "n", "value": "v"}],
            author={"name": "a"}, footer={"text": "f"},
            timestamp="ts", image={"url": "i"}, thumbnail={"url": "th"},
        )
        self.assertEqual(e["title"], "t")
        self.assertEqual(e["fields"], [{"name": "n", "value": "v"}])
        self.assertEqual(e["footer"], {"text": "f"})


class TestSendWebhook(unittest.TestCase):
    def test_no_url_sends_nothing(self):
        with patch("scripts.discord_webhook.os.getenv", return_value=None):
            with patch(
                "scripts.discord_webhook.requests.post"
            ) as mock_post:
                send_webhook(content="hi")
                mock_post.assert_not_called()

    def test_success_posts_payload(self):
        fake_resp = type("R", (), {"status_code": 204})()
        with patch("scripts.discord_webhook.os.getenv",
                   return_value="http://example/hook"):
            with patch("scripts.discord_webhook.requests.post",
                       return_value=fake_resp) as mock_post:
                send_webhook(content="hi", username="bot",
                             embeds=[{"title": "t"}])
                mock_post.assert_called_once()
                _, kwargs = mock_post.call_args
                self.assertEqual(kwargs["json"]["content"], "hi")
                self.assertEqual(kwargs["json"]["username"], "bot")

    def test_non_204_does_not_raise_current_behavior(self):
        # current behavior: logs an error, does not raise. Lock it so
        # callers keep relying on fire-and-forget semantics.
        fake_resp = type("R", (), {"status_code": 400})()
        with patch("scripts.discord_webhook.os.getenv",
                   return_value="http://example/hook"):
            with patch("scripts.discord_webhook.requests.post",
                       return_value=fake_resp):
                send_webhook(content="hi")  # should not raise


if __name__ == "__main__":
    unittest.main()
