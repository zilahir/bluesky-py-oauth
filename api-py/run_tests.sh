#!/bin/bash

# Test runner script for atproto OAuth application
# This script runs the test suite with proper configuration

set -e

echo "🧪 Running atproto OAuth test suite..."
echo ""

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "❌ pytest is not installed. Installing test dependencies..."
    pip install pytest pytest-mock
    echo ""
fi

# Run tests
echo "Running tests..."
pytest -v tests/

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ All tests passed!"
else
    echo ""
    echo "❌ Some tests failed. Please review the output above."
    exit 1
fi
