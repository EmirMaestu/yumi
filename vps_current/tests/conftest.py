"""
Config de pytest. Setea envs dummy ANTES de cualquier import, para que un test
que importe main.py (que en import-time lee os.environ["TELEGRAM_TOKEN"], etc.)
no crashee. Los modulos puros (fx, finance, ...) no necesitan esto.
"""
import os

os.environ.setdefault("TELEGRAM_TOKEN", "test-token")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("ALLOWED_USER_IDS", "0")
os.environ.setdefault("TIMEZONE", "America/Argentina/Buenos_Aires")
