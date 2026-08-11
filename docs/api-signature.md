# 外部接口签名与加密规范

本文档定义「会务助手」对外部应用开放接口（`/ext/*`）的通用签名与加密规范。
所有外部调用必须先通过**应用密钥管理**创建密钥（见 README「外部接口」章节），
再按本规范签名调用。

---

## 1. 基本概念

| 概念 | 说明 |
|------|------|
| `app_id` | 应用标识，创建密钥时生成，格式 `ea_xxxxxxxxxxxxxxxx`，明文传输 |
| `app_secret` | 应用密钥，创建/轮换时**仅展示一次**，服务端加密存储，请妥善保管 |
| 签名算法 | HMAC-SHA256（密钥 = `app_secret`，输出 hex 小写） |
| 时间戳 | Unix 秒级时间戳，允许偏差 **±300 秒**，防重放 |
| nonce | 随机字符串（推荐 16 字节以上随机数），同一 app 在时间窗内不可重复，防重放 |

## 2. 请求头（4 个必选 + 1 个可选）

| 请求头 | 必选 | 说明 |
|--------|------|------|
| `X-App-Id` | ✅ | 应用标识 |
| `X-Timestamp` | ✅ | Unix 秒级时间戳 |
| `X-Nonce` | ✅ | 随机串（每次请求唯一） |
| `X-Signature` | ✅ | 签名，见下 |
| `X-Encrypt` | ⬜ | 设为 `1` 表示请求体经 AES-256-GCM 加密（可选） |

## 3. 签名计算步骤

### 3.1 构造待签串（string_to_sign）

```
METHOD\nPATH\nTIMESTAMP\nNONCE\nBODY_SHA256
```

- `METHOD`：HTTP 方法大写（`GET` / `POST` / `PUT` / `DELETE`）
- `PATH`：请求路径（不含域名、不含 query，例如 `/ext/echo`）
- `TIMESTAMP` / `NONCE`：与请求头一致
- `BODY_SHA256`：请求体原始字节的 SHA-256（十六进制小写）；
  GET 请求或空请求体时取 `sha256("")`，即
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- 若开启 `X-Encrypt: 1`：`BODY_SHA256` 对**加密后的密文**计算（先加密、后签名、后发送）

### 3.2 计算签名

```
X-Signature = hex( HMAC-SHA256( key = app_secret, data = string_to_sign ) )
```

## 4. 服务端校验流程（失败返回 401/403）

1. 校验 4 个签名头齐全，`app_id` 存在且状态为启用
2. 校验密钥未过期（`expires_at`）
3. 校验时间戳在 `当前时间 ±300 秒` 内
4. 校验 nonce 未在时间窗内重复使用（防重放）
5. 用 `app_secret` 重算签名并比对（恒定时间比较）
6. （可选）`X-Encrypt: 1` 时用 `app_secret` 派生密钥解密请求体后再解析参数

错误码：`401` 签名/时间戳/nonce 非法，`403` 应用被禁用或过期，`400` 业务参数错误。

## 5. 可选：请求体加密（AES-256-GCM）

- 密钥派生：`key = SHA-256(app_secret)`（32 字节）
- 随机 nonce：12 字节，每次加密随机生成
- 输出：`base64( nonce(12B) + tag(16B) + ciphertext )`
- 发送时请求头加 `X-Encrypt: 1`，签名针对加密后的 body 字节计算

## 6. 示例

### Python（推荐，见 `examples/api_client.py`）

```python
import hashlib, hmac, time, secrets, requests

def sign(method, path, timestamp, nonce, body_bytes, secret):
    body_sha = hashlib.sha256(body_bytes).hexdigest()
    s2s = "\n".join([method.upper(), path, str(timestamp), nonce, body_sha])
    return hmac.new(secret.encode(), s2s.encode(), hashlib.sha256).hexdigest()

ts = int(time.time())
nonce = secrets.token_hex(8)
body = b'{"hello": "world"}'
headers = {
    "X-App-Id": app_id, "X-Timestamp": str(ts), "X-Nonce": nonce,
    "X-Signature": sign("POST", "/ext/echo", ts, nonce, body, app_secret),
}
r = requests.post(base_url + "/ext/echo", data=body, headers=headers)
```

### Shell / curl（见 `examples/api_client.sh`）

```bash
TS=$(date +%s); NONCE=$(openssl rand -hex 8)
BODY='{"hello":"world"}'
BODY_SHA=$(printf '%s' "$BODY" | sha256sum | awk '{print $1}')
S2S=$(printf 'POST\n/ext/echo\n%s\n%s\n%s' "$TS" "$NONCE" "$BODY_SHA")
SIG=$(printf '%s' "$S2S" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')
curl -s -X POST "$BASE/ext/echo" \
  -H "X-App-Id: $APP_ID" -H "X-Timestamp: $TS" -H "X-Nonce: $NONCE" \
  -H "X-Signature: $SIG" -H "Content-Type: application/json" -d "$BODY"
```

## 7. 调用日志

- 每次携带 `X-App-Id` 的调用（含签名失败）都会记录：**调用方 IP、接口路径、状态码、请求参数、返回结果、耗时**
- 日志默认保留 **7 天**，后端每小时自动清理超期数据
- 通过管理接口 `GET /api/app-keys/{id}/logs` 查看（需 `X-Admin-Token`）
