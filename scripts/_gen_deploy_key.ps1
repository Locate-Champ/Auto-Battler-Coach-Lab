$keyPath = "$env:USERPROFILE\.ssh\coach_sim_deploy"
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.ssh" | Out-Null
if (Test-Path $keyPath) { Remove-Item $keyPath -Force }
if (Test-Path "$keyPath.pub") { Remove-Item "$keyPath.pub" -Force }

& 'C:\Windows\System32\OpenSSH\ssh-keygen.exe' -t ed25519 -C 'coach-sim-graviton' -f $keyPath -N ''

if (Test-Path "$keyPath.pub") {
    Write-Host "PUBLIC_KEY:"
    Get-Content "$keyPath.pub"
    Write-Host "PRIVATE_B64:"
    [Convert]::ToBase64String([IO.File]::ReadAllBytes($keyPath))
} else {
    Write-Host "ERROR: Key generation failed"
    exit 1
}
