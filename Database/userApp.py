from typing import Optional, List
from datetime import datetime
from enum import Enum
from fastapi import FastAPI, Body, Form, HTTPException, status, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response, RedirectResponse
from pydantic import ConfigDict, BaseModel, Field
from pydantic.functional_validators import BeforeValidator
from typing_extensions import Annotated

import motor.motor_asyncio
import constants as constants

client = motor.motor_asyncio.AsyncIOMotorClient(constants.MONGODB_URL)
db = client[constants.DataBaseName]
PyObjectId = Annotated[str, BeforeValidator(str)]

app = FastAPI(title="User API",
    summary="FastAPI Application to add a ReST API to a MongoDB collection for users.",)

app.mount("/static", StaticFiles(directory="static"), name="static")

class UserModel(BaseModel):
    email: str
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )
class UserResponseModel(BaseModel):
    id: Optional[PyObjectId] = None
    email: str

class UserListing(BaseModel):
    menus: List[UserResponseModel]

@app.get("/")
def read_root():
    return RedirectResponse("/docs")

@app.post("/user/",
          response_description="Add new user",
          response_model=UserResponseModel,
          status_code=status.HTTP_201_CREATED,
          response_model_by_alias=False
)
async def addUser(email: str = Form(...),):
    userCollection = db[constants.UsersCollectionName]
    menu = UserModel(
        email=email,
    )
    newUser = await userCollection.insert_one(menu.model_dump(by_alias=True, exclude=["id"]))
    response = await userCollection.find_one({"_id": newUser.inserted_id})
    response['id'] = str(response.pop('_id'))
    return response