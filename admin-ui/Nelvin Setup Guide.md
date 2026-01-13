As a latest version read this if you deploy on a VM

## Backend setup
1. Backend (python)
2. Git pull ```python main.py```.
3. APIs and WSS are both hosted in port 8000
4. External system will not be able to call this as port 8000 is not accessible directly. We will configure it via UI Configuration, see below.


## UI Setup
1. NextJS at port 3000 
2. Configure IIS default reverse proxy :80 to :3000
3. Create self-signed cert, enable https, configure web.config to redirect to https
4. Since proxy is configured only for port :3000 (for UI only), next step is to configure for the API and WSS requests proxy
5. Add 2 redirects in web.config -
```
NEXT_PUBLIC_API_HOST=https://18.223.174.209/api
NEXT_PUBLIC_WS_HOST=wss://18.223.174.209/

NEXT_PUBLIC_API_PORT=
NEXT_PUBLIC_WS_PORT=
```
**ensure to make the ports empty**


```
NOTE: This configuration will work only from outside. For local dev and internal VM test, continue to use the below configurations.

Ignore all other .env configuration guide as those are obsolete and this is updated working configuration.

```
