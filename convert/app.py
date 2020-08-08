import os
import logging
from flask import Flask, request, send_file
from pantomime import FileName, normalize_mimetype, mimetype_extension

from convert.converter import Converter, ConversionFailure, SystemFailure
from convert.converter import CONVERT_DIR
from convert.formats import load_mime_extensions

PDF = "application/pdf"
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger("convert")
extensions = load_mime_extensions()
converter = Converter()
app = Flask("convert")
log.debug("INIT")


@app.route("/")
@app.route("/healthz")
@app.route("/health/live")
def check_health():
    try:
        desktop = converter.connect()
        if desktop is None:
            return ("BUSY", 500)
        return ("OK", 200)
    except Exception:
        log.exception("Converter is not healthy.")
        return ("DEAD", 500)


@app.route("/health/ready")
def check_ready():
    if converter.is_locked:
        return ("BUSY", 503)
    return ("OK", 200)


@app.route("/reset")
def reset():
    converter.kill()
    return ("OK", 200)


@app.route("/convert", methods=["POST"])
def convert():
    upload_file = None
    if not converter.lock():
        return ("BUSY", 503)
    try:
        timeout = int(request.args.get("timeout", 7200))
        for upload in request.files.values():
            file_name = FileName(upload.filename)
            mime_type = normalize_mimetype(upload.mimetype)
            if not file_name.has_extension:
                file_name.extension = extensions.get(mime_type)
            if not file_name.has_extension:
                file_name.extension = mimetype_extension(mime_type)
            upload_file = os.path.join(CONVERT_DIR, file_name.safe())
            log.info("PDF convert: %s [%s]", upload_file, mime_type)
            upload.save(upload_file)
            out_file = converter.convert_file(upload_file, timeout)
            return send_file(out_file, mimetype=PDF, attachment_filename="output.pdf")
        return ("No file uploaded", 400)
    except ConversionFailure as ex:
        converter.abort()
        return (str(ex), 400)
    except (SystemFailure, Exception) as ex:
        converter.abort()
        log.warn("Error: %s", ex)
        return (str(ex), 500)
    finally:
        converter.clear()
