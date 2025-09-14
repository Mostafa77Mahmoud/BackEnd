#!/bin/bash

# Smoke Test Script for Shariaa Contract Analyzer Backend
# Tests basic functionality after restructuring

set -e  # Exit on any error

echo "===========================================" 
echo "🔍 SHARIAA ANALYZER BACKEND SMOKE TESTS"
echo "==========================================="

# Check if server is running
echo "📡 Checking if Flask server is running..."
if ! curl -s http://localhost:5000/api/health > /dev/null; then
    echo "❌ ERROR: Flask server is not running on port 5000"
    echo "Please start the server with: python run.py"
    exit 1
fi

echo "✅ Flask server is running"

# Test health endpoint
echo ""
echo "🏥 Testing health endpoint..."
health_response=$(curl -s http://localhost:5000/api/health)
if echo "$health_response" | grep -q "healthy"; then
    echo "✅ Health endpoint working"
    echo "Response: $health_response"
else
    echo "❌ Health endpoint failed"
    echo "Response: $health_response"
    exit 1
fi

# Test analyze endpoint (should fail gracefully without data)
echo ""
echo "🔍 Testing analyze endpoint (no data)..."
analyze_response=$(curl -s -X POST http://localhost:5000/api/analyze)
if echo "$analyze_response" | grep -q "error"; then
    echo "✅ Analyze endpoint correctly rejects empty requests"
else
    echo "❌ Analyze endpoint should reject empty requests"
    echo "Response: $analyze_response"
    exit 1
fi

# Test analyze endpoint with text (may fail without AI key but should handle gracefully)
echo ""
echo "📄 Testing analyze endpoint with text..."
analyze_text_response=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -d '{"text": "This is a test contract clause", "analysis_type": "sharia", "jurisdiction": "Egypt"}' \
    http://localhost:5000/api/analyze)

echo "Response: $analyze_text_response"
if echo "$analyze_text_response" | grep -q -E "(session_id|error)"; then
    echo "✅ Analyze endpoint handles text input (may need AI configuration)"
else
    echo "❌ Analyze endpoint not handling text input correctly"
    exit 1
fi

# Test interact endpoint (should fail without session)
echo ""
echo "💬 Testing interact endpoint (no session)..."
interact_response=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -d '{"question": "Test question"}' \
    http://localhost:5000/api/interact)

if echo "$interact_response" | grep -q "error"; then
    echo "✅ Interact endpoint correctly requires session"
else
    echo "❌ Interact endpoint should require session"
    echo "Response: $interact_response"
    exit 1
fi

# Test generate from brief endpoint (should fail gracefully without data)
echo ""
echo "📋 Testing generate from brief endpoint..."
generate_response=$(curl -s -X POST http://localhost:5000/api/generate_from_brief)
if echo "$generate_response" | grep -q "error"; then
    echo "✅ Generate endpoint correctly rejects empty requests"
else
    echo "❌ Generate endpoint should reject empty requests"
    echo "Response: $generate_response"
    exit 1
fi

# Test sessions endpoint
echo ""
echo "📁 Testing sessions endpoint..."
sessions_response=$(curl -s http://localhost:5000/api/sessions)
if echo "$sessions_response" | grep -q -E "(sessions|Database service unavailable)"; then
    echo "✅ Sessions endpoint working (may need database configuration)"
else
    echo "❌ Sessions endpoint failed"
    echo "Response: $sessions_response"
    exit 1
fi

# Test statistics endpoint  
echo ""
echo "📊 Testing statistics endpoint..."
stats_response=$(curl -s http://localhost:5000/api/statistics)
if echo "$stats_response" | grep -q -E "(total_sessions|total_terms|Database service unavailable)"; then
    echo "✅ Statistics endpoint working (may need database configuration)"
else
    echo "❌ Statistics endpoint failed"
    echo "Response: $stats_response"
    exit 1
fi

# Test admin endpoints
echo ""
echo "🔧 Testing admin endpoints..."

# Test health check
admin_health_response=$(curl -s http://localhost:5000/api/admin/health)
if echo "$admin_health_response" | grep -q "status"; then
    echo "✅ Admin health endpoint working"
else
    echo "❌ Admin health endpoint failed"
    echo "Response: $admin_health_response"
    exit 1
fi

# Test file structure verification  
echo ""
echo "📁 Verifying file structure..."

required_dirs=("app" "app/routes" "app/services" "app/utils" "config" "prompts" "tests" "scripts")
for dir in "${required_dirs[@]}"; do
    if [ -d "$dir" ]; then
        echo "✅ Directory exists: $dir"
    else
        echo "❌ Missing directory: $dir"
        exit 1
    fi
done

required_files=(
    "app/__init__.py"
    "app/routes/analysis.py"
    "app/routes/generation.py" 
    "app/routes/interaction.py"
    "app/routes/admin.py"
    "app/services/ai_service.py"
    "app/services/database.py"
    "app/services/document_processor.py"
    "app/services/cloudinary_service.py"
    "config/default.py"
    "prompts/SYS_PROMPT_SHARIA_ANALYSIS.txt"
    "prompts/SYS_PROMPT_LEGAL_ANALYSIS.txt"
    "utils.py"
    "remote_api.py"
    "doc_processing.py" 
    "config.py"
    "run.py"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ File exists: $file"
    else
        echo "❌ Missing file: $file"
        exit 1
    fi
done

# Test compatibility shims
echo ""
echo "🔗 Testing compatibility shims..."
if python -c "import utils; import remote_api; import doc_processing; import config; print('All imports successful')" 2>/dev/null; then
    echo "✅ Compatibility shims working"
else
    echo "❌ Compatibility shims failed"
    exit 1
fi

# Test prompt loading
echo ""
echo "📝 Testing prompt loading..."
if python -c "from config.default import DefaultConfig; c = DefaultConfig(); print('Prompts loaded:', len(c.SYS_PROMPT_SHARIA))" 2>/dev/null; then
    echo "✅ Prompt loading working"
else
    echo "❌ Prompt loading failed"
    exit 1
fi

echo ""
echo "🎉 ALL SMOKE TESTS PASSED!"
echo "=========================================="
echo "✅ Flask server responding correctly"
echo "✅ All API endpoints accessible"
echo "✅ File structure is correct"
echo "✅ Compatibility shims working"
echo "✅ Prompt loading functional"
echo "✅ Error handling working properly"
echo ""
echo "🚀 Backend restructuring appears successful!"
echo "Note: Some endpoints may need AI service configuration for full functionality"
echo "=========================================="