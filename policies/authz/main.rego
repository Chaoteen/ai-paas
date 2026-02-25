package authz

import data.authz.organization
import data.authz.project
import data.authz.resource
import data.authz.mfa

# 默认拒绝
default allow := false

# 允许规则：所有子策略都必须允许
# 由于子策略都有 default allow := false，这里直接调用即可
allow if {
    organization.allow
    project.allow
    resource.allow
    mfa.allow
}

# 综合评估结果
evaluation_result := {
    "allowed": allow,
    "checks": {
        "organization": organization.allow,
        "project": project.allow,
        "resource": resource.allow,
        "mfa": mfa.allow
    }
}
