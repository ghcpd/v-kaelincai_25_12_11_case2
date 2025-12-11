# Setup script for v2 routing service
# This script initializes the virtual environment and installs dependencies

Write-Host "Setting up v2 Logistics Routing Service..."

# Create virtual environment
Write-Host "Creating virtual environment..."
if (-not (Test-Path ".venv")) {
    python -m venv .venv
} else {
    Write-Host "Virtual environment already exists."
}

# Activate virtual environment
Write-Host "Activating virtual environment..."
& .\.venv\Scripts\Activate.ps1

# Install dependencies
Write-Host "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

Write-Host ""
Write-Host "Setup complete!"
Write-Host "To activate the environment in the future, run: .\.venv\Scripts\Activate.ps1"
Write-Host "To run tests, run: pytest"
