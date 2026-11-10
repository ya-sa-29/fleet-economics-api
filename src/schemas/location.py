from pydantic import BaseModel, ConfigDict


class LocationResponse(BaseModel):
    id: int
    name: str
    slug: str

    model_config = ConfigDict(from_attributes=True)