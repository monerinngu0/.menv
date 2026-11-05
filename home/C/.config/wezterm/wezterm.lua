local wezterm = require 'wezterm'

local config = wezterm.config_builder()

config.default_domain = 'WSL:Ubuntu'

-- Choose a WSL distribution for a new tab (Ubuntu or Ubuntu-Test).
config.keys = {
  {
    key = 'u',
    mods = 'CTRL|SHIFT',
    action = wezterm.action.ShowLauncherArgs({ flags = 'DOMAINS', title = 'Select WSL distribution' }),
  },
}

config.canonicalize_pasted_newlines = "LineFeed"

config.automatically_reload_config = true
config.font_size = 12.0

config.line_height = 1.0
config.cell_width = 1.0

config.use_ime = true
config.window_background_opacity = 0.7
config.window_decorations = "RESIZE"

config.window_frame = {
  inactive_titlebar_bg = "none",
  active_titlebar_bg = "none",
}

config.window_background_gradient = {
  colors = { "#000000" },
}

config.colors = {
  tab_bar = {
    inactive_tab_edge = "none",
  }
}

local SOLID_LEFT_ARROW = wezterm.nerdfonts.ple_lower_right_triangle
local SOLID_RIGHT_ARROW = wezterm.nerdfonts.ple_upper_left_triangle

wezterm.on("format-tab-title", function (tab, tabs, panes, config, hover, max_width)
  local background = "#6E6E6E"
  local foreground = "#FFFFFF"
  local edge_background = "none"

  if tab.is_active then
    background = "#B0AE35"
    foreground = "#FFFFFF"
  end

  local edge_foreground = background
  local title = "   " .. wezterm.truncate_right(tab.active_pane.title, max_width - 1) .. "   "

  return {
    { Background = { Color = edge_background } },
    { Background = { Color = edge_foreground } },
    { Background = { Color = background } },
    { Foreground = { Color = foreground } },
    { Text = title },
    { Background = { Color = edge_background } },
    { Foreground = { Color = edge_foreground } },
    { Text = SOLID_RIGHT_ARROW },
  }

end)

wezterm.on('gui-startup', function()
  wezterm.mux.spawn_window({
    position = {
      x = 200,
      y = 100,
    },
  })
end)

config.initial_cols = 100
config.initial_rows = 23

return config