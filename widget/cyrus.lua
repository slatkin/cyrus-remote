-- Noctalia v5 scripted widget for Cyrus ONE BLE amplifier
-- Left-click: toggle mute   Right-click: cycle input

local INPUTS = { "bt", "usb", "optical", "spdif", "phono", "aux5", "aux6" }

local connected = false
local volPct    = 0
local muted     = false
local inputName = "--"
local started   = false

local function parseBool(json, key)
    return json:match('"' .. key .. '":%s*true') ~= nil
end

local function parseNum(json, key)
    return tonumber(json:match('"' .. key .. '":%s*(%d+)')) or 0
end

local function parseStr(json, key)
    return json:match('"' .. key .. '":%s*"([^"]*)"') or ""
end

local function updateDisplay()
    if connected then
        local muteTag = muted and "  muted" or ""
        barWidget.setText(string.format("%d%%  %s%s", volPct, inputName, muteTag))
        barWidget.setGlyph("music")
        barWidget.setColor("on_surface")
        barWidget.setGlyphColor("primary")
    else
        barWidget.setText("cyrus")
        barWidget.setGlyph("bluetooth-off")
        barWidget.setColor("on_surface_variant")
        barWidget.setGlyphColor("on_surface_variant")
    end
end

function update()
    if started then return end
    started = true
    local home = noctalia.getenv("HOME") or ""
    local proxyHost = noctalia.getenv("CYRUS_PROXY_HOST")
    if proxyHost and proxyHost ~= "" then
        noctalia.runAsync(
            "nohup " .. home .. "/.local/bin/cyrus-proxy --host " .. proxyHost .. " > /dev/null 2>&1 &"
        )
    else
        noctalia.runAsync(
            "nohup " .. home .. "/.local/bin/cyrus-daemon > /dev/null 2>&1 &"
        )
    end
    barWidget.setUpdateInterval(5000)
    updateDisplay()
end

function onIpc(event, payload)
    if event ~= "updateState" then return end
    connected = parseBool(payload, "connected")
    volPct    = parseNum(payload, "vol_pct")
    muted     = parseBool(payload, "muted")
    local inp = parseStr(payload, "input")
    inputName = inp ~= "" and inp or "--"
    updateDisplay()
end

function onClick()
    if not connected then return end
    noctalia.runAsync("cyrus-cmd " .. (muted and "unmute" or "mute"))
end

function onRightClick()
    if not connected then return end
    local idx = 1
    for i, name in ipairs(INPUTS) do
        if name == inputName then idx = i; break end
    end
    noctalia.runAsync("cyrus-cmd input:" .. INPUTS[(idx % #INPUTS) + 1])
end
