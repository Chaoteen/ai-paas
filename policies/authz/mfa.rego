package authz.mfa

default allow := false

allow if {
    not input.resource.requires_mfa
}

allow if {
    input.resource.requires_mfa
    input.subject.mfa_verified == true
}
