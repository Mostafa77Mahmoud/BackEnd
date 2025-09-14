# Route Docstrings Collection

## Analysis Split - Route Documentation

### analysis_upload.py

#### POST /analyze
```python
def analyze_contract():
    """
    Analyze contract for Sharia compliance.
    
    Accepts file uploads or direct text input for analysis.
    Processes documents through AI analysis pipeline.
    Returns analysis results with term-by-term breakdown.
    """
```

### analysis_terms.py

#### GET /analysis/<analysis_id>
```python
def get_analysis_results(analysis_id):
    """Get analysis results by ID."""
```

#### GET /session/<session_id>
```python
def get_session_details(session_id):
    """Fetch session details including contract info."""
```

#### GET /terms/<session_id>
```python
def get_session_terms(session_id):
    """Retrieve all terms for a session."""
```

### analysis_session.py

#### GET /sessions
```python
def get_sessions():
    """List recent sessions with pagination."""
```

#### GET /history
```python
def get_analysis_history():
    """Retrieve analysis history."""
```

### analysis_admin.py

#### GET /statistics
```python
def get_statistics():
    """Provide system statistics."""
```

#### GET /stats/user
```python
def get_user_stats():
    """Provide user-specific statistics."""
```

#### POST /feedback/expert
```python
def submit_expert_feedback():
    """Submit expert feedback on analysis."""
```

#### GET /health
```python
def health_check():
    """Health check endpoint."""
```

### analysis_generation.py

#### GET /preview_contract/<session_id>/<contract_type>
```python
def preview_contract(session_id, contract_type):
    """Generate PDF preview for modified or marked contracts."""
```

#### GET /download_pdf_preview/<session_id>/<contract_type>
```python
def download_pdf_preview(session_id, contract_type):
    """Proxy PDF downloads from Cloudinary."""
```

## Summary

- **Total Routes**: 12 endpoints preserved exactly from original analysis.py
- **All docstrings maintained** during the split process
- **Clear functional grouping** achieved through module separation
- **API contract preservation**: No changes to external interfaces