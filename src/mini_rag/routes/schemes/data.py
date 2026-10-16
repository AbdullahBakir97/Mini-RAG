from pydantic import BaseModel, Field, model_validator


class ProcessRequest(BaseModel):

    file_id: str = Field(pattern=r"^[\w.]+$", max_length=255)
    chunk_size: int = Field(default=1000, gt=0, le=100_000)
    overlap_size: int = Field(default=200, ge=0)

    @model_validator(mode="after")
    def check_overlap_smaller_than_chunk(self):
        if self.overlap_size >= self.chunk_size:
            raise ValueError("overlap_size must be smaller than chunk_size")
        return self
