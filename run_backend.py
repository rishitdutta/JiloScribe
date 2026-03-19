from src.router import app, global_state
from src.config import Settings
import os
import dotenv


def main() -> None:
    import uvicorn

    if os.path.exists(".env"):
        print("loading dotenv...")
        dotenv.load_dotenv(dotenv_path=".env")
    global_state.settings = Settings()
    uvicorn.run(
        app,
        host=global_state.settings.host,
        port=global_state.settings.port,
    )


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    main()
