from typing import Optional, List
from datetime import datetime
from enum import Enum
from fastapi import FastAPI, Body, Form, File, HTTPException, status, UploadFile, Query
from fastapi.responses import Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ConfigDict, BaseModel, Field
from pydantic.functional_validators import BeforeValidator
import aiofiles
from fastapi.middleware.cors import CORSMiddleware

from typing_extensions import Annotated

import motor.motor_asyncio
import constants as constants

client = motor.motor_asyncio.AsyncIOMotorClient(constants.MONGODB_URL)
db = client[constants.DataBaseName]
PyObjectId = Annotated[str, BeforeValidator(str)]

app = FastAPI(title="Restaurant API",
    summary="FastAPI Application to add a ReST API to a MongoDB collection for restaurants.",)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Set this to the domains you want to allow
    allow_credentials=True,
    allow_methods=["*"],  # Set this to the HTTP methods you want to allow
    allow_headers=["*"],  # Set this to the HTTP headers you want to allow
)

app.mount("/static", StaticFiles(directory="static"), name="static")

#Restaurant type
class RestaurantTypeEnum(str, Enum):
    VEG = "Veg"
    NON_VEG = "Non-Veg"
    BOTH = "Both"

class RestaurantModel(BaseModel):
    name: str
    phone_number: str
    restaurant_type: RestaurantTypeEnum
    opening_time: str = Field(..., description="Save Opening Time")
    closing_time: str = Field(..., description="Save Closing Time")
    rating: Optional[float] = Field(default=0.0, ge=0, le=5, description="Rating should be between 0 and 5")
    imageUrl: str
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )
class RestaurantResponseModel(BaseModel):
    name: str
    phone_number: str
    restaurant_type: RestaurantTypeEnum
    opening_time: str = Field(..., description="Save Opening Time")
    closing_time: str = Field(..., description="Save Closing Time")
    rating: Optional[float] = Field(default=0.0, ge=0, le=5, description="Rating should be between 0 and 5")
    imageUrl: str

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
async def addRestaurant(name: str = Form(...),
    phone_number: str = Form(...),
    restaurant_type: RestaurantTypeEnum = Form(...),
    opening_time: str = Form(...),
    closing_time: str = Form(...),
    rating: Optional[float] = Form(None),
    image: UploadFile = File(...),):
    restaurantCollection = db[constants.RestaurantCollectionName]
    restaurant = RestaurantModel(
        name=name,
        phone_number=phone_number,
        restaurant_type=restaurant_type,
        opening_time=opening_time,
        closing_time=closing_time,
        rating=rating,
        imageUrl=f"/static/{name}.jpg",
    )
    async with aiofiles.open(f"static/{restaurant.name}.jpg", "wb") as out_file:
        while content := await image.read(1024):  # async read chunk
            await out_file.write(content)
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

@app.get(
    "/restaurants/search/",
    response_description="Search restaurants by name",
    response_model=RestaurantListing,
    response_model_by_alias=False,
)
async def searchRestaurantByQuery(query: str = Query(..., description="Search query")):
    restaurantCollection = db[constants.RestaurantCollectionName]
    
    # Perform case-insensitive search using regular expression
    search_pattern = {"name": {"$regex": query, "$options": "i"}}
    matching_restaurants = await restaurantCollection.find(search_pattern).to_list(None)

    if not matching_restaurants:
        raise HTTPException(status_code=404, detail=f"No restaurants found matching the query: {query}")
    
    # Convert opening_time and closing_time to string format
    for restaurant in matching_restaurants:
        restaurant['opening_time'] = restaurant['opening_time'].strftime('%I:%M %p')
        restaurant['closing_time'] = restaurant['closing_time'].strftime('%I:%M %p')

    return RestaurantListing(restaurants=matching_restaurants)

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

#Menu Items
class MenuTypeEnum(str, Enum):
    VEG = "Veg"
    NON_VEG = "Non-Veg"

class MenuModel(BaseModel):
    name: str
    restaurantName: str
    menu_type: MenuTypeEnum
    description: str
    price: int
    imageUrl: str
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )
class MenuResponseModel(BaseModel):
    id: Optional[PyObjectId] = None
    name: str
    restaurantName: str
    menu_type: MenuTypeEnum
    description: str
    price: int
    imageUrl: str

class MenuListing(BaseModel):
    menus: List[MenuResponseModel]

@app.get("/")
def read_root():
    return RedirectResponse("/docs")

@app.post("/menu/",
          response_description="Add new menu item",
          response_model=MenuResponseModel,
          status_code=status.HTTP_201_CREATED,
          response_model_by_alias=False
)
async def addMenuItem(name: str = Form(...),
    restaurantName: str = Form(...),
    menu_type: MenuTypeEnum = Form(...),
    description: str = Form(...),
    price: int = Form(...),
    image: UploadFile = File(...),):
    menuCollection = db[constants.RestaurantMenuCollectionName]
    menu = MenuModel(
        name=name,
        restaurantName=restaurantName,
        description=description,
        menu_type=menu_type,
        price=price,
        imageUrl=f"/static/{restaurantName}_{name}.jpg",
    )
    async with aiofiles.open(f"static/{menu.restaurantName}_{menu.name}.jpg", "wb") as out_file:
        while content := await image.read(1024):  # async read chunk
            await out_file.write(content)
    newMenu = await menuCollection.insert_one(menu.model_dump(by_alias=True, exclude=["id"]))
    response = await menuCollection.find_one({"_id": newMenu.inserted_id})
    response['id'] = str(response.pop('_id'))
    return response

@app.get(
    "/menu/{name}",
    response_description="List all restaurant menu items",
    response_model=MenuListing,
    response_model_by_alias=False,
)
async def listRestaurantItems(name: str):
    menuCollection = db[constants.RestaurantMenuCollectionName]
    if (menuListings := await menuCollection.find({"restaurantName": name}).to_list(None)) is not None:
        for menu in menuListings:
            menu['id'] = str(menu.pop('_id'))
        return MenuListing(menus=menuListings)
    
    raise HTTPException(status_code=404, detail=f"Restaurant {name} not found")

@app.delete("/menu/{restaurant_name}/{menu_name}",
            response_description="Delete a menu item from a restaurant by name",
            status_code=status.HTTP_204_NO_CONTENT
            )
async def delete_menu_item_from_restaurant_by_name(restaurant_name: str, menu_name: str):
    menuCollection = db[constants.RestaurantMenuCollectionName]
    delete_result = await menuCollection.delete_one({"name": menu_name, "restaurantName": restaurant_name})
    if delete_result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Menu item not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# rating models
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
