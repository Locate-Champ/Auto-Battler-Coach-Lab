param(
    [string]$Title = "Codex done",
    [string]$Message = "Task finished.",
    [ValidateSet("min", "low", "default", "high", "max", "urgent")]
    [string]$Priority = "default",
    [string]$Tags = "white_check_mark"
)

$ErrorActionPreference = "Stop"

function Resolve-NtfyTopicUrl {
    if ($env:NTFY_TOPIC_URL) {
        return $env:NTFY_TOPIC_URL.Trim()
    }

    if ($env:NTFY_TOPIC) {
        $topic = $env:NTFY_TOPIC.Trim()
        if ($topic -match "^https?://") {
            return $topic.TrimEnd("/")
        }
        return "https://ntfy.sh/$topic"
    }

    $topicFile = Join-Path $PSScriptRoot "..\.ntfy-topic"
    if (Test-Path $topicFile) {
        $rawTopic = (Get-Content $topicFile -Raw).Trim()
        if ($rawTopic) {
            if ($rawTopic -match "^https?://") {
                return $rawTopic.TrimEnd("/")
            }
            return "https://ntfy.sh/$rawTopic"
        }
    }

    throw "No ntfy topic configured. Set NTFY_TOPIC_URL, NTFY_TOPIC, or create .ntfy-topic in repo root."
}

$topicUrl = Resolve-NtfyTopicUrl
$headers = @{
    "Title"    = $Title
    "Priority" = $Priority
}

if ($Tags) {
    $headers["Tags"] = $Tags
}

Invoke-RestMethod -Method Post -Uri $topicUrl -Headers $headers -Body $Message -TimeoutSec 20 | Out-Null
Write-Output "Sent ntfy notification to $topicUrl"
