package authz.project

default allow := false

allow if {
    input.subject.user_id == input.resource.owner_id
}

allow if {
    some role in input.resource.allowed_roles
    role == input.subject.role
    input.subject.organization_id == input.resource.organization_id
}

allow if {
    input.subject.role == "superadmin"
}

allow if {
    input.subject.role == "admin"
    input.subject.organization_id == input.resource.organization_id
    input.action.type != "delete"
}
