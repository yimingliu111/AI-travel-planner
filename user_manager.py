"""
user_manager.py - 多用户管理 + API Key AES 加密存储
API keys 用用户密码 AES-GCM 加密，users.json 泄露也无法读取
"""

import json, hashlib, os, base64, secrets
from datetime import datetime
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Util.Padding import pad, unpad

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.json")
SALT_BYTES = 16
PBKDF2_ITERATIONS = 100_000


# ---- 加密工具 ----

def _derive_key(password: str, salt: bytes) -> bytes:
    """从密码+盐派生 AES-256 密钥"""
    return PBKDF2(password.encode(), salt, dkLen=32, count=PBKDF2_ITERATIONS)


def _encrypt(plaintext: str, password: str, salt: bytes | None = None) -> dict:
    """用密码加密明文，返回 {'salt': base64, 'ciphertext': base64}"""
    if salt is None:
        salt = secrets.token_bytes(SALT_BYTES)
    key = _derive_key(password, salt)
    nonce = secrets.token_bytes(12)  # AES-GCM nonce
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode())
    # 存储: nonce + tag + ciphertext
    blob = nonce + tag + ciphertext
    return {
        "salt": base64.b64encode(salt).decode(),
        "blob": base64.b64encode(blob).decode(),
    }


def _decrypt(encrypted: dict, password: str) -> str | None:
    """用密码解密，失败返回 None"""
    try:
        salt = base64.b64decode(encrypted["salt"])
        blob = base64.b64decode(encrypted["blob"])
        key = _derive_key(password, salt)
        nonce, tag, ciphertext = blob[:12], blob[12:28], blob[28:]
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        return plaintext.decode()
    except Exception:
        return None


# ---- 数据读写 ----

def load_users() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_users(users: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


# ---- 用户操作 ----

def register(username: str, password: str) -> bool:
    users = load_users()
    if username in users:
        return False
    users[username] = {
        "password_hash": hashlib.sha256(password.encode()).hexdigest(),
        "created_at": datetime.now().isoformat(),
        "history": [],
        "api_keys_encrypted": None,  # 先登录再填 key
    }
    save_users(users)
    return True


def login(username: str, password: str) -> dict | None:
    users = load_users()
    user = users.get(username)
    if user and user["password_hash"] == hashlib.sha256(password.encode()).hexdigest():
        return user
    return None


def save_api_keys(username: str, password: str,
                  llm_key: str, llm_url: str, tavily_key: str, model_id: str):
    """加密存储 API keys"""
    users = load_users()
    if username not in users:
        return
    plain = json.dumps({
        "llm_api_key": llm_key,
        "llm_base_url": llm_url or "https://api.deepseek.com",
        "tavily_api_key": tavily_key,
        "model_id": model_id or "deepseek-v4-flash",
    })
    users[username]["api_keys_encrypted"] = _encrypt(plain, password)
    save_users(users)


def get_api_keys(username: str, password: str) -> dict | None:
    """解密并返回用户的 API keys，需提供密码"""
    users = load_users()
    user = users.get(username)
    if not user:
        return None
    # 验证密码
    if user["password_hash"] != hashlib.sha256(password.encode()).hexdigest():
        return None
    encrypted = user.get("api_keys_encrypted")
    if not encrypted:
        return {}
    plain = _decrypt(encrypted, password)
    if plain is None:
        return {}  # 解密失败
    return json.loads(plain)


def update_user(username: str, field: str, value):
    users = load_users()
    if username in users:
        users[username][field] = value
        save_users(users)
