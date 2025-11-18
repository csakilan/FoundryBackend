from fastapi import APIRouter


costs = APIRouter(prefix="/canvas")


@costs.get("/costs_estimate")
async def get_costs_estimate():

    print("hello world")