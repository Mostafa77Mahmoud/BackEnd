from flask import jsonify

def register_root_routes(app):
    """Register root routes for testing."""
    
    @app.route('/')
    def index():
        return jsonify({
            "message": "Sharia Contract Analyzer API",
            "version": "1.0",
            "endpoints": {
                "analysis": "/api/analyze",
                "interaction": "/api/interact",
                "file_search": "/api/file_search/*",
                "health": "/api/file_search/health"
            }
        })
    
    @app.route('/health')
    def health():
        return jsonify({"status": "healthy"})
    
    @app.route('/debug/routes')
    def list_routes():
        """List all registered routes for debugging."""
        routes = []
        for rule in app.url_map.iter_rules():
            routes.append({
                "endpoint": rule.endpoint,
                "methods": list(rule.methods),
                "path": str(rule)
            })
        return jsonify({"routes": routes})
