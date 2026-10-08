# Tuya Cloud setup guide

This guide walks you from zero to a working `tuya-mcp` server: create a Tuya
developer account, create a cloud project, link your Tuya Smart / Smart Life
app account, collect the three credentials, and plug the server into your MCP
client.

Expect about 15 minutes. Everything is free.

> The Tuya Developer Platform UI changes often. Labels below match the
> platform as of October 2026; if a button moved, look for the same wording
> nearby.

---

## Before you start

You need:

- Your devices already paired in the **Tuya Smart** or **Smart Life** app on
  your phone. Both apps run on the same Tuya cloud and work the same way
  here. White-label brands such as LSC Smart Connect (Action) are Tuya
  devices too.
- The phone with that app, to scan a QR code.
- The **region** of your app account. It is chosen when you sign up in the
  app and usually matches your country (e.g. Europe for France).

### Two different accounts

| | App account | Developer account |
|---|---|---|
| Used for | Pairing and controlling your devices | Creating the cloud project that issues API credentials |
| Where | Tuya Smart / Smart Life app | https://iot.tuya.com |
| You already have it? | Yes | No, create it in step 1 |

You may use the same email address for both, but they are separate accounts.
Step 4 (QR scan) is what connects them.

---

## Step 1: Create a developer account

1. Go to https://iot.tuya.com and sign up.
2. When asked for an account type, any choice works. You can also skip it.
3. Close any welcome or announcement pop-up (e.g. **Got it**).

## Step 2: Create a cloud project

1. In the left sidebar, click **Cloud** (cloud icon), then **Development**.
   Alternatively, from the home page: **Developer Console > Cloud Development**.
2. Click **Create Cloud Project** and fill in:

   | Field | Value |
   |---|---|
   | Project Name | anything, e.g. `tuya-mcp` |
   | Industry | Smart Home |
   | Development Method | Smart Home |
   | Data Center | **the region of your app account** (e.g. *Central Europe Data Center*) |

   > **The data center must match your app account region.** If it does not,
   > the link in step 4 succeeds but no device ever shows up.

3. Click **Create**.

## Step 3: Authorize the API services

The **Configuration Wizard > Authorize API Services** screen opens right after
creation. Make sure the right-hand column (*Selected API Service(s)*) contains
at least:

| Service | Why |
|---|---|
| **IoT Core** | Devices: list, status, commands. Required. |
| **Authorization Token Management** | Access tokens. Required. |
| Smart Home Basic Service | Home and user data. Recommended. |
| Smart Home Scene Linkage | Tap-to-run scenes. May be marked *[Deprecate]*; keep it anyway. |
| Data Dashboard Service | Optional, harmless. |

Click **Authorize**.

You can add or remove services later in the project's **Service API** tab.

## Step 4: Link your app account (QR code)

1. In the project, open the **Devices** tab.
2. Open the **Link App Account** sub-tab, then **Account Authorization**.
   - Do **not** use *Link My App*. That tab is for custom OEM apps, not for
     Tuya Smart / Smart Life.
   - Do **not** use the *Add Device* button either.
3. Click **Add App Account > Tuya App Account Authorization**. Do not pick
   *Configure OAuth 2.0 Authorization*. A QR code appears.
4. On your phone, in Tuya Smart / Smart Life: open the **Me** tab, tap the
   **scan** icon (top-right) and scan the QR code. Confirm in the app.
5. Back on the website, the **Link App Account** dialog asks for a device
   linking method. Keep **Automatic Link (Recommended)** so that devices you
   add later are linked too. Click **OK**.
6. A row appears in the table with your app account.

### Check that devices are associated

Look at the **Associated/Number of devices** column of that row.

- `N/N` (e.g. `3/3`): all good.
- `0/N`: devices are visible but not yet associated with the project, and the
  API will return an empty list.
  1. Wait a minute and reload the page. Automatic linking can lag.
  2. If it is still `0/N`, click **Manage Devices** on the row and associate
     the devices with your project.
- Fewer devices than you expect: some devices may be paired under another
  app account or another *home* in the app.

Finally, open **Devices > All Devices**. Your devices must be listed there.

## Step 5: Collect the three credentials

| Variable | Where to find it |
|---|---|
| `TUYA_ACCESS_ID` | **Overview** tab > *Authorization Key* > **Access ID/Client ID** |
| `TUYA_ACCESS_SECRET` | **Overview** tab > *Authorization Key* > **Access Secret/Client Secret** (click the eye icon) |
| `TUYA_UID` | **Devices > Link App Account** > **UID** column of your app account row (looks like `eu17…`) |

Keep the Access Secret private. Never paste it in an issue, a chat or a log.

Optional variables:

| Variable | Default | Notes |
|---|---|---|
| `TUYA_API_ENDPOINT` | `https://openapi.tuyaeu.com` | Must match the data center of step 2 (see below) |
| `TUYA_CACHE_TTL` | `60` | Seconds before the device list is refreshed |
| `TUYA_LOG_LEVEL` | `WARNING` | `DEBUG` for troubleshooting; secrets are always redacted |

| Data center | `TUYA_API_ENDPOINT` |
|---|---|
| Central Europe / Western Europe | `https://openapi.tuyaeu.com` |
| Western America / Eastern America | `https://openapi.tuyaus.com` |
| China | `https://openapi.tuyacn.com` |
| India | `https://openapi.tuyain.com` |

## Step 6: Store the credentials locally

From the project folder:

```bash
cp .env.example .env
chmod 600 .env        # readable by you only
```

Edit `.env` and fill in the values, with no quotes and no spaces around `=`:

```
TUYA_ACCESS_ID=your_access_id
TUYA_ACCESS_SECRET=your_access_secret
TUYA_UID=your_uid
```

`.env` is git-ignored. Only `.env.example` (no secrets) is committed.

The server itself reads **environment variables only**. `.env` is just a
convenient place to keep them; load it into your shell with:

```bash
set -a; . ./.env; set +a
```

## Step 7: Verify

With the variables loaded, list your devices.

From a development checkout:

```bash
.venv/bin/python -c "import asyncio; from tuya_mcp.config import Config; from tuya_mcp.client import TuyaClient; [print(d) for d in asyncio.run(TuyaClient(Config.from_env()).list_devices())]"
```

You should get one line per device. If you get an error, see
[Troubleshooting](#troubleshooting).

## Step 8: Register the server in your MCP client

### Claude Code

```bash
set -a; . ./.env; set +a
claude mcp add tuya --scope user \
  -e TUYA_ACCESS_ID="$TUYA_ACCESS_ID" \
  -e TUYA_ACCESS_SECRET="$TUYA_ACCESS_SECRET" \
  -e TUYA_UID="$TUYA_UID" \
  -- uvx tuya-mcp
```

From a development checkout, replace `uvx tuya-mcp` with the absolute path to
`.venv/bin/tuya-mcp`.

Restart Claude Code, run `/mcp` and check that `tuya` is connected.

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "tuya": {
      "command": "uvx",
      "args": ["tuya-mcp"],
      "env": {
        "TUYA_ACCESS_ID": "your_access_id",
        "TUYA_ACCESS_SECRET": "your_access_secret",
        "TUYA_UID": "your_uid"
      }
    }
  }
}
```

The MCP client stores these values in plain text in its own config file.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Missing required environment variable(s): …` | Variable not set in the server's environment | Fill `.env` and reload it, or check the `env` block of your MCP client config |
| `Tuya API error 2009: clientId is invalid` | Wrong Access ID, or endpoint does not match the project data center | Re-copy the Access ID; set `TUYA_API_ENDPOINT` for your data center |
| `Tuya API error 1004: sign invalid` | Wrong Access Secret | Re-copy the secret (eye icon), with no trailing space |
| `Tuya API error 1106: permission deny` | IoT Core not authorized, its trial expired, or device not linked | **Service API** tab: authorize IoT Core; if expired, see below; check the *Associated* column |
| `Tuya API error 28841002` / `28841004` / `288411xx` | Cloud plan or IoT Core trial expired / quota exhausted | Renew the trial, see below |
| `Tuya API error 28841105` | Project not authorized for this API | **Service API** tab: add the missing service (e.g. Smart Home Scene Linkage for scenes) |
| `Tuya API error 1013` | Computer clock is wrong | Enable automatic time sync |
| Empty device list | App not linked, devices not associated (`0/N`), or wrong data center | Redo step 4 and check the *Associated* column |
| Some devices missing | Paired under another app account or home | Link that account too, or move the devices in the app |

### Free trial expiry

The free IoT Core resource pack lasts about one month. When it expires, calls
fail with a permission error, and the server tells you to renew it. Your
Access ID and Secret do **not** change: nothing to update in `.env` or in your
MCP client. To renew it for free: **Cloud > Development >
your project > Service API**, click **Go to Authorize** or **Extend Trial
Period** next to IoT Core, and fill in the short form. Plan to renew it
periodically.
