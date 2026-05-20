-- Noctalia v5 scripted widget — Cyrus ONE input selector
-- Left: prev input   Right: next input

local INPUTS = { "bt", "usb", "optical", "spdif", "phono", "aux5", "aux6" }

local connected = false
local inputName = "--"
local started   = false

local function parseBool(json, key)
    return json:match('"' .. key .. '":%s*true') ~= nil
end

local function parseStr(json, key)
    return json:match('"' .. key .. '":%s*"([^"]*)"') or ""
end

local function updateDisplay()
    if connected then
        barWidget.setGlyph("music")
        barWidget.setText(inputName)
        barWidget.setColor("on_surface")
        barWidget.setGlyphColor("primary")
    else
        barWidget.setGlyph("bluetooth-off")
        barWidget.setText("--")
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
    local inp = parseStr(payload, "input")
    inputName = inp ~= "" and inp or "--"
    updateDisplay()
end

local function currentIdx()
    for i, name in ipairs(INPUTS) do
        if name == inputName then return i end
    end
    return 1
end

function onClick()
    if not connected then return end
    local prev = ((currentIdx() - 2) % #INPUTS) + 1
    noctalia.runAsync("cyrus-cmd input:" .. INPUTS[prev])
end

function onRightClick()
    if not connected then return end
    local next = (currentIdx() % #INPUTS) + 1
    noctalia.runAsync("cyrus-cmd input:" .. INPUTS[next])
end
