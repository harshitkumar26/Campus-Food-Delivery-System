from typing import Optional, List
from datetime import datetime
from enum import Enum
from fastapi import FastAPI, Body, Form, HTTPException, status, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response, RedirectResponse
from pydantic import ConfigDict, BaseModel, Field
from pydantic.functional_validators import BeforeValidator
import aiofiles
from typing_extensions import Annotated

import motor.motor_asyncio
import constants as constants

client = motor.motor_asyncio.AsyncIOMotorClient(constants.MONGODB_URL)
db = client[constants.DataBaseName]
PyObjectId = Annotated[str, BeforeValidator(str)]

app = FastAPI(title="Menu API",
    summary="FastAPI Application to add a ReST API to a MongoDB collection for menu.",)

app.mount("/static", StaticFiles(directory="static"), name="static")

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