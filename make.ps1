# PowerShell Make Script for AI Sales Project

function Get-EnvVariables {
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

    # Create virtual environment only if it doesn't exist
    if (-not (Test-Path venv)) {
        Write-Host "Creating new virtual environment..." -ForegroundColor Green
        python -m venv venv
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Failed to create virtual environment!" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "Using existing virtual environment..." -ForegroundColor Green
    }

    # Install all requirements except tgcrypto
    Get-Content requirements.txt | Where-Object { $_ -notmatch 'tgcrypto' } | Set-Content requirements.local.txt
    .\venv\Scripts\pip install -r requirements.local.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to install dependencies!" -ForegroundColor Red
        Remove-Item requirements.local.txt
        exit 1
    }
    Remove-Item requirements.local.txt

    # Install development dependencies
    .\venv\Scripts\pip install pytest pytest-asyncio isort black
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to install development dependencies!" -ForegroundColor Red
        exit 1
    }

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
    ssh "${RemoteUser}@${RemoteHost}" @'
        cd /home/sales_bot &&
        sudo -u sales_bot python3 -m venv venv &&
        sudo -u sales_bot venv/bin/pip install -r requirements.txt &&
        sudo -u sales_bot venv/bin/pip install pytest
'@
}

function Format-Code {
    Write-Host "Formatting code..." -ForegroundColor Green
    Write-Host "Running isort..." -ForegroundColor Green
    .\venv\Scripts\isort sales_bot tests

    Write-Host "Running black..." -ForegroundColor Green
    .\venv\Scripts\black sales_bot
    .\venv\Scripts\black tests
}

function Run-Tests {
    Write-Host "Installing dependencies and running tests..." -ForegroundColor Green
    Install-LocalDependencies
    Format-Code
    .\venv\Scripts\python -m pytest -x --ff
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Tests failed! Aborting deployment." -ForegroundColor Red
        exit 1
    }
}

function Setup-Logs {
    param (
        [Parameter(Mandatory=$true)]
        [string]$RemoteHost,
        [Parameter(Mandatory=$true)]
        [string]$RemoteUser
    )

    Write-Host "Setting up log directory on remote host..." -ForegroundColor Green
    ssh "${RemoteUser}@${RemoteHost}" @'
        sudo mkdir -p /var/log/sales_bot &&
        sudo chown -R sales_bot:sales_bot /var/log/sales_bot
'@
}

function Deploy-Files {
    param (
        [Parameter(Mandatory=$true)]
        [string]$RemoteHost,
        [Parameter(Mandatory=$true)]
        [string]$RemoteUser
    )

    Write-Host "Deploying application files..." -ForegroundColor Green

    # Create remote directory if it doesn't exist
    ssh "${RemoteUser}@${RemoteHost}" 'sudo mkdir -p /home/sales_bot/sales_bot'

    # Clean up __pycache__ directories locally before copying
    Get-ChildItem -Path "./sales_bot" -Filter "__pycache__" -Recurse | Remove-Item -Recurse -Force

    # Create a temporary directory for deployment files
    $tempDir = Join-Path $env:TEMP "ai_sales_deploy"
    if (Test-Path $tempDir) {
        Remove-Item -Path $tempDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $tempDir | Out-Null

    # Copy files excluding tests
    Get-ChildItem -Path "./sales_bot" -Recurse |
        Where-Object {
            -not $_.PSIsContainer -and
            -not $_.Name.EndsWith("_test.py") -and
            -not $_.FullName.Contains("tests") -and
            -not $_.FullName.Contains("script_tests")
        } |
        ForEach-Object {
            $targetPath = Join-Path $tempDir $_.FullName.Substring((Get-Location).Path.Length + 11)
            $targetDir = Split-Path -Parent $targetPath
            if (-not (Test-Path $targetDir)) {
                New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
            }
            Copy-Item $_.FullName -Destination $targetPath
        }

    # Deploy files
    Write-Host "`nCopying files to server..." -ForegroundColor Green
    # First copy requirements.txt to the correct location
    scp requirements.txt "${RemoteUser}@${RemoteHost}:/home/sales_bot/"
    # Then copy all other files
    scp -r -p ./$tempDir/* "${RemoteUser}@${RemoteHost}:/home/sales_bot/sales_bot/"

    # Set permissions
    ssh "${RemoteUser}@${RemoteHost}" 'sudo chown -R sales_bot:sales_bot /home/sales_bot'
}

function Configure-Service {
    param (
        [Parameter(Mandatory=$true)]
        [string]$RemoteHost,
        [Parameter(Mandatory=$true)]
        [string]$RemoteUser
    )

    Write-Host "Configuring systemd service..." -ForegroundColor Green

    # Read environment variables from .env
    $envVars = Get-EnvVariables

    # Generate Environment variables section
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
User=sales_bot
WorkingDirectory=/home/sales_bot/sales_bot
$envSection
ExecStart=/home/sales_bot/venv/bin/python /home/sales_bot/sales_bot/main.py
StandardOutput=append:/var/log/sales_bot/app.log
StandardError=append:/var/log/sales_bot/error.log
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"@

    $serviceContent | ssh "${RemoteUser}@${RemoteHost}" 'sudo tee /etc/systemd/system/sales_bot.service'
}

function Start-Service {
    param (
        [Parameter(Mandatory=$true)]
        [string]$RemoteHost,
        [Parameter(Mandatory=$true)]
        [string]$RemoteUser
    )

    Write-Host "Starting and verifying service..." -ForegroundColor Green

    ssh "${RemoteUser}@${RemoteHost}" @'
        echo "Reloading systemd..."
        sudo systemctl daemon-reload

        echo "Enabling and starting service..."
        sudo systemctl enable sales_bot
        sudo systemctl restart sales_bot

        echo "Waiting for service to stabilize..."
        sleep 5

        echo "Checking service status..."
        sudo systemctl status sales_bot

        if ! sudo systemctl is-active --quiet sales_bot; then
            echo "Service failed to start!"
            echo "Last 50 lines of error log:"
            sudo tail -n 50 /var/log/sales_bot/error.log
            echo "Journal logs:"
            sudo journalctl -u sales_bot -n 50 --no-pager
            exit 1
        fi

        echo "Service started successfully!"
        echo "Recent application logs:"
        sudo tail -n 20 /var/log/sales_bot/app.log
'@
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

    try {
        Run-Tests
        Deploy-Files -RemoteHost $RemoteHost -RemoteUser $RemoteUser
        Install-RemoteDependencies -RemoteHost $RemoteHost -RemoteUser $RemoteUser
        Setup-Logs -RemoteHost $RemoteHost -RemoteUser $RemoteUser
        Configure-Service -RemoteHost $RemoteHost -RemoteUser $RemoteUser
        Start-Service -RemoteHost $RemoteHost -RemoteUser $RemoteUser

        # Проверяем финальный статус сервиса
        $serviceStatus = ssh "${RemoteUser}@${RemoteHost}" 'sudo systemctl is-active sales_bot'
        if ($serviceStatus -ne 'active') {
            Write-Host "Deployment failed: Service is not running!" -ForegroundColor Red
            Write-Host "Service status: $serviceStatus" -ForegroundColor Red
            ssh "${RemoteUser}@${RemoteHost}" 'sudo systemctl status sales_bot'
            exit 1
        }

        $endTime = Get-Date
        $deploymentTime = $endTime - $startTime

        Write-Host "`nDeployment completed successfully!" -ForegroundColor Green
        Write-Host "Started:  $startTime"
        Write-Host "Finished: $endTime"
        Write-Host "Total deployment time: $($deploymentTime.ToString('hh\:mm\:ss'))"
    }
    catch {
        Write-Host "Deployment failed with error: $_" -ForegroundColor Red
        exit 1
    }
}

function Show-Help {
    Write-Host "Available commands:" -ForegroundColor Yellow
    Write-Host "  .\make.ps1 install       - Install project dependencies"
    Write-Host "  .\make.ps1 install-local - Install project dependencies locally"
    Write-Host "  .\make.ps1 format        - Format code with isort and black"
    Write-Host "  .\make.ps1 test          - Run tests"
    Write-Host "  .\make.ps1 logs          - Setup log directories"
    Write-Host "  .\make.ps1 deploy        - Run full deployment"
    Write-Host "  .\make.ps1 help          - Show this help message"
}

# Parse command line argument
$command = $args[0]

switch ($command) {
    "install" {
        $envVars = Get-EnvVariables
        Install-RemoteDependencies -RemoteHost $envVars['REMOTE_HOST'] -RemoteUser $envVars['REMOTE_USER']
    }
    "install-local" { Install-LocalDependencies }
    "format"  { Format-Code }
    "test"    { Run-Tests }
    "logs"    {
        $envVars = Get-EnvVariables
        Setup-Logs -RemoteHost $envVars['REMOTE_HOST'] -RemoteUser $envVars['REMOTE_USER']
    }
    "deploy"  {
        $envVars = Get-EnvVariables
        Deploy-All -RemoteHost $envVars['REMOTE_HOST'] -RemoteUser $envVars['REMOTE_USER']
    }
    "help"    { Show-Help }
    default   {
        Write-Host "Unknown command: $command" -ForegroundColor Red
        Show-Help
    }
}
