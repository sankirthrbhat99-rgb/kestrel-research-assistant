import urllib.error
import urllib.request
from unittest.mock import patch, MagicMock

from kestrel.llm import LLMClient, LLMQuotaExhausted

def mock_urlopen(*args, **kwargs):
    raise urllib.error.HTTPError(
        url="http://mock.com",
        code=429,
        msg="Too Many Requests",
        hdrs={},
        fp=MagicMock(read=lambda: b'{"error": "rate limit exhausted"}')
    )

def test_quota_exhausted():
    client = LLMClient()
    # Force it to think it's configured
    client.config = type('obj', (object,), {'configured': True, 'api_key': 'fake', 'model': 'fake', 'base_url': 'http://mock.com', 'timeout': 10})()
    
    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        # We also mock time.sleep so we don't actually wait
        with patch("time.sleep") as mock_sleep:
            try:
                client.complete("Test prompt")
                print("Failed: Should have raised LLMQuotaExhausted")
            except LLMQuotaExhausted as e:
                print(f"Success! Caught LLMQuotaExhausted: {e}")
            except Exception as e:
                print(f"Failed: Raised wrong exception: {type(e)} - {e}")

if __name__ == '__main__':
    test_quota_exhausted()
