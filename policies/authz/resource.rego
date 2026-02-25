package authz.resource

default allow := false

allow if {
    input.resource.sensitivity == "public"
}

allow if {
    input.resource.sensitivity == "internal"
    input.subject.auth_level in ["basic", "full"]
    input.subject.organization_id == input.resource.organization_id
}

allow if {
    input.resource.sensitivity == "confidential"
    input.subject.auth_level == "full"
    input.subject.level in ["L4", "L5", "L6"]
    input.subject.organization_id == input.resource.organization_id
}

allow if {
    input.subject.user_id == input.resource.owner_id
}

allow if {
    input.subject.role == "superadmin"
}
