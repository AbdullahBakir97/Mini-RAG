import os
import re

from fastapi import UploadFile

from mini_rag.core.errors import FileTooLarge, UnsupportedFileType

from .BaseController import BaseController
from .ProjectController import ProjectController


class DataController(BaseController):
    def __init__(self):
        super().__init__()
        self.size_scale = 1048576 # convert MB to bytes

    def validate_uploaded_file(self, file: UploadFile):

        if file.content_type not in self.app_settings.FILE_ALLOWED_TYPES:
            raise UnsupportedFileType()

        if file.size is not None and file.size > self.app_settings.FILE_MAX_SIZE * self.size_scale:
            raise FileTooLarge()


    def generate_unique_file_path(self, orig_file_name: str, project_id: str):

        random_key = self.generate_random_string()
        project_path = ProjectController().get_project_path(project_id=project_id)

        cleaned_file_name = self.get_clean_file_name(
            orig_file_name=orig_file_name
        )

        new_file_path = os.path.join(
            project_path,
            random_key + "_" + cleaned_file_name
        )

        while os.path.exists(new_file_path):
            random_key = self.generate_random_string()
            new_file_path = os.path.join(
                project_path,
                random_key + "_" + cleaned_file_name
            )

        return new_file_path, random_key + "_" + cleaned_file_name

    def get_clean_file_name(self, orig_file_name: str):

        # replace spaces with underscore
        cleaned_file_name = orig_file_name.strip().replace(" ", "_")

        # remove any special characters except underscore and .
        cleaned_file_name = re.sub(r'[^\w.]', '', cleaned_file_name)

        return cleaned_file_name
