# PowerShell Make Script for Jeeves Project

# Stop on any error
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Test-LastExitCode {
    param(
        [string]$Action = "Previous command"
    )
    if ($LASTEXITCODE -ne 0) {
        Write-Host "$Action failed with exit code $LASTEXITCODE" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

Write-Host "Starting deployment..." -ForegroundColor Green

function Get-EnvVariables {
    Write-Host "Reading environment variables..." -ForegroundColor Green
    $envVars = @{}
    if (Test-Path .env) {
        Get-Content .env | ForEach-Object {
            if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
                $name = $matches[1].Trim()
                $value = $matches[2].Trim()
                $envVars[$name] = $value
            }
        }
    } else {
        Write-Host "Warning: .env file not found!" -ForegroundColor Yellow
        exit 1
    }
    return $envVars
}

function Install-LocalDependencies {
    Write-Host "Installing Python dependencies locally..." -ForegroundColor Green

    if (-not (Test-Path venv)) {
        Write-Host "Creating new virtual environment..." -ForegroundColor Green
        python -m venv venv
    }

    # Install all requirements except tgcrypto
    Get-Content requirements.txt | Where-Object { $_ -notmatch 'tgcrypto' } | Set-Content requirements.local.txt
    .\venv\Scripts\pip install -r requirements.local.txt
    Remove-Item requirements.local.txt

    # Install development dependencies
    .\venv\Scripts\pip install pytest pytest-asyncio isort black

    Write-Host "Dependencies installed successfully!" -ForegroundColor Green
}

function Install-RemoteDependencies {
    param (
        [Parameter(Mandatory=$true)]
        [string]$RemoteHost,
        [Parameter(Mandatory=$true)]
        [string]$RemoteUser
    )

    Write-Host "Installing Python dependencies on remote host..." -ForegroundColor Green

    $commands = @(
        'cd /home/jeeves',
        'sudo -u jeeves python3 -m venv venv',
        'sudo -u jeeves venv/bin/pip install -r requirements.txt'
    ) -join ' && '

    ssh "${RemoteUser}@${RemoteHost}" $commands
}

function Format-Code {
    Write-Host "Formatting code..." -ForegroundColor Green
    .\venv\Scripts\isort jeeves tests
    .\venv\Scripts\black jeeves tests
}

function Run-Tests {
    Write-Host "Installing dependencies and running tests..." -ForegroundColor Green
    Install-LocalDependencies
    Format-Code
    .\venv\Scripts\python -m pytest -x --ff
}

function Setup-Logs {
    param (
        [Parameter(Mandatory=$true)]
        [string]$RemoteHost,
        [Parameter(Mandatory=$true)]
        [string]$RemoteUser
    )

    Write-Host "Setting up log directory on remote host..." -ForegroundColor Green

    $commands = @(
        'sudo mkdir -p /var/log/jeeves',
        'sudo chown -R jeeves:jeeves /var/log/jeeves',
        'sudo chmod -R 755 /var/log/jeeves',
        'sudo touch /var/log/jeeves/app.log /var/log/jeeves/error.log',
        'sudo chown jeeves:jeeves /var/log/jeeves/app.log /var/log/jeeves/error.log'
    ) -join ' && '

    ssh "${RemoteUser}@${RemoteHost}" $commands
}

function Deploy-Files {
    param (
        [Parameter(Mandatory=$true)]
        [string]$RemoteHost,
        [Parameter(Mandatory=$true)]
        [string]$RemoteUser
    )

    Write-Host "Deploying application files..." -ForegroundColor Green

    # First clean up the remote directory
    ssh "${RemoteUser}@${RemoteHost}" @'
        sudo rm -rf /home/jeeves/jeeves
        sudo mkdir -p /home/jeeves
'@
    Test-LastExitCode "Cleaning remote directory"

    # Clean up __pycache__ directories locally
    Get-ChildItem -Path "./jeeves" -Filter "__pycache__" -Recurse | Remove-Item -Recurse -Force

    # Create and prepare temp directory
    $tempDir = Join-Path $env:TEMP "ai_sales_deploy"
    Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path $tempDir | Out-Null

    # Copy files excluding tests
    Get-ChildItem -Path "./jeeves" -Recurse |
        Where-Object {
            -not $_.PSIsContainer -and
            -not $_.Name.EndsWith("_test.py") -and
            -not $_.FullName.Contains("tests") -and
            -not $_.FullName.Contains("script_tests")
        } |
        ForEach-Object {
            $relativePath = $_.FullName.Substring((Get-Location).Path.Length + 1)
            $targetPath = Join-Path $tempDir $relativePath
            $targetDir = Split-Path -Parent $targetPath
            if (-not (Test-Path $targetDir)) {
                New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
            }
            Copy-Item $_.FullName -Destination $targetPath
        }

    # Deploy files
    Write-Host "`nCopying files to server..." -ForegroundColor Green
    scp requirements.txt "${RemoteUser}@${RemoteHost}:/home/jeeves/"
    Test-LastExitCode "Copying requirements.txt"

    # Copy the entire jeeves directory structure
    scp -r "${tempDir}/jeeves" "${RemoteUser}@${RemoteHost}:/home/jeeves/"
    Test-LastExitCode "Copying application files"

    # Set permissions
    ssh "${RemoteUser}@${RemoteHost}" 'sudo chown -R jeeves:jeeves /home/jeeves'
    Test-LastExitCode "Setting permissions"

    # Verify deployment
    ssh "${RemoteUser}@${RemoteHost}" @'
        echo "Verifying deployment structure:"
        ls -la /home/jeeves/jeeves
        echo -e "\nVerifying specific files:"
        test -f /home/jeeves/jeeves/api/handlers/testing.py && echo "testing.py exists" || echo "testing.py missing"
'@
}

function Configure-Service {
    param (
        [Parameter(Mandatory=$true)]
        [string]$RemoteHost,
        [Parameter(Mandatory=$true)]
        [string]$RemoteUser
    )

    Write-Host "Configuring systemd service..." -ForegroundColor Green

    $envVars = Get-EnvVariables
    $envLines = $envVars.GetEnumerator() | ForEach-Object {
        "Environment=`"$($_.Key)=$($_.Value)`""
    }
    $envSection = [System.String]::Join("`n", $envLines)

    $serviceContent = @"
[Unit]
Description=Sales Bot
After=network.target postgresql.service

[Service]
Type=simple
User=jeeves
WorkingDirectory=/home/jeeves/jeeves
Environment=PYTHONPATH=/home/jeeves
$envSection
ExecStart=/home/jeeves/venv/bin/python -u main.py
StandardOutput=append:/var/log/jeeves/app.log
StandardError=append:/var/log/jeeves/error.log
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"@

    # Convert to Unix line endings
    $serviceContent = $serviceContent.Replace("`r`n", "`n")

    $serviceContent | ssh "${RemoteUser}@${RemoteHost}" 'sudo tee /etc/systemd/system/jeeves.service'
}

function Start-Service {
    param (
        [Parameter(Mandatory=$true)]
        [string]$RemoteHost,
        [Parameter(Mandatory=$true)]
        [string]$RemoteUser
    )

    Write-Host "Starting and verifying service..." -ForegroundColor Green

    # Stop service if running
    ssh "${RemoteUser}@${RemoteHost}" 'sudo systemctl stop jeeves'
    Start-Sleep -Seconds 2

    # Reload and restart service
    ssh "${RemoteUser}@${RemoteHost}" 'sudo systemctl daemon-reload'
    Test-LastExitCode "Reloading systemd"

    ssh "${RemoteUser}@${RemoteHost}" 'sudo systemctl enable jeeves'
    Test-LastExitCode "Enabling service"

    # Clear logs before starting
    ssh "${RemoteUser}@${RemoteHost}" @'
sudo truncate -s 0 /var/log/jeeves/app.log
sudo truncate -s 0 /var/log/jeeves/error.log
sudo systemctl restart jeeves
'@
    Test-LastExitCode "Restarting service"

    # Wait and verify service status
    Write-Host "Waiting for service to start..." -ForegroundColor Yellow
    $maxAttempts = 6
    $attempt = 0
    $serviceActive = $false

    while ($attempt -lt $maxAttempts) {
        Start-Sleep -Seconds 5
        $status = ssh "${RemoteUser}@${RemoteHost}" 'sudo systemctl is-active jeeves'

        if ($status -eq 'active') {
            $serviceActive = $true
            break
        }

        $attempt++
        Write-Host "Attempt ${attempt} of ${maxAttempts}: Service not active yet..." -ForegroundColor Yellow
    }

    if (-not $serviceActive) {
        Write-Host "Service failed to start. Checking logs..." -ForegroundColor Red
        ssh "${RemoteUser}@${RemoteHost}" @'
echo "=== Journal Logs ==="
sudo journalctl -u jeeves -n 50 --no-pager
echo -e "\n=== App Logs ==="
sudo tail -n 50 /var/log/jeeves/app.log
echo -e "\n=== Error Logs ==="
sudo tail -n 50 /var/log/jeeves/error.log
'@
        exit 1
    }

    # Show recent logs
    Write-Host "`nService is running. Recent logs:" -ForegroundColor Green

    # Use sed with properly escaped quotes
    Write-Host "`n=== App Log ===" -ForegroundColor Cyan
    ssh "${RemoteUser}@${RemoteHost}" 'sudo cat /var/log/jeeves/app.log | sed ''s/^/  /'''

    Write-Host "`n=== Error Log ===" -ForegroundColor Cyan
    ssh "${RemoteUser}@${RemoteHost}" 'sudo cat /var/log/jeeves/error.log | sed ''s/^/  /'''

    Test-LastExitCode "Fetching logs"

    # Count errors without displaying them
    $errorCount = ssh "${RemoteUser}@${RemoteHost}" 'sudo cat /var/log/jeeves/*.log | grep -c -i "error\|exception\|traceback" || echo 0'

    if ($LASTEXITCODE -eq 0) {
        if ([int]$errorCount -gt 0) {
            Write-Host "`nWarning: Found $errorCount potential errors in logs" -ForegroundColor Yellow
            # Show errors with proper formatting
            Write-Host "`nError context:" -ForegroundColor Yellow
            ssh "${RemoteUser}@${RemoteHost}" 'sudo cat /var/log/jeeves/*.log | grep -i "error\|exception\|traceback" | sed ''s/^/  /'''
        } else {
            Write-Host "`nNo errors found in logs" -ForegroundColor Green
        }
    } else {
        Write-Host "`nWarning: Could not check logs for errors" -ForegroundColor Yellow
    }
}

function Deploy-All {
    param (
        [Parameter(Mandatory=$true)]
        [string]$RemoteHost,
        [Parameter(Mandatory=$true)]
        [string]$RemoteUser
    )

    $startTime = Get-Date
    Write-Host "Starting deployment at $startTime" -ForegroundColor Green

    Run-Tests
    Setup-Logs -RemoteHost $RemoteHost -RemoteUser $RemoteUser
    Deploy-Files -RemoteHost $RemoteHost -RemoteUser $RemoteUser
    Install-RemoteDependencies -RemoteHost $RemoteHost -RemoteUser $RemoteUser
    Configure-Service -RemoteHost $RemoteHost -RemoteUser $RemoteUser
    Start-Service -RemoteHost $RemoteHost -RemoteUser $RemoteUser

    $endTime = Get-Date
    $duration = $endTime - $startTime
    Write-Host "`nDeployment completed successfully in $($duration.TotalMinutes) minutes" -ForegroundColor Green
}

# Main execution
$envVars = Get-EnvVariables
Deploy-All -RemoteHost $envVars['REMOTE_HOST'] -RemoteUser $envVars['REMOTE_USER']
