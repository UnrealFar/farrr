
import flask

app = flask.Flask("farrr")

@app.get("/")
def index():
    return flask.render_template("index.html")

app.run(host="0.0.0.0",port=8080)