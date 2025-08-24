import requests
import json

# Test the server endpoints
BASE_URL = 'http://localhost:5000'

def test_config():
    print('Testing /config endpoint...')
    response = requests.get(f'{BASE_URL}/config')
    print(f'GET /config: {response.status_code} - {response.json()}')
    
    # Test POST config
    test_config = {
        'restic_version': '0.16.0',
        'locations': {},
        'paths': ['/home/nonbios/test']
    }
    response = requests.post(f'{BASE_URL}/config', json=test_config)
    print(f'POST /config: {response.status_code} - {response.json()}')

if __name__ == '__main__':
    try:
        test_config()
        print('Basic tests completed successfully!')
    except requests.exceptions.ConnectionError:
        print('Server is not running. Start it with: ./start_server.sh')
    except Exception as e:
        print(f'Test failed: {e}')
