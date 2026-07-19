# app/db.py
from pymongo import MongoClient

# Local MongoDB
client = MongoClient("mongodb://localhost:27017")

# Access the database
db = client["resume_parser_db"]

users_collection = db["users"]
users_collection.create_index("email", unique=True)
