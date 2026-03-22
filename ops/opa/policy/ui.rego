package ui

default allow = false

# ---- Canonical menu ids ----
admin_only_menu_ids := {"admin", "workflows", "flowise", "promptflow", "langgraph", "opa"}
user_menu_ids := {"chat", "history", "settings"}

# ---- Input normalization helpers ----
is_menu if {
  input.resource.type == "menu"
}

is_menu if {
  input.resource.kind == "menu"
}

is_admin if {
  input.subject.is_admin
}

is_admin if {
  input.user.is_admin
}

menu_id := rid if {
  rid := input.resource.id
}

# ---- Admin-only menus ----
allow if {
  is_menu
  menu_id in admin_only_menu_ids
  is_admin
}

# ---- Normal user menus ----
allow if {
  is_menu
  menu_id in user_menu_ids
}