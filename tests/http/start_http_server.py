import http.server
import socketserver
import logging

PORT = 8080
Handler = http.server.SimpleHTTPRequestHandler

with socketserver.TCPServer(("", PORT), Handler) as serv:
    logging.info("serving at port {}".format(PORT))
    serv.serve_forever()