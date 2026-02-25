package authz.compliance

import future.keywords.if
import future.keywords.in

# ==================== 规则定义 ====================

# 允许访问如果地理位置合规
allow_location if {
    some location in input.resource.allowed_locations
    location == input.environment.location
}

# 拒绝地理位置不合规的访问
deny_location[msg] if {
    count(input.resource.allowed_locations) > 0
    not allow_location
    msg := sprintf("访问被拒绝：用户位置 %s 不在允许的位置列表 %v 中", 
                   [input.environment.location, input.resource.allowed_locations])
}

# 允许访问如果 GDPR 合规
allow_gdpr if {
    not ("gdpr" in input.resource.compliance_tags)
}

allow_gdpr if {
    "gdpr" in input.resource.compliance_tags
    input.environment.location in ["eu-west-1", "eu-central-1"]
}

# 拒绝 GDPR 不合规的访问
deny_gdpr[msg] if {
    "gdpr" in input.resource.compliance_tags
    not allow_gdpr
    msg := sprintf("访问被拒绝：GDPR 数据只能在欧盟区域访问，当前位于 %s", 
                   [input.environment.location])
}

# ==================== 综合检查 ====================

# 所有合规检查通过
compliance_pass if {
    allow_location
    allow_gdpr
}

# 合规检查结果
compliance_result := {
    "location_ok": allow_location,
    "gdpr_ok": allow_gdpr,
    "pass": compliance_pass
}
