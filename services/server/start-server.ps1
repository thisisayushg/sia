# Define the URL of the Git repository
$repoUrl = "https://github.com/thisisayushg/tavily-mcp-http"

# Define the directory where the repo will be cloned
$repoDir = "tavily-mcp"
$tempDir  = "temp-extract"

# Step 1: Download the git repo as a zip file
Write-Output "Downloading the Git repository as a zip file..."
Invoke-WebRequest -Uri $repoUrl/archive/refs/heads/main.zip -OutFile main.zip

# Step 2: Extract the zip file
Write-Output "Extracting the zip file..."

# Extract to a temp directory
Expand-Archive -LiteralPath main.zip -DestinationPath $tempDir

# Move inner folder contents to target directory
$innerDir = Get-ChildItem $tempDir | Where-Object { $_.PSIsContainer }

New-Item -ItemType Directory -Path $repoDir -Force | Out-Null
Move-Item "$($innerDir.FullName)\*" $repoDir

# Cleanup
Remove-Item $tempDir -Recurse -Force

# Step 3: Change directory to the extracted repository
Set-Location -Path $repoDir
Write-Output "Display dockerfile content"
ls
Get-Content -LiteralPath Dockerfile
# Step 4: Modify the ENTRYPOINT line in the Dockerfile
Write-Output "Modifying the ENTRYPOINT line in the Dockerfile..."
$content = Get-Content -Path Dockerfile
$modifiedContent = $content -replace '^ENTRYPOINT.*', 'CMD ["npx", "-y", "mcp-remote", "https://mcp.tavily.com/mcp/?tavilyApiKey=$TAVILY_API_KEY"]'
Set-Content -LiteralPath Dockerfile -Value $modifiedContent

# Step 5: Display the modified Dockerfile to confirm changes
Write-Output "Dockerfile after modification:"
Get-Content -LiteralPath Dockerfile

Write-Output "Script execution completed."

Set-Location ..

docker compose -f compose.yaml up --build -d