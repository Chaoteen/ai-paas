package authz.simple

allow = true if {
    input.subject.role == "admin"
}
