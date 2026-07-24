import urllib.request
import json
req = urllib.request.Request(
    'https://www.instahyre.com/api/v1/job_search?search=internship',
    headers={'User-Agent': 'Mozilla/5.0'}
)
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode('utf-8'))
        if data.get('objects'):
            print(json.dumps(data['objects'][0], indent=2))
except Exception as e:
    print('Error:', e)
