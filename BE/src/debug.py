import os
from dotenv import load_dotenv
load_dotenv()
token = os.environ.get("GITHUB_TOKEN", "")
print(
    f"Token loaded: {'yes (' + token[:8] + '...)' if token else 'NO — empty!'}")
