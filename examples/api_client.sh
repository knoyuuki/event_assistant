#!/usr/bin/env bash
# 外部接口签名调用示例（Shell + curl，仅依赖 openssl/curl）
#
# 用法:
#   export BASE_URL=http://127.0.0.1
#   export APP_ID=ea_xxxxxxxxxxxxxxxx
#   export APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxx
#   bash examples/api_client.sh
#
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1}"
: "${APP_ID:?请设置 APP_ID}"
: "${APP_SECRET:?请设置 APP_SECRET}"

# 计算签名: METHOD\nPATH\nTS\nNONCE\nBODY_SHA256
sign() { # $1=method $2=path $3=ts $4=nonce $5=body
    local body_sha
    body_sha=$(printf '%s' "$5" | sha256sum | awk '{print $1}')
    printf '%s\n%s\n%s\n%s\n%s' "$1" "$2" "$3" "$4" "$body_sha" \
        | openssl dgst -sha256 -hmac "$APP_SECRET" -binary | xxd -p -c 256
}

echo "BASE_URL=$BASE_URL  APP_ID=$APP_ID"
echo

# ── 1. GET 签名请求 ───────────────────────────────
TS=$(date +%s); NONCE=$(openssl rand -hex 8)
SIG=$(sign GET /ext/persons "$TS" "$NONCE" "")
echo "[GET /ext/persons]"
curl -s "$BASE_URL/ext/persons?limit=3" \
    -H "X-App-Id: $APP_ID" -H "X-Timestamp: $TS" -H "X-Nonce: $NONCE" -H "X-Signature: $SIG"
echo; echo

# ── 2. POST 签名请求（JSON）───────────────────────
TS=$(date +%s); NONCE=$(openssl rand -hex 8)
BODY='{"hello":"world","n":42}'
SIG=$(sign POST /ext/echo "$TS" "$NONCE" "$BODY")
echo "[POST /ext/echo]"
curl -s -X POST "$BASE_URL/ext/echo" \
    -H "X-App-Id: $APP_ID" -H "X-Timestamp: $TS" -H "X-Nonce: $NONCE" -H "X-Signature: $SIG" \
    -H "Content-Type: application/json" -d "$BODY"
echo
