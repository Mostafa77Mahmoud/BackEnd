"""
Admin Routes

Administrative endpoints for rules management and request tracing.
"""

import datetime
import logging
import os
import json
from flask import Blueprint, request, jsonify, send_file

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__)

TRACES_DIR = "traces"


@admin_bp.route('/health', methods=['GET'])
def admin_health():
    """Admin health check."""
    return jsonify({
        "service": "Shariaa Analyzer Admin",
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat()
    }), 200


@admin_bp.route('/rules', methods=['GET'])
def get_rules():
    """Get rules."""
    return jsonify({"message": "Get rules endpoint", "status": "coming_soon"})


@admin_bp.route('/rules', methods=['POST'])
def create_rule():
    """Create rule."""
    return jsonify({"message": "Create rule endpoint", "status": "coming_soon"})


@admin_bp.route('/rules/<rule_id>', methods=['PUT'])
def update_rule(rule_id):
    """Update rule."""
    return jsonify({"message": f"Update rule {rule_id} endpoint", "status": "coming_soon"})


@admin_bp.route('/rules/<rule_id>', methods=['DELETE'])
def delete_rule(rule_id):
    """Delete rule."""
    return jsonify({"message": f"Delete rule {rule_id} endpoint", "status": "coming_soon"})


def check_debug_mode():
    """Check if debug/development mode is enabled for trace access."""
    from flask import current_app
    debug_enabled = current_app.config.get('DEBUG', False)
    trace_access_key = request.headers.get('X-Trace-Access-Key') or request.args.get('access_key')
    expected_key = current_app.config.get('TRACE_ACCESS_KEY')
    
    if debug_enabled:
        return True
    if expected_key and trace_access_key == expected_key:
        return True
    return False


@admin_bp.route('/traces', methods=['GET'])
def list_traces():
    """List all trace files with metadata. Requires debug mode or access key."""
    if not check_debug_mode():
        return jsonify({"error": "Trace access not permitted in production without access key"}), 403
    
    try:
        if not os.path.exists(TRACES_DIR):
            return jsonify({"traces": [], "count": 0, "message": "No traces directory found"}), 200
        
        trace_files = []
        for filename in os.listdir(TRACES_DIR):
            if filename.endswith('.json'):
                filepath = os.path.join(TRACES_DIR, filename)
                stat = os.stat(filepath)
                
                trace_info = {
                    "filename": filename,
                    "size_bytes": stat.st_size,
                    "created_at": datetime.datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified_at": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()
                }
                
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        trace_data = json.load(f)
                        trace_info["trace_id"] = trace_data.get("trace_id")
                        trace_info["endpoint"] = trace_data.get("metadata", {}).get("endpoint")
                        trace_info["session_id"] = trace_data.get("metadata", {}).get("session_id")
                        summary = trace_data.get("summary", {})
                        trace_info["duration_seconds"] = summary.get("total_duration_seconds")
                        trace_info["status"] = summary.get("status")
                        trace_info["steps_count"] = summary.get("total_steps")
                        trace_info["api_calls_count"] = summary.get("total_api_calls")
                except Exception:
                    pass
                
                trace_files.append(trace_info)
        
        trace_files.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return jsonify({
            "traces": trace_files,
            "count": len(trace_files),
            "traces_dir": TRACES_DIR
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing traces: {e}")
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/traces/<filename>', methods=['GET'])
def get_trace(filename):
    """Get a specific trace file content. Requires debug mode or access key."""
    if not check_debug_mode():
        return jsonify({"error": "Trace access not permitted in production without access key"}), 403
    
    try:
        if not filename.endswith('.json'):
            filename = f"{filename}.json"
        
        filepath = os.path.join(TRACES_DIR, filename)
        
        if not os.path.exists(filepath):
            return jsonify({"error": f"Trace file not found: {filename}"}), 404
        
        with open(filepath, 'r', encoding='utf-8') as f:
            trace_data = json.load(f)
        
        return jsonify(trace_data), 200
        
    except Exception as e:
        logger.error(f"Error reading trace {filename}: {e}")
        return jsonify({"error": str(e)}), 500


@admin_bp.route('/traces/<filename>/download', methods=['GET'])
def download_trace(filename):
    """Download a trace file. Requires debug mode or access key."""
    if not check_debug_mode():
        return jsonify({"error": "Trace access not permitted in production without access key"}), 403
    
    try:
        if not filename.endswith('.json'):
            filename = f"{filename}.json"
        
        filepath = os.path.join(TRACES_DIR, filename)
        
        if not os.path.exists(filepath):
            return jsonify({"error": f"Trace file not found: {filename}"}), 404
        
        return send_file(
            filepath,
            mimetype='application/json',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        logger.error(f"Error downloading trace {filename}: {e}")
        return jsonify({"error": str(e)}), 500