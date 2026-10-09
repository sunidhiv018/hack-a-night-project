import http.server
import socketserver
import os
import urllib.parse

PORT = 3000

class CleanRouteHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path).path
        
        # Route clean paths
        if parsed_path in ['/', '']:
            self.path = '/index.html'
        elif parsed_path in ['/login', '/login/', '/signup', '/signup/', '/users/sign_in']:
            self.path = '/login.html'
        elif parsed_path in ['/dashboard', '/dashboard/']:
            self.path = '/dashboard.html'
        elif parsed_path in ['/transactions', '/transactions/']:
            self.path = '/transactions.html'
        elif parsed_path in ['/forecasts', '/forecasts/']:
            self.path = '/forecasts.html'
        elif not os.path.exists('.' + parsed_path) and os.path.exists('.' + parsed_path + '.html'):
            self.path = parsed_path + '.html'
            
        return super().do_GET()

if __name__ == '__main__':
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), CleanRouteHandler) as httpd:
        print(f"BrokeNoMore Server running on port {PORT} with routing for /, /login, /signup, /dashboard...")
        httpd.serve_forever()
