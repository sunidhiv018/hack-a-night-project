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
        elif parsed_path in ['/savings', '/savings/']:
            self.path = '/savings.html'
        elif parsed_path in ['/time-machine', '/time-machine/']:
            self.path = '/time-machine.html'
        elif parsed_path in ['/reports', '/reports/']:
            self.path = '/reports.html'
        elif parsed_path in ['/import', '/import/']:
            self.path = '/import.html'
        elif parsed_path in ['/chat', '/chat/', '/milo', '/milo/']:
            self.path = '/chat.html'

        elif not os.path.exists('.' + parsed_path) and os.path.exists('.' + parsed_path + '.html'):
            self.path = parsed_path + '.html'
            
        return super().do_GET()

if __name__ == '__main__':
    # Ensure current working directory is the frontend directory
    frontend_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(frontend_dir)
    
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), CleanRouteHandler) as httpd:
        print(f"BrokeNoMore Server running on port {PORT} (serving {frontend_dir})...")
        httpd.serve_forever()
