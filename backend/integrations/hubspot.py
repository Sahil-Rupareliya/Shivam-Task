import os
import json
import secrets
import asyncio
import httpx
import requests
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse

from integrations.integration_item import IntegrationItem
from redis_client import add_key_value_redis, get_value_redis, delete_key_redis


# Environment variables
HUBSPOT_CLIENT_ID = os.getenv('HUBSPOT_CLIENT_ID')
HUBSPOT_CLIENT_SECRET = os.getenv('HUBSPOT_CLIENT_SECRET')
HUBSPOT_REDIRECT_URI = os.getenv('HUBSPOT_REDIRECT_URI', 'http://localhost:8000/integrations/hubspot/oauth2callback')

HUBSPOT_AUTH_URL = 'https://app.hubspot.com/oauth/authorize'
HUBSPOT_TOKEN_URL = 'https://api.hubapi.com/oauth/v1/token'

HUBSPOT_SCOPE = 'crm.objects.contacts.read crm.objects.deals.read'


async def authorize_hubspot(user_id, org_id):
    if not HUBSPOT_CLIENT_ID or not HUBSPOT_REDIRECT_URI:
        raise HTTPException(status_code=500, detail='HubSpot OAuth is not configured. Missing env vars.')

    state_data = {
        'state': secrets.token_urlsafe(32),
        'user_id': user_id,
        'org_id': org_id,
    }
    encoded_state = json.dumps(state_data)

    await add_key_value_redis(f'hubspot_state:{org_id}:{user_id}', encoded_state, expire=600)

    params = (
        f'?client_id={HUBSPOT_CLIENT_ID}'
        f'&redirect_uri={HUBSPOT_REDIRECT_URI}'
        f'&scope={HUBSPOT_SCOPE}'
        f'&response_type=code'
        f'&state={encoded_state}'
    )

    auth_url = f'{HUBSPOT_AUTH_URL}{params}'
    print(f'[HubSpot] Generated authorize URL for user {user_id}, org {org_id}')
    return auth_url


async def oauth2callback_hubspot(request: Request):
    if request.query_params.get('error'):
        raise HTTPException(status_code=400, detail=request.query_params.get('error'))

    code = request.query_params.get('code')
    encoded_state = request.query_params.get('state')
    if not code or not encoded_state:
        raise HTTPException(status_code=400, detail='Missing code or state in callback.')

    state_data = json.loads(encoded_state)
    original_state = state_data.get('state')
    user_id = state_data.get('user_id')
    org_id = state_data.get('org_id')

    saved_state = await get_value_redis(f'hubspot_state:{org_id}:{user_id}')
    if not saved_state or original_state != json.loads(saved_state).get('state'):
        raise HTTPException(status_code=400, detail='State does not match.')

    if not HUBSPOT_CLIENT_ID or not HUBSPOT_CLIENT_SECRET or not HUBSPOT_REDIRECT_URI:
        raise HTTPException(status_code=500, detail='HubSpot OAuth is not configured. Missing env vars.')

    async with httpx.AsyncClient() as client:
        response, _ = await asyncio.gather(
            client.post(
                HUBSPOT_TOKEN_URL,
                data={
                    'grant_type': 'authorization_code',
                    'client_id': HUBSPOT_CLIENT_ID,
                    'client_secret': HUBSPOT_CLIENT_SECRET,
                    'redirect_uri': HUBSPOT_REDIRECT_URI,
                    'code': code,
                },
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
            ),
            delete_key_redis(f'hubspot_state:{org_id}:{user_id}'),
        )

    if response.status_code != 200:
        print(f'[HubSpot] Token exchange failed: {response.status_code} {response.text}')
        raise HTTPException(status_code=400, detail='Failed to exchange code for tokens.')

    token_payload = response.json()
    await add_key_value_redis(
        f'hubspot_credentials:{org_id}:{user_id}', json.dumps(token_payload), expire=600
    )

    print(f'[HubSpot] Stored credentials for user {user_id}, org {org_id}')

    close_window_script = """
    <html>
        <script>
            window.close();
        </script>
    </html>
    """
    return HTMLResponse(content=close_window_script)


async def get_hubspot_credentials(user_id, org_id):
    credentials = await get_value_redis(f'hubspot_credentials:{org_id}:{user_id}')
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')
    credentials = json.loads(credentials)
    await delete_key_redis(f'hubspot_credentials:{org_id}:{user_id}')
    return credentials


def _hs_contact_to_integration_item(contact: dict) -> IntegrationItem:
    properties = contact.get('properties', {}) or {}
    firstname = properties.get('firstname') or ''
    lastname = properties.get('lastname') or ''
    name = (firstname + ' ' + lastname).strip() or properties.get('email') or 'Unknown Contact'
    item = IntegrationItem(
        id=contact.get('id'),
        name=name,
        type='Contact',
        parent_id=None,
        parent_path_or_name=None,
        url=None,
    )
    return item


async def get_items_hubspot(credentials) -> list[IntegrationItem]:
    try:
        credentials = json.loads(credentials)
    except Exception:
        # credentials might already be a dict
        pass

    access_token = (
        credentials.get('access_token') if isinstance(credentials, dict) else None
    )
    if not access_token:
        raise HTTPException(status_code=400, detail='Missing access token for HubSpot.')

    url = 'https://api.hubapi.com/crm/v3/objects/contacts'
    params = {'limit': 10}
    headers = {'Authorization': f'Bearer {access_token}'}

    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        print(f'[HubSpot] Fetch contacts failed: {response.status_code} {response.text}')
        raise HTTPException(status_code=400, detail='Failed to fetch HubSpot contacts.')

    data = response.json()
    results = data.get('results', [])
    items: list[IntegrationItem] = []
    for contact in results:
        try:
            items.append(_hs_contact_to_integration_item(contact))
        except Exception as e:
            print(f'[HubSpot] Failed to transform contact: {e}')

    print(f'[HubSpot] Returning {len(items)} items')
    return items