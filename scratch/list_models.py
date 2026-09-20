import urllib.request
import json
import os
from dotenv import load_dotenv

load_dotenv('.env')

req = urllib.request.Request(
    'https://api.groq.com/openai/v1/models',
    headers={'Authorization': f'Bearer {os.environ.get("GROQ_API_KEY")}', 'User-Agent': 'Mozilla/5.0'}
)
res = urllib.request.urlopen(req)
data = json.loads(res.read().decode('utf-8'))
print([m['id'] for m in data['data']])
