from typing import Optional, List
from datetime import datetime
from enum import Enum
from fastapi import FastAPI, Body, File, HTTPException, status, UploadFile
from fastapi.responses import Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ConfigDict, BaseModel, Field
from pydantic.functional_validators import BeforeValidator
from bson import Binary

from typing_extensions import Annotated

import motor.motor_asyncio
import constants as constants

client = motor.motor_asyncio.AsyncIOMotorClient(constants.MONGODB_URL)
db = client[constants.DataBaseName]
PyObjectId = Annotated[str, BeforeValidator(str)]

app = FastAPI(title="Restaurant API",
    summary="FastAPI Application to add a ReST API to a MongoDB collection for restaurants.",)

app.mount("/static", StaticFiles(directory="static"), name="static")

class RestaurantTypeEnum(str, Enum):
    VEG = "Veg"
    NON_VEG = "Non-Veg"
    BOTH = "Both"

class ImageModel(BaseModel):
    file_name: str
    content_type: str
    image_data: bytes

class RestaurantModel(BaseModel):
    name: str
    phone_number: str
    restaurant_type: RestaurantTypeEnum
    opening_time: str = Field(..., description="Save Opening Time")
    closing_time: str = Field(..., description="Save Closing Time")
    rating: Optional[float] = Field(default=0.0, ge=0, le=5, description="Rating should be between 0 and 5")
    image: Optional[ImageModel]
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )

class RestaurantListing(BaseModel):
    restaurants: List[RestaurantModel]

@app.get("/")
def read_root():
    return RedirectResponse("/docs")

@app.post("/restaurants/",
          response_description="Add new restaurant",
          response_model=RestaurantModel,
          status_code=status.HTTP_201_CREATED,
          response_model_by_alias=False
)
async def addRestaurant(restaurant: RestaurantModel = Body(...), image: UploadFile = File(None)):
    restaurantCollection = db[constants.RestaurantCollectionName]
    if image:
        content = await image.read()
        restaurant.image = ImageModel(
            file_name=image.filename,
            content_type=image.content_type,
            image_data=content,
        )
    restaurant.opening_time = datetime.strptime(restaurant.opening_time, '%I:%M %p')
    restaurant.closing_time = datetime.strptime(restaurant.closing_time, '%I:%M %p')
    newRestaurant = await restaurantCollection.insert_one(restaurant.model_dump(by_alias=True, exclude=["id"]))
    response = await restaurantCollection.find_one({"_id": newRestaurant.inserted_id})
    response['opening_time'] = response['opening_time'].strftime('%I:%M %p')
    response['closing_time'] = response['closing_time'].strftime('%I:%M %p')
    return response

@app.get(
    "/restaurants/",
    response_description="List all restaurants",
    response_model=RestaurantListing,
    response_model_by_alias=False,
)
async def listRestaurants():
    restaurantCollection = db[constants.RestaurantCollectionName]
    restaurantListings = await restaurantCollection.find().to_list(None)
    for restaurant in restaurantListings:
        restaurant['opening_time'] = restaurant['opening_time'].strftime('%I:%M %p')
        restaurant['closing_time'] = restaurant['closing_time'].strftime('%I:%M %p')
    return RestaurantListing(restaurants=restaurantListings)

@app.get(
    "/restaurants/{name}",
    response_description="Find restaurant by name",
    response_model=RestaurantModel,
    response_model_by_alias=False,
)
async def searchRestaurantByName(name: str):
    restaurantCollection = db[constants.RestaurantCollectionName]

    if (restaurant := await restaurantCollection.find_one({"name": name})) is not None:
        restaurant['opening_time'] = restaurant['opening_time'].strftime('%I:%M %p')
        restaurant['closing_time'] = restaurant['closing_time'].strftime('%I:%M %p')
        return restaurant
    
    raise HTTPException(status_code=404, detail=f"Restaurant {name} not found")

@app.delete(
    "/restaurants/{name}",
    response_description="Delete restaurant by name"
)
async def deleteRestaurant(name):
    restaurantCollection = db[constants.RestaurantCollectionName]
    deleteRes = await restaurantCollection.delete_one({"name":name})
    if deleteRes.deleted_count == 1:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise HTTPException(status_code=404, detail=f"Restaurant {name} not found")