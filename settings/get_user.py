from dotenv import load_dotenv
import os
import asyncio,asyncpg

async def get_users(): 


    load_dotenv()

    DATABASE_URL = os.getenv("DATABASE_URL")

    print("DATABASE_URL:", DATABASE_URL)

    try: 
        info = await asyncpg.connect(DATABASE_URL)


        rows = await info.fetch("SELECT * FROM users;")

        user_info = []
        for row in rows:
            user_info.append(row.get("email"))

        
        print("users:",user_info)


        await info.close()




        return user_info
    

    except Exception as e: 
        print(f"Failed to connect to database: {e}")
        return



    


    



# asyncio.run(get_users())