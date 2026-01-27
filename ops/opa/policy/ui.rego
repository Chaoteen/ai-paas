package ui

# default deny
default allow = false

# ---- Admin-only menus ----
admin_only_menu_ids := {"admin", "workflows", "promptflow", "langgraph"}

allow if {
  input.resource.type == "menu"
  input.resource.id in admin_only_menu_ids
  input.subject.is_admin
}

# ---- Normal user menus (explicit allow) ----
# 你可以按实际菜单逐步补全；先放一个最小集合，避免“新增菜单默认放行”
user_menu_ids := {"chat", "history", "settings"}

allow if {
  input.resource.type == "menu"
  input.resource.id in user_menu_ids
}

