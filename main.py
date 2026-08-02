from app.main import app

if __name__ == "__main__":
    import uvicorn

    from app.config import HOST, PORT

    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
