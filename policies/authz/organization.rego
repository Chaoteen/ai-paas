package authz.organization

# 默认拒绝
default allow := false

# 允许规则
allow if {
    input.subject.role == "owner"
    input.subject.organization_id == input.resource.organization_id
}

allow if {
    input.subject.role == "admin"
    input.subject.organization_id == input.resource.organization_id
    input.action.type in ["read", "write"]
}

allow if {
    input.subject.role == "superadmin"
}
