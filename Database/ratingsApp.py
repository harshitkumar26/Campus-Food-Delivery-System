from typing import Optional, List
from datetime import datetime
from enum import Enum
from fastapi import FastAPI, Body, HTTPException, status
from fastapi.responses import Response, RedirectResponse
from pydantic import ConfigDict, BaseModel, Field
from pydantic.functional_validators import BeforeValidator

from typing_extensions import Annotated

import motor.motor_asyncio
import constants as constants
import restaurantApp as restaurant

client = motor.motor_asyncio.AsyncIOMotorClient(constants.MONGODB_URL)
db = client[constants.DataBaseName]
PyObjectId = Annotated[str, BeforeValidator(str)]

app = FastAPI(title="rating API",
    summary="FastAPI Application to add a ReST API to a MongoDB collection for ratings.",)

class ratingModel(BaseModel):
    rating: Optional[float] = Field(..., ge=0, le=5, description="Rating should be between 0 and 5")
    restaurantName: str = Field(..., description="name of restaurant")
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )

class ratingResponseModel(BaseModel):
    avgRating: Optional[float] = Field(..., ge=0, le=5, description="Rating should be between 0 and 5")
    restaurantName: str = Field(..., description="name of restaurant")
    numRatings: float = Field(..., description="Total number of people who have rated the restaurant")
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )

class ratingListing(BaseModel):
    ratings: List[ratingModel]

@app.get("/")
def read_root():
    return RedirectResponse("/docs")

@app.post("/newRating/",
          response_description="Add new rating",
          response_model=ratingResponseModel,
          status_code=status.HTTP_201_CREATED,
          response_model_by_alias=False
)
async def addNewRating(rating: ratingModel = Body(...)):
    ratingCollection = db[constants.RatingsCollectionName]

    restaurantCheck = await ratingCollection.find_one({"restaurantName": rating.restaurantName})

    if restaurantCheck:
        # If data already exists, update the average rating and increase the number of ratings
        new_avg_rating = ((restaurantCheck['avgRating'] * restaurantCheck['numRatings']) + rating.avgRating) / (restaurantCheck['numRatings'] + 1)
        updated_data = {
            "$set": {
                "avgRating": new_avg_rating,
                "numRatings": restaurantCheck['numRatings'] + 1
            }
        }

        await ratingCollection.update_one({"restaurantName": rating.restaurantName}, updated_data)
        response_data = await ratingCollection.find_one({"restaurantName": rating.restaurantName})

    else:
        # If data doesn't exist, insert new data
        new_data = {
            "restaurantName": rating.restaurantName,
            "avgRating": rating.rating,
            "numRatings": 1
        }

        result = await ratingCollection.insert_one(new_data)
        response_data = await ratingCollection.find_one({"_id": result.inserted_id})

    return response_data

@app.get(
    "/avgRating/{name}",
    response_description="Fetch average rating",
    response_model=ratingResponseModel,
    response_model_by_alias=False,
)
async def fetch_avgratings(name: str):
    ratingCollection = db[constants.RatingsCollectionName]

    restaurant_data = await ratingCollection.find_one({"restaurantName": name})

    if restaurant_data:
        avg_rating = restaurant_data["avgRating"]
        num_ratings = restaurant_data["numRatings"]

        response_data = {
            "avgRating": avg_rating,
            "restaurantName": name,
            "numRatings": num_ratings,
        }

        return response_data
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Restaurant with name '{name}' not found",
        )