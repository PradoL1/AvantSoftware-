"""Punto de entrada para desarrollo:  python run.py"""

import os

from app import create_app

app = create_app(os.environ.get("FLASK_ENV", "development"))

if __name__ == "__main__":
    # host 0.0.0.0 para poder probar el escaneo de codigo de barras desde el
    # celular, conectado a la misma red que la PC.
    app.run(host="0.0.0.0", port=5000, debug=app.config["DEBUG"])
