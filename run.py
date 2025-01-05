import main
import uvicorn

app = main.app
uvicorn.run(app, host="0.0.0.0")

