package ui

allow contains true if {
    input.subject.is_admin == false
    input.resource.id == "chat"
}

allow contains true if {
    input.subject.is_admin == true
    input.resource.id == "admin"
}

allow contains true if {
    input.subject.is_admin == true
    input.resource.id == "chat"
}
