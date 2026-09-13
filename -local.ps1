param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Data
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$chatPy = Join-Path $scriptDir "chat.py"

if ($Data) {
    python $chatPy -local $Data
} else {
    python $chatPy -local
}
