param(
  [string]$WorkingDir = (Get-Location)
)
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$Form = New-Object System.Windows.Forms.Form
$Form.Text = "OpenAI Research Scanner"
$Form.Size = New-Object System.Drawing.Size(700,520)
$Form.StartPosition = 'CenterScreen'

# Labels & Inputs
$lblPdf = New-Object System.Windows.Forms.Label
$lblPdf.Text = 'PDF/JSON:'
$lblPdf.Location = '20,20'
$lblPdf.AutoSize = $true

$txtPdf = New-Object System.Windows.Forms.TextBox
$txtPdf.Location = '120,18'
$txtPdf.Size = '420,24'

$btnBrowse = New-Object System.Windows.Forms.Button
$btnBrowse.Text = 'Browse...'
$btnBrowse.Location = '550,16'
$btnBrowse.Add_Click({
  $ofd = New-Object System.Windows.Forms.OpenFileDialog
  $ofd.Filter = 'PDF or JSON (*.pdf;*.json)|*.pdf;*.json|PDF files (*.pdf)|*.pdf|OpenAI export (*.json)|*.json|All files (*.*)|*.*'
  if ($ofd.ShowDialog() -eq 'OK') { $txtPdf.Text = $ofd.FileName }
})

$lblKey = New-Object System.Windows.Forms.Label
$lblKey.Text = 'OpenAI API Key:'
$lblKey.Location = '20,60'
$lblKey.AutoSize = $true

$txtKey = New-Object System.Windows.Forms.TextBox
$txtKey.Location = '120,58'
$txtKey.Size = '420,24'
$txtKey.UseSystemPasswordChar = $true

$chkSaveEnv = New-Object System.Windows.Forms.CheckBox
$chkSaveEnv.Text = 'Save to .env'
$chkSaveEnv.Location = '550,60'
$chkSaveEnv.AutoSize = $true

$lblOllama = New-Object System.Windows.Forms.Label
$lblOllama.Text = 'Ollama Path (optional):'
$lblOllama.Location = '20,100'
$lblOllama.AutoSize = $true

$txtOllama = New-Object System.Windows.Forms.TextBox
$txtOllama.Location = '180,98'
$txtOllama.Size = '360,24'

$btnOllama = New-Object System.Windows.Forms.Button
$btnOllama.Text = 'Find...'
$btnOllama.Location = '550,96'
$btnOllama.Add_Click({
  $ofd = New-Object System.Windows.Forms.OpenFileDialog
  $ofd.Filter = 'Executable (*.exe)|*.exe|All files (*.*)|*.*'
  if ($ofd.ShowDialog() -eq 'OK') { $txtOllama.Text = $ofd.FileName }
})

$lblModel = New-Object System.Windows.Forms.Label
$lblModel.Text = 'Ollama Model:'
$lblModel.Location = '20,140'
$lblModel.AutoSize = $true

$cmbModel = New-Object System.Windows.Forms.ComboBox
$cmbModel.Location = '120,138'
$cmbModel.Size = '200,24'
$cmbModel.DropDownStyle = 'DropDownList'
[void]$cmbModel.Items.AddRange(@('llama3.2','qwen2.5','mistral:7b','phi4'))
$cmbModel.SelectedIndex = 0

$lblGpt = New-Object System.Windows.Forms.Label
$lblGpt.Text = 'OpenAI Model:'
$lblGpt.Location = '340,140'
$lblGpt.AutoSize = $true

$cmbGpt = New-Object System.Windows.Forms.ComboBox
$cmbGpt.Location = '430,138'
$cmbGpt.Size = '140,24'
$cmbGpt.DropDownStyle = 'DropDownList'
[void]$cmbGpt.Items.AddRange(@('gpt-5','gpt-5-mini','gpt-5-nano','gpt-4o'))
$cmbGpt.SelectedIndex = 0

# Role filter for JSON scans
$lblRoles = New-Object System.Windows.Forms.Label
$lblRoles.Text = 'Roles:'
$lblRoles.Location = '20,170'
$lblRoles.AutoSize = $true

$cmbRoles = New-Object System.Windows.Forms.ComboBox
$cmbRoles.Location = '70,168'
$cmbRoles.Size = '120,24'
$cmbRoles.DropDownStyle = 'DropDownList'
[void]$cmbRoles.Items.AddRange(@('Both','User only','Assistant only'))
$cmbRoles.SelectedIndex = 0

# Cost threshold
$lblThreshold = New-Object System.Windows.Forms.Label
$lblThreshold.Text = 'Auto-run if cost ≤ $'
$lblThreshold.Location = '220,170'
$lblThreshold.AutoSize = $true

$txtThreshold = New-Object System.Windows.Forms.TextBox
$txtThreshold.Location = '355,168'
$txtThreshold.Size = '60,24'
$txtThreshold.Text = '0.50'

# Buttons
$btnOpen = New-Object System.Windows.Forms.Button
$btnOpen.Text = 'Open PDF'
$btnOpen.Location = '20,180'
$btnOpen.Add_Click({ if ($txtPdf.Text) { Start-Process $txtPdf.Text } })

$btnScan = New-Object System.Windows.Forms.Button
$btnScan.Text = 'Scan PDF with ChatGPT'
$btnScan.Location = '140,180'

$btnParseGPT = New-Object System.Windows.Forms.Button
$btnParseGPT.Text = 'Compile with GPT (+ cost estimate)'
$btnParseGPT.Location = '360,180'
$btnParseGPT.Size = '200,30'

$btnAppsTools = New-Object System.Windows.Forms.Button
$btnAppsTools.Text = 'Reconstruct Apps & Tools'
$btnAppsTools.Location = '570,180'
$btnAppsTools.Size = '200,30'

# Log box
$txtLog = New-Object System.Windows.Forms.TextBox
$txtLog.Location = '20,230'
$txtLog.Size = '690,270'
$txtLog.Multiline = $true
$txtLog.ScrollBars = 'Vertical'
$txtLog.ReadOnly = $true

function Log([string]$msg) {
  $ts = (Get-Date).ToString('HH:mm:ss')
  $txtLog.AppendText("[$ts] $msg`r`n")
}

$Form.Controls.AddRange(@($lblPdf,$txtPdf,$btnBrowse,$lblKey,$txtKey,$chkSaveEnv,$lblOllama,$txtOllama,$btnOllama,$lblModel,$cmbModel,$lblGpt,$cmbGpt,$lblRoles,$cmbRoles,$lblThreshold,$txtThreshold,$btnOpen,$btnScan,$btnParseGPT,$btnAppsTools,$txtLog))

# Handlers
$btnScan.Add_Click({
  if (-not (Test-Path $txtPdf.Text)) { Log 'Pick a PDF first.'; return }
  if (-not $txtKey.Text) { Log 'Enter your OpenAI API key.'; return }

  $env:OPENAI_API_KEY = $txtKey.Text
  if ($chkSaveEnv.Checked) {
    $envFile = Join-Path $WorkingDir '.env'
    "OPENAI_API_KEY=$($txtKey.Text)" | Out-File -Encoding ascii $envFile
    Log "Saved .env at $envFile"
  }

  $outDir = Join-Path $WorkingDir "output\$(Get-Date -Format yyyyMMdd_HHmmss)"
  New-Item -ItemType Directory -Force -Path $outDir | Out-Null

  $gptModel = $cmbGpt.SelectedItem
  $ext = [System.IO.Path]::GetExtension($txtPdf.Text).ToLower()
  
  $rolesArg = switch ($cmbRoles.SelectedItem) {
    'User only' { '--roles user' }
    'Assistant only' { '--roles assistant' }
    default { '--roles both' }
  }
  
  if ($ext -eq '.json') {
    $cmd = ".venv\\Scripts\\python.exe scripts\\scan_openai_json.py -i `"$($txtPdf.Text)`" -o `"$outDir`" -m $gptModel $rolesArg"
  } else {
    $cmd = ".venv\\Scripts\\python.exe scripts\\scan_pdf.py -i `"$($txtPdf.Text)`" -o `"$outDir`" -m $gptModel"
  }
  Log "Running: $cmd"
  $res = cmd.exe /c $cmd 2>&1
  $res | ForEach-Object { Log $_ }
})

$btnParseGPT.Add_Click({
  $latest = Get-ChildItem (Join-Path $WorkingDir 'output') | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if (-not $latest) { Log 'No output folder found. Run a scan first.'; return }
  $jsonl = Join-Path $latest.FullName 'scan_quotes.jsonl'
  if (-not (Test-Path $jsonl)) { Log 'scan_quotes.jsonl not found. Run a scan first.'; return }
  if (-not $txtKey.Text) { Log 'Enter your OpenAI API key.'; return }
  $env:OPENAI_API_KEY = $txtKey.Text
  $model = $cmbGpt.SelectedItem

  # 1) Estimate
  $estCmd = ".venv\\Scripts\\python.exe scripts\\parse_with_openai.py -i `"$jsonl`" -m `"$model`" -o `"$latest.FullName`" --estimate-only"
  Log "Estimating: $estCmd"
  $estOut = cmd.exe /c $estCmd 2>&1
  $estOut | ForEach-Object { Log $_ }

  # Parse last non-empty line as JSON
  $jsonLine = ($estOut | Where-Object { $_ -ne '' } | Select-Object -Last 1)
  try {
    $est = $jsonLine | ConvertFrom-Json
    $inTok = [int]$est.estimate.input_tokens
    $outTok = [int]$est.estimate.output_tokens
  $cost = [double]$est.estimate.usd_total
  $rateIn = $est.estimate.usd_per_million_input
  $rateOut = $est.estimate.usd_per_million_output
  $threshold = [double]$txtThreshold.Text
  $msg = "Estimated tokens — in: $inTok, out: $outTok`nModel rates — in: $rateIn/million, out: $rateOut/million`nEstimated cost: $" + ([Math]::Round([double]$cost,4)) + " USD. Continue?"
  
  if ($cost -le $threshold) {
    Log "Cost ($([Math]::Round($cost,4))) is within threshold ($threshold). Auto-running..."
  } else {
    $choice = [System.Windows.Forms.MessageBox]::Show($msg, 'Cost estimate', 'YesNo', 'Question')
    if ($choice -ne 'Yes') { Log 'Canceled by user.'; return }
  }
  } catch {
    Log 'Could not parse estimate JSON; proceeding without confirmation.'
  }

  # 2) Run compile
  $runCmd = ".venv\\Scripts\\python.exe scripts\\parse_with_openai.py -i `"$jsonl`" -m `"$model`" -o `"$latest.FullName`""
  Log "Running: $runCmd"
  $res = cmd.exe /c $runCmd 2>&1
  $res | ForEach-Object { Log $_ }
})

$btnAppsTools.Add_Click({
  $latest = Get-ChildItem (Join-Path $WorkingDir 'output') | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if (-not $latest) { Log 'No output folder found. Run a scan first.'; return }
  $jsonl = Join-Path $latest.FullName 'scan_quotes.jsonl'
  if (-not (Test-Path $jsonl)) { Log 'scan_quotes.jsonl not found. Run a scan first.'; return }
  if (-not $txtKey.Text) { Log 'Enter your OpenAI API key.'; return }
  $env:OPENAI_API_KEY = $txtKey.Text
  $model = $cmbGpt.SelectedItem

  $cmd = ".venv\\Scripts\\python.exe scripts\\reconstruct_apps_tools.py -i `"$jsonl`" -m `"$model`" -o `"$latest.FullName`""
  Log "Running: $cmd"
  $res = cmd.exe /c $cmd 2>&1
  $res | ForEach-Object { Log $_ }
})

[void]$Form.ShowDialog()
