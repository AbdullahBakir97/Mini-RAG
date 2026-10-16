import os
import secrets
import string

from mini_rag.helpers.config import get_settings


class BaseController:

    def __init__(self):
        self.app_settings = get_settings()
        # src/ (the uploads folder moves to a FILES_DIR setting later)
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.file_dir = os.path.join(
            self.base_dir,
            "assets/files"
        )

    def generate_random_string(self, length: int=12):
        alphabet = string.ascii_lowercase + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
