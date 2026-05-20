-- Noctalia v5 scripted widget — Cyrus ONE volume
-- Left: vol−   Right: vol+   Middle: toggle mute

local connected = false
local volPct    = 0
local muted     = false
local started   = false

local function parseBool(json, key)
    return json:match('"' .. key .. '":%s*true') ~= nil
end

local function parseNum(json, key)
    return tonumber(json:match('"' .. key .. '":%s*(%d+)')) or 0
end

local function updateDisplay()
    if connected then
        if muted then
            barWidget.setGlyph("volume-off")
            barWidget.setText("muted")
            barWidget.setColor("on_surface_variant")
            barWidget.setGlyphColor("on_surface_variant")
        else
            barWidget.setGlyph("volume")
            barWidget.setText(string.format("%d%%", volPct))
            barWidget.setColor("on_surface")
            barWidget.setGlyphColor("primary")
        end
    else
        barWidget.setGlyph("volume-off")
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
    volPct    = parseNum(payload, "vol_pct")
    muted     = parseBool(payload, "muted")
    updateDisplay()
end

function onClick()
    if not connected then return end
    noctalia.runAsync("cyrus-cmd vol-")
end

function onRightClick()
    if not connected then return end
    noctalia.runAsync("cyrus-cmd vol+")
end

function onMiddleClick()
    if not connected then return end
    noctalia.runAsync("cyrus-cmd " .. (muted and "unmute" or "mute"))
end
