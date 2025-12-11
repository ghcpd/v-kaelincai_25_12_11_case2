# Test runner script for v2 routing service
# Runs all integration tests and generates a summary report

param(
    [string]$Mode = "run",  # "run" or "coverage"
    [string]$TestFilter = "",  # Optional: filter tests by name
    [switch]$Verbose = $false
)

$ErrorActionPreference = "Stop"

Write-Host "=========================================="
Write-Host "v2 Logistics Routing Service – Test Runner"
Write-Host "=========================================="
Write-Host ""

# Ensure venv is activated
if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "ERROR: Virtual environment not found. Run setup.ps1 first."
    exit 1
}

& .\.venv\Scripts\Activate.ps1

# Run tests
$TestArgs = @("tests/", "-v")

if ($Mode -eq "coverage") {
    Write-Host "Running tests with coverage..."
    pip install coverage pytest-cov | Out-Null
    $TestArgs += "--cov=src/logistics", "--cov-report=html", "--cov-report=term"
} else {
    Write-Host "Running tests..."
}

if ($TestFilter) {
    $TestArgs += "-k", $TestFilter
}

if ($Verbose) {
    $TestArgs += "-vv"
}

Write-Host ""
Write-Host "Executing: pytest $($TestArgs -join ' ')"
Write-Host ""

pytest @TestArgs
$TestExitCode = $LASTEXITCODE

Write-Host ""
Write-Host "=========================================="
if ($TestExitCode -eq 0) {
    Write-Host "✓ All tests PASSED"
} else {
    Write-Host "✗ Some tests FAILED (exit code: $TestExitCode)"
}
Write-Host "=========================================="

if ($Mode -eq "coverage") {
    Write-Host ""
    Write-Host "Coverage report generated in: htmlcov/index.html"
}

exit $TestExitCode
