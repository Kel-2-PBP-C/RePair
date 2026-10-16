param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Navbar', 'Accounts')]
    [string]$Feature
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot

function Invoke-ProjectGit {
    param([string[]]$GitArguments)
    & git --no-pager -C $repoRoot @GitArguments
    if ($LASTEXITCODE -ne 0) {
        throw 'Git gagal. Staging dihentikan; belum ada commit atau push.'
    }
}

$expectedBranch = if ($Feature -eq 'Navbar') {
    'feat/shared-navbar'
} else {
    'Halaman-Login/Register-dan-Profil-dan-Setting'
}
$actualBranch = (Invoke-ProjectGit -GitArguments @('branch', '--show-current')).Trim()
if ($actualBranch -ne $expectedBranch) {
    throw "Branch aktif '$actualBranch'. Jalankan script dari folder branch '$expectedBranch'."
}

$sharedPaths = @(
    '.gitignore', '.gitattributes', '.githooks/pre-commit', '.githooks/pre-push',
    'scripts/check_git_safety.py', 'scripts/test_git_safety.py',
    'scripts/stage_feature.ps1',
    'core/context_processors.py', 'core/templates/core/landing.html',
    'core/tests/test_navigation.py', 'core/tests/urls_integrated.py',
    'static/css/site.css', 'static/css/navbar.css',
    'templates/base.html', 'templates/components/navbar.html',
    'static/img/Group 40.png', 'static/img/Group 46.png',
    'static/img/home_filled.png', 'static/img/shopping_cart.png',
    'static/img/chat_bubble_outline.png', 'static/img/insert_photo.png',
    'static/img/settings.png'
)
$accountPaths = @(
    '.env.example', 'README.md', 'RePair', 'requirements.txt', 'manage.py',
    'accounts', 'barter_details', 'core',
    'static/img/Group 47.png',
    'static/img/Barter & Perbaiki barang tak terpakai dengan mudah..png',
    'static/img/google.jpg', 'static/img/google.png', 'static/img/Chevron 2.png'
)
$paths = @($sharedPaths)
if ($Feature -eq 'Accounts') { $paths += $accountPaths }
$deletedDocs = @(Invoke-ProjectGit -GitArguments @('ls-files', '--deleted', '--', 'docs'))
$paths += $deletedDocs
$paths += @(Invoke-ProjectGit -GitArguments @('diff', '--cached', '--name-only', '--diff-filter=D', '--', 'docs'))

$alreadyStaged = @(Invoke-ProjectGit -GitArguments @('diff', '--cached', '--name-only'))
foreach ($file in $alreadyStaged) {
    $owned = $false
    foreach ($allowed in $paths) {
        if ($file -eq $allowed -or $file.StartsWith($allowed + '/', [StringComparison]::Ordinal)) {
            $owned = $true
            break
        }
    }
    if (-not $owned) {
        throw "File staged di luar daftar fitur: $file. Periksa dan unstage file itu dahulu."
    }
}

foreach ($file in $sharedPaths) {
    if (-not (Test-Path -LiteralPath (Join-Path $repoRoot $file))) {
        throw "Berkas bersama belum tersedia: $file. Staging dihentikan."
    }
}
$existingPaths = @($paths | Where-Object { Test-Path -LiteralPath (Join-Path $repoRoot $_) })
Invoke-ProjectGit -GitArguments (@('add', '--') + $existingPaths)
if ($deletedDocs.Count -gt 0) {
    Invoke-ProjectGit -GitArguments (@('add', '-u', '--') + $deletedDocs)
}
Invoke-ProjectGit -GitArguments @('update-index', '--chmod=+x', '--', '.githooks/pre-commit', '.githooks/pre-push')

$pythonCandidates = @(
    (Join-Path $repoRoot '.venv/Scripts/python.exe'),
    (Join-Path (Split-Path -Parent $repoRoot) '.venv/Scripts/python.exe')
)
$python = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $python) { $python = 'python' }
Push-Location -LiteralPath $repoRoot
try {
    & $python (Join-Path $repoRoot 'scripts/check_git_safety.py') --index
    if ($LASTEXITCODE -ne 0) { throw 'Pengaman menolak staging. Jangan commit atau push sebelum diperbaiki.' }
} finally {
    Pop-Location
}
Invoke-ProjectGit -GitArguments @('diff', '--cached', '--check')
Invoke-ProjectGit -GitArguments @('diff', '--cached', '--stat')
Write-Host 'Staging selesai. Tinjau daftar di atas; belum ada commit atau push.'
