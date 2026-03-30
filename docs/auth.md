# Authentication & User Management

Locus ships with an optional auth system. When disabled (the default), all requests run as the built-in `guest` user — no changes to existing behavior.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `AUTH_ENABLED` | `false` | Enable auth. Set to `true` to require login. |
| `REGISTRATION_ENABLED` | `false` | Allow new users to self-register. Set to `true` to enable. |
| `SECRET_KEY` | *(none)* | **Required** when `AUTH_ENABLED=true`. Use a long random string. |
| `SESSION_HOURS` | `24` | How long a web (JWT) session lasts. |

### Generating a secret key

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Example docker-compose override

```yaml
environment:
  AUTH_ENABLED: "true"
  REGISTRATION_ENABLED: "false"
  SECRET_KEY: "your-long-random-secret-here"
```

---

## First-time setup

1. Set `AUTH_ENABLED=true` and `SECRET_KEY` in your environment.
2. Set `REGISTRATION_ENABLED=true` temporarily, or create the first user via the API:

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "your-password"}'
```

**The first registered user automatically becomes an admin.**

1. Log in to get a session token:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "your-password"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

1. Use the token on all requests:

```bash
curl http://localhost:8000/spaces -H "Authorization: Bearer $TOKEN"
```

---

## Web UI

When `AUTH_ENABLED=true`, opening Locus shows a login page.

- **Sign in** — enter username and password.
- **Create account** — visible only when `REGISTRATION_ENABLED=true`.
- **Use reset token** — if an admin generated a reset token for you, paste it here along with your new password.

After login, the **Settings panel** (⚙) shows extra sections:

- **Change Password** — update your own password (requires current password).
- **API Keys** — create and revoke scoped API keys.
- **Users** (admins only) — manage all accounts.

---

## API keys

API keys let you grant scoped access without sharing your session token — useful for scripts, CI, or third-party integrations.

### Create a key

```bash
curl -X POST http://localhost:8000/auth/keys \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-script",
    "allowed_spaces": ["notes", "research"],
    "allowed_collections": []
  }'
```

The response includes the raw key (`lcs_...`) — **copy it now, it is not stored**.

Leave `allowed_spaces` and `allowed_collections` empty (`[]`) to grant access to all of your spaces/collections.

### Use a key

```bash
curl http://localhost:8000/spaces \
  -H "Authorization: Bearer lcs_your_key_here"
```

### Key restrictions

- API keys **cannot** create or delete spaces/collections (only access them).
- API keys **cannot** modify settings.
- API keys **cannot** create, list, or delete other API keys.
- API keys **cannot** perform admin actions.

---

## Admin user management

Admins can manage all accounts from the **Users** section of the Settings panel, or via the API.

### List all users

```bash
curl http://localhost:8000/auth/users -H "Authorization: Bearer $TOKEN"
```

### Reset a user's password

```bash
curl -X POST http://localhost:8000/auth/users/{user_id}/reset-password \
  -H "Authorization: Bearer $TOKEN"
# Returns: {"reset_token": "..."}
```

Share the token with the user out-of-band. It expires in **15 minutes**. The user exchanges it on the login page ("Use reset token") or via the API:

```bash
curl -X POST http://localhost:8000/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{"token": "...", "new_password": "newpass123"}'
```

### Promote / demote admin

```bash
curl -X POST http://localhost:8000/auth/users/{user_id}/promote \
  -H "Authorization: Bearer $TOKEN"

curl -X POST http://localhost:8000/auth/users/{user_id}/demote \
  -H "Authorization: Bearer $TOKEN"
```

Admins cannot demote themselves.

### Delete a user

```bash
curl -X DELETE http://localhost:8000/auth/users/{user_id} \
  -H "Authorization: Bearer $TOKEN"
```

This removes the user and their DB records (spaces, collections, API keys). On-disk data under `data/{username}/` is **not deleted** — remove it manually if needed.

Admins cannot delete themselves or the `guest` user.

---

## Data isolation

Each user's spaces live under `{DATA_DIR}/{username}/{space}/`. Users can only access their own spaces and collections. Admins can manage accounts but **cannot** read another user's documents or search their spaces.

### Legacy migration

On first boot with auth enabled, Locus automatically moves any flat `data/{space}/` directories into `data/guest/{space}/` so existing data is preserved under the guest account.

---

## Auth status endpoint

Always public, no token required:

```bash
curl http://localhost:8000/auth/status
# {"auth_enabled": true, "registration_enabled": false}
```
