param(
    [ValidateSet('macos', 'linux', 'windows', 'docker')]
    [string]$Platform = 'windows',

    [ValidateSet('a', 'b', 'c', 'd', 'A', 'B', 'C', 'D')]
    [string]$Profile = 'b',

    [string]$Target = ''
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$Platform = $Platform.ToLowerInvariant()
if ($Platform -eq 'linux') { $Platform = 'macos' }
$profileLower = $Profile.ToLower()
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)

if ([string]::IsNullOrWhiteSpace($Target)) {
    $Target = Join-Path $projectRoot '.env'
}

$baseEnv = Join-Path $projectRoot '.env.example'
$overrideEnv = Join-Path $projectRoot ("deploy/profiles/{0}/profile-{1}.env" -f $Platform, $profileLower)

function Read-LinesUtf8 {
    param([string]$FilePath)

    if (-not (Test-Path $FilePath)) {
        return @()
    }

    return [System.IO.File]::ReadAllLines($FilePath, $utf8NoBom)
}

function Write-LinesUtf8 {
    param(
        [string]$FilePath,
        [string[]]$Lines
    )

    $parent = Split-Path -Parent $FilePath
    if (-not [string]::IsNullOrWhiteSpace($parent) -and -not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }

    [System.IO.File]::WriteAllLines($FilePath, $Lines, $utf8NoBom)
}

function Set-EnvValueInFile {
    param(
        [string]$FilePath,
        [string]$Key,
        [string]$Value
    )

    $lines = @(Read-LinesUtf8 -FilePath $FilePath)

    $escaped = [regex]::Escape($Key)
    $updated = $false
    $newLines = [System.Collections.Generic.List[string]]::new()

    foreach ($line in $lines) {
        if ($line -match "^\s*${escaped}\s*=") {
            if (-not $updated) {
                $updated = $true
                [void]$newLines.Add("$Key=$Value")
            }
            continue
        }

        [void]$newLines.Add([string]$line)
    }

    if (-not $updated) {
        [void]$newLines.Add("$Key=$Value")
    }

    Write-LinesUtf8 -FilePath $FilePath -Lines $newLines.ToArray()
}

function Dedupe-EnvKeys {
    param([string]$FilePath)

    if (-not (Test-Path $FilePath)) {
        return
    }

    $keys = Read-LinesUtf8 -FilePath $FilePath |
        Where-Object { $_ -match '^\s*[A-Z0-9_]+\s*=' } |
        ForEach-Object {
            $parts = $_ -split '=', 2
            $parts[0].Trim()
        } |
        Group-Object |
        Where-Object { $_.Count -gt 1 } |
        Sort-Object Name

    foreach ($group in $keys) {
        $escaped = [regex]::Escape($group.Name)
        $lastLine = Read-LinesUtf8 -FilePath $FilePath |
            Where-Object { $_ -match "^\s*${escaped}\s*=" } |
            Select-Object -Last 1
        if (-not $lastLine) {
            continue
        }

        $value = ($lastLine -split '=', 2)[1].TrimStart()
        Set-EnvValueInFile -FilePath $FilePath -Key $group.Name -Value $value
    }
}

function Get-EnvValueFromFile {
    param(
        [string]$FilePath,
        [string]$Key
    )

    if (-not (Test-Path $FilePath)) {
        return ''
    }

    $escaped = [regex]::Escape($Key)
    $lastLine = Read-LinesUtf8 -FilePath $FilePath |
        Where-Object { $_ -match "^\s*${escaped}\s*=" } |
        Select-Object -Last 1

    if (-not $lastLine) {
        return ''
    }

    return ($lastLine -split '=', 2)[1].TrimStart()
}

function Sync-DockerWalOverrides {
    param([string]$FilePath)

    $walEnabled = (Get-EnvValueFromFile -FilePath $FilePath -Key 'RUNTIME_WRITE_WAL_ENABLED').Trim()
    $journalMode = (Get-EnvValueFromFile -FilePath $FilePath -Key 'RUNTIME_WRITE_JOURNAL_MODE').Trim()

    if (-not [string]::IsNullOrWhiteSpace($walEnabled)) {
        Set-EnvValueInFile -FilePath $FilePath -Key 'MEMORY_PALACE_DOCKER_WAL_ENABLED' -Value $walEnabled
    }
    if (-not [string]::IsNullOrWhiteSpace($journalMode)) {
        Set-EnvValueInFile -FilePath $FilePath -Key 'MEMORY_PALACE_DOCKER_JOURNAL_MODE' -Value $journalMode
    }
}

function New-DockerMcpApiKey {
    $bytes = [byte[]]::new(24)
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return [Convert]::ToHexString($bytes).ToLowerInvariant()
}

function Assert-ResolvedProfilePlaceholders {
    param(
        [string]$FilePath,
        [string]$ResolvedProfile
    )

    if ($ResolvedProfile -notin @('c', 'd')) {
        return
    }

    $unresolved = [System.Collections.Generic.List[string]]::new()
    foreach ($line in Read-LinesUtf8 -FilePath $FilePath) {
        if (
            $line -match '^\s*(ROUTER_API_BASE|RETRIEVAL_EMBEDDING_API_BASE|RETRIEVAL_RERANKER_API_BASE)\s*=\s*.*:PORT/' `
            -or $line -match '=\s*replace-with-your-key(\s+#.*)?\s*$' `
            -or $line -match '=\s*your-embedding-model-id(\s+#.*)?\s*$' `
            -or $line -match '=\s*your-reranker-model-id(\s+#.*)?\s*$' `
            -or $line -match '=\s*https://router\.example\.com/'
        ) {
            [void]$unresolved.Add($line)
        }
    }

    if ($unresolved.Count -eq 0) {
        return
    }

    [Console]::Error.WriteLine(
        "Generated {0}, but profile {1} still contains unresolved placeholders:" -f $FilePath, $ResolvedProfile
    )
    foreach ($item in $unresolved) {
        [Console]::Error.WriteLine("  {0}" -f $item)
    }
    throw "Fill the placeholder values before using profile $ResolvedProfile."
}

if (-not (Test-Path $baseEnv)) {
    Write-Error "Missing base env template: $baseEnv"
    exit 1
}

if (-not (Test-Path $overrideEnv)) {
    Write-Error "Missing profile template: $overrideEnv"
    exit 1
}

$combinedLines = [System.Collections.Generic.List[string]]::new()
foreach ($line in Read-LinesUtf8 -FilePath $baseEnv) {
    [void]$combinedLines.Add([string]$line)
}
[void]$combinedLines.Add("")
[void]$combinedLines.Add("# -----------------------------------------------------------------------------")
[void]$combinedLines.Add("# Appended profile overrides ($Platform/profile-$profileLower)")
[void]$combinedLines.Add("# -----------------------------------------------------------------------------")
foreach ($line in Read-LinesUtf8 -FilePath $overrideEnv) {
    [void]$combinedLines.Add([string]$line)
}
Write-LinesUtf8 -FilePath $Target -Lines $combinedLines.ToArray()

if ($Platform -eq 'macos') {
    $placeholderPattern = '^\s*DATABASE_URL\s*=\s*sqlite\+aiosqlite:////Users/<your-user>/memory_palace/agent_memory\.db(\s+#.*)?\s*$'
    if (Select-String -Path $Target -Pattern $placeholderPattern -Quiet) {
        $dbPath = (Join-Path $projectRoot 'demo.db') -replace '\\', '/'
        $dbUrl = 'DATABASE_URL=sqlite+aiosqlite:////' + $dbPath.TrimStart('/')
        Set-EnvValueInFile -FilePath $Target -Key 'DATABASE_URL' -Value $dbUrl.Substring('DATABASE_URL='.Length)
        Write-Host "[auto-fill] DATABASE_URL set to $dbPath"
    }
}

if ($Platform -eq 'windows') {
    $placeholderPattern = '^\s*DATABASE_URL\s*=\s*sqlite\+aiosqlite:///C:/memory_palace/agent_memory\.db(\s+#.*)?\s*$'
    if (Select-String -Path $Target -Pattern $placeholderPattern -Quiet) {
        $dbPath = (Join-Path $projectRoot 'demo.db') -replace '\\', '/'
        if ($dbPath -match '^/([a-zA-Z])/(.*)$') {
            $drive = $Matches[1].ToUpperInvariant()
            $dbPath = "${drive}:/$($Matches[2])"
        }
        elseif ($dbPath -match '^/mnt/([a-zA-Z])/(.*)$') {
            $drive = $Matches[1].ToUpperInvariant()
            $dbPath = "${drive}:/$($Matches[2])"
        }
        elseif ($dbPath -notmatch '^[A-Za-z]:/') {
            $dbPath = 'C:/memory_palace/demo.db'
        }
        $dbUrl = 'DATABASE_URL=sqlite+aiosqlite:///' + $dbPath
        Set-EnvValueInFile -FilePath $Target -Key 'DATABASE_URL' -Value $dbUrl.Substring('DATABASE_URL='.Length)
        Write-Host "[auto-fill] DATABASE_URL set to $dbPath"
    }
}

if ($Platform -eq 'docker') {
    $currentApiKey = Get-EnvValueFromFile -FilePath $Target -Key 'MCP_API_KEY'
    if ([string]::IsNullOrWhiteSpace($currentApiKey)) {
        $generatedApiKey = New-DockerMcpApiKey
        Set-EnvValueInFile -FilePath $Target -Key 'MCP_API_KEY' -Value $generatedApiKey
        Write-Host "[auto-fill] MCP_API_KEY generated for docker profile"
    }
    Sync-DockerWalOverrides -FilePath $Target
}

Dedupe-EnvKeys -FilePath $Target
Assert-ResolvedProfilePlaceholders -FilePath $Target -ResolvedProfile $profileLower

Write-Host "Generated $Target from $overrideEnv"
